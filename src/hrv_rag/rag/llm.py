"""
llm.py — The interpretation call, on either of two backends.

The response schema is enforced by the API rather than requested in prose. The
model is handed the pydantic model as a structured-output schema, so the reply is
constrained to that shape instead of being politely asked for JSON. That removes an
entire class of failure — malformed or truncated JSON — from the pipeline, and it
is the property that had to survive when a second backend was added.

WHY TWO BACKENDS, AND WHY AN ABSTRACT BASE HERE

CLAUDE.md admits a class hierarchy only where genuine variants exist — modality and
dataset. The backend is now a third such axis, and it earns its place the same way:
Gemini and a self-hosted Ollama differ in transport, in how the schema is declared,
in what provenance they can report, and in which failures are worth retrying. An
`if provider == ...` running through every method would hide exactly the
differences that must be defensible.

What the split buys the thesis:

- **Quota.** The free Gemini tier allows 20 calls a day, which cannot pay for the
  ablations the title depends on (BACKLOG T5.8, U3.2, U3.3).
- **Independence.** L8 records the risk of resting on a model the vendor can change
  silently. Running the same pipeline on two unrelated models turns that from a
  limitation into evidence that the architecture is not vendor-specific.
- **Reproducibility.** Ollama pins weights by digest and accepts a seed. Gemini
  offers neither.

What it deliberately does NOT change: every classification figure already reported
comes from the frozen scoring rule with no API call whatsoever
(`scripts/run_holdout.py`). Only narrative, faithfulness and consistency depend on
which model answers.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any

from dotenv import load_dotenv

from ..config.settings import LLMConfig, OllamaConfig, settings
from ..core.schemas import LLMResponse
from .rate_limit import RateLimiter, call_with_retry

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

#: Statuses from a self-hosted instance that clear on their own.
_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})

#: httpx failures that mean "the machine was not ready", not "the request was
#: wrong". A rented GPU refuses connections for a few seconds while it wakes.
_RETRYABLE_TRANSPORT = ("ConnectError", "ConnectTimeout", "RemoteProtocolError")


class OllamaHTTPError(RuntimeError):
    """
    An error response from the Ollama proxy, carrying its status as a number.

    A typed status rather than one buried in prose, because the retry layer has to
    tell a busy server from a rejected key — and a self-hosted instance answers at
    an arbitrary port. An error message quoting `http://host:11503/ollama/api/chat`
    contains "503" while meaning nothing of the sort, so a fatal 401 at that
    address would be retried for four minutes before the real cause surfaced.
    """

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        super().__init__(f"Ollama HTTP {status}: {detail[:200]}")


def _first_env(*names: str) -> str:
    """
    First of these environment variables that carries a value.

    Case-sensitive, and the names are listed in the order they should win, so a
    correctly-named variable always beats an alias.
    """
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _is_retryable_ollama(exc: Exception) -> bool:
    if isinstance(exc, OllamaHTTPError):
        return exc.status in _RETRYABLE_HTTP
    return type(exc).__name__ in _RETRYABLE_TRANSPORT


class BaseInterpreter(ABC):
    """
    The contract every backend must satisfy.

    Two methods rather than one because the hybrid path needs a different response
    shape from the per-segment path: it returns narrative without a stress level,
    since the rule already decided that (K16). Parameterising the schema keeps one
    client instead of two that would drift apart.
    """

    cfg: LLMConfig

    @property
    @abstractmethod
    def model_label(self) -> str:
        """
        What actually answered, recorded in every `Assessment` for provenance.

        Not simply `cfg.model`: the configured name and the model that replied can
        differ, and the whole point of U4.4 is that a result names the thing that
        produced it.
        """

    @abstractmethod
    def interpret_as(self, prompt: str, schema: type,
                     temperature: float | None = None) -> Any:
        """Send the prompt constrained to any pydantic schema the caller supplies."""

    def interpret(self, prompt: str,
                  temperature: float | None = None) -> LLMResponse:
        """
        Send the prompt and return the parsed response.

        `temperature` can be overridden per call, which is what the U3.5 sweep and
        the run-to-run consistency measurement (T5.4) need. The default is 0.0 for
        maximum determinism — though determinism is never assumed, only measured.
        """
        return self.interpret_as(prompt, LLMResponse, temperature=temperature)


class GeminiInterpreter(BaseInterpreter):
    """
    Thin wrapper around the Gemini generation call.

    A class because it holds reusable state — the API client and the generation
    configuration — not because there is any variation to abstract over (K12). The
    variation now lives one level up, in `BaseInterpreter`.
    """

    def __init__(self, cfg: LLMConfig | None = None,
                 api_key: str | None = None) -> None:
        self.cfg = cfg or settings.llm

        if api_key is None:
            load_dotenv(_ENV_PATH)
            api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not found. Fill in the .env file at the repo root."
            )

        from google import genai
        self._client = genai.Client(api_key=api_key)

        # One limiter per interpreter, shared by every call it makes, so a batch
        # run paces itself rather than discovering the quota by being rejected.
        self._limiter = RateLimiter(self.cfg.requests_per_minute)

    @property
    def model_label(self) -> str:
        return self.cfg.model

    def interpret_as(self, prompt: str, schema: type,
                     temperature: float | None = None) -> Any:
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=(temperature if temperature is not None
                         else self.cfg.temperature),
            max_output_tokens=self.cfg.max_output_tokens,
        )
        self._limiter.wait()
        response = call_with_retry(
            lambda: self._client.models.generate_content(
                model=self.cfg.model, contents=prompt, config=config,
            )
        )
        if response.parsed is None:
            # Should not happen with a schema attached, but if the model returns
            # nothing usable it must fail loudly rather than yield a silent default.
            raise ValueError(
                f"Model returned no parsable response. Raw text: {response.text!r}"
            )
        return response.parsed


class OllamaInterpreter(BaseInterpreter):
    """
    A self-hosted model, reached through OpenWebUI's proxy to Ollama's native API.

    Two routing decisions are worth defending at the viva:

    **Native `/ollama/api/chat`, not the OpenAI-compatible route.** Only the native
    endpoint accepts a full JSON Schema in `format`. The OpenAI-compatible one
    takes `response_format`, whose pass-through to Ollama is not guaranteed, and
    losing schema enforcement would reintroduce exactly the malformed-JSON failures
    that the structured-output design exists to prevent.

    **Through OpenWebUI, not straight to port 11434.** A Vast.ai instance has a
    public address and Ollama ships with no authentication, so an exposed port is
    an open GPU for anyone who scans the range. The proxy keeps the API key in
    front of it.
    """

    def __init__(self, cfg: LLMConfig | None = None,
                 ollama_cfg: OllamaConfig | None = None,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 model: str | None = None,
                 client: Any | None = None) -> None:
        self.cfg = cfg or settings.llm
        self.ollama = ollama_cfg or settings.ollama

        if base_url is None or api_key is None or model is None:
            load_dotenv(_ENV_PATH)
        # Aliases accepted because the credential has two obvious names — it is
        # OpenWebUI's key, but it is the OLLAMA server it unlocks, and .env files
        # get written by hand. Refusing a key that is plainly present, over the
        # capitalisation of its label, is a bad trade for the person debugging it.
        base_url = base_url or _first_env("OPENWEBUI_BASE_URL", "OLLAMA_BASE_URL",
                                          "VASTAI_BASE_URL")
        api_key = api_key or _first_env("OPENWEBUI_API_KEY", "Ollama_API_KEY",
                                        "OLLAMA_API_KEY")
        model = model or _first_env("OLLAMA_MODEL") or self.ollama.model

        if not base_url:
            raise RuntimeError(
                "OPENWEBUI_BASE_URL not found. Add it to .env, e.g. "
                "OPENWEBUI_BASE_URL=https://<host>:<port>  (no trailing slash). "
                "A Vast.ai instance gets a new address every time it starts, so "
                "this belongs in .env and never in the code."
            )
        if not api_key:
            raise RuntimeError(
                "OPENWEBUI_API_KEY not found. Create one in OpenWebUI under "
                "Settings > Account > API keys, then add it to .env."
            )
        if not model:
            raise RuntimeError(
                "OLLAMA_MODEL not set. Use the tag exactly as `ollama list` "
                "reports it, e.g. OLLAMA_MODEL=qwen3:32b. There is no default on "
                "purpose: a wrong tag must fail here rather than have the server "
                "quietly answer with a different model."
            )

        # Vast.ai hands you a portal link with the access token in the query
        # string, and pasting it verbatim is the obvious thing to do. Left
        # attached, the query would land in the middle of every request path
        # (`...:20703/?token=abc/ollama/api/chat`) and every call would 404 for a
        # reason nothing in the message would explain.
        split = urlsplit(base_url.strip())
        if split.scheme and split.netloc:
            self.base_url = f"{split.scheme}://{split.netloc}"
        else:
            self.base_url = base_url.strip().rstrip("/")

        # The two values sit next to each other in .env and are easy to swap. A
        # URL sent as a bearer token produces a 401 that reads as "wrong key",
        # sending you to regenerate a key that was never the problem.
        if api_key.lower().startswith(("http://", "https://")):
            raise RuntimeError(
                "The API key looks like a URL. OPENWEBUI_API_KEY must be the key "
                "from OpenWebUI (Settings > Account > API keys), which begins "
                "with 'sk-' — not the address of the instance."
            )

        # `direct` (default) or `openwebui` — see `OllamaConfig.chat_path`.
        if _first_env("OLLAMA_ROUTE").lower() == "openwebui":
            self.ollama = replace(self.ollama, chat_path="/ollama/api/chat",
                                  tags_path="/ollama/api/tags")

        self.model = model
        self._digest: str | None = None

        if client is None:
            import httpx
            client = httpx.Client(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                timeout=self.ollama.timeout_sec,
            )
        self._client = client
        self._limiter = RateLimiter(self.ollama.requests_per_minute)

    @property
    def model_label(self) -> str:
        """
        `ollama:<tag>@<digest>` once the digest is known, `ollama:<tag>` before.

        The digest is the reproducibility claim: a tag like `qwen3:32b` can be
        re-pulled and point at different weights later, whereas the digest cannot.
        `check()` fills it in, which is why the runner scripts call `check()` first.
        """
        if self._digest:
            return f"ollama:{self.model}@{self._digest[:19]}"
        return f"ollama:{self.model}"

    def check(self) -> dict:
        """
        Verify the instance before a long run, and capture provenance.

        Worth its own method because all three failure modes here are ones that
        would otherwise surface deep inside a batch: an instance that has been
        stopped, a model tag that was never pulled, and an Ollama too old to
        enforce a JSON Schema. The last is the dangerous one — older versions
        accept only `format: "json"` and ignore a schema, so the call still
        succeeds and returns free-form JSON that may not match what the pipeline
        expects.
        """
        response = self._client.get(self.ollama.tags_path)
        status = getattr(response, "status_code", 200)
        if status >= 400:
            raise OllamaHTTPError(status, self._detail(response))
        models = response.json().get("models", [])

        available = [m.get("name", "") for m in models]
        if self.model not in available:
            raise RuntimeError(
                f"Model {self.model!r} is not on the server. Available: "
                f"{', '.join(available) or '(none)'}. Pull it first with "
                f"`ollama pull {self.model}`."
            )
        for entry in models:
            if entry.get("name") == self.model:
                self._digest = entry.get("digest")
                break

        # A schema the model cannot satisfy by accident, so a server that ignores
        # `format` fails this check instead of passing it by luck.
        from pydantic import BaseModel

        class _Probe(BaseModel):
            ok: bool
            note: str

        probe = self.interpret_as(
            "Reply with ok=true and note=\"ready\".", _Probe, temperature=0.0
        )
        return {
            "base_url": self.base_url,
            "model": self.model,
            "digest": self._digest,
            "model_label": self.model_label,
            "structured_output": bool(probe.ok or probe.note),
            "num_ctx": self.ollama.num_ctx,
            "seed": self.ollama.seed,
        }

    def interpret_as(self, prompt: str, schema: type,
                     temperature: float | None = None) -> Any:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            # The schema itself, not the string "json". This is what preserves the
            # guarantee `response_schema` gives on Gemini.
            "format": schema.model_json_schema(),
            "stream": False,
            "options": {
                "temperature": (temperature if temperature is not None
                                else self.cfg.temperature),
                "seed": self.ollama.seed,
                "num_ctx": self.ollama.num_ctx,
                "num_predict": self.cfg.max_output_tokens,
            },
        }

        self._limiter.wait()
        response = call_with_retry(
            lambda: self._post(self.ollama.chat_path, body),
            is_retryable=_is_retryable_ollama,
        )

        content = (response.get("message") or {}).get("content", "")
        if not content.strip():
            raise ValueError(
                f"Model returned an empty response. Full reply: {response!r}"
            )

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Model did not return JSON, which means the server ignored the "
                f"`format` schema — Ollama below 0.5 does that silently. Upgrade "
                f"it, or the structured-output guarantee is gone. "
                f"Raw text: {content[:300]!r}"
            ) from exc

        return schema.model_validate(payload)

    def _post(self, path: str, body: dict) -> dict:
        """One request, with the status raised as a number rather than as prose."""
        response = self._client.post(path, json=body)
        status = getattr(response, "status_code", 200)
        if status >= 400:
            raise OllamaHTTPError(status, self._detail(response))
        return response.json()

    @staticmethod
    def _detail(response: Any) -> str:
        """Whatever the server said, without letting a parse failure mask it."""
        try:
            return str(response.json())
        except Exception:                                        # noqa: BLE001
            return str(getattr(response, "text", ""))


def make_interpreter(cfg: LLMConfig | None = None,
                     provider: str | None = None) -> BaseInterpreter:
    """
    Build whichever backend the configuration asks for.

    Resolution order is environment, then config, so a single run can switch
    backend without touching a file that other results depend on:

        LLM_PROVIDER=ollama python scripts/run_assessment.py ...

    Gemini stays the default. Every figure reported so far was produced with it,
    and a default that silently changed backend would quietly make older results
    irreproducible.
    """
    cfg = cfg or settings.llm
    if provider is None:
        load_dotenv(_ENV_PATH)
        provider = os.getenv("LLM_PROVIDER") or cfg.provider

    provider = provider.strip().lower()
    if provider == "gemini":
        return GeminiInterpreter(cfg)
    if provider == "ollama":
        return OllamaInterpreter(cfg)
    raise ValueError(
        f"Unknown LLM provider {provider!r}. Use 'gemini' or 'ollama'."
    )
