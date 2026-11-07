"""
test_llm_providers.py — the contract both LLM backends must satisfy.

These tests never touch the network. They exist because the dangerous failures in
a self-hosted setup are all SILENT: a server that ignores the JSON Schema still
answers, a context window too small still answers, and a provenance field that
records the configured model rather than the one that replied still looks right.
Each of those is pinned here.

The classification figures are unaffected by any of this — the frozen rule assigns
labels with no API call at all — so what is protected here is the narrative layer,
faithfulness (T5.6) and run-to-run consistency (T5.4).
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

from hrv_rag.config.settings import LLMConfig, OllamaConfig
from hrv_rag.core.schemas import LLMResponse
from hrv_rag.rag.llm import (BaseInterpreter, GeminiInterpreter,
                             OllamaInterpreter, make_interpreter)

VALID_REPLY = {
    "stress_level": "moderate",
    "confidence": 0.6,
    "reasoning": "RMSSD fell 24% below the personal baseline.",
    "references": ["KB-RMSSD-01"],
    "uncertainty_notes": "PPG modality lowers confidence.",
    "user_summary": "Tubuhmu menunjukkan tanda ketegangan sedang.",
    "user_recommendation": "Tarik napas perlahan selama sepuluh detik sebelum menjawab.",
}


class FakeResponse:
    def __init__(self, payload, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"Server error '{self.status_code}' for url /x")

    def json(self):
        return self._payload


class FakeClient:
    """Stands in for httpx.Client, recording what the interpreter actually sent."""

    def __init__(self, chat_content=None, tags=None, status: int = 200) -> None:
        self.chat_content = (json.dumps(VALID_REPLY) if chat_content is None
                             else chat_content)
        self.tags = tags if tags is not None else [
            {"name": "qwen3:32b", "digest": "sha256:abc123def456789012345"}
        ]
        self.status = status
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    def post(self, path, json=None):
        self.posts.append((path, json))
        content = self.chat_content
        # `check()` sends its own tiny probe schema. Answering it with the main
        # reply would make the probe fail for the wrong reason, so the fake
        # replies in the shape it was actually asked for — which is exactly what
        # a server honouring `format` does.
        properties = (json or {}).get("format", {})
        if isinstance(properties, dict) and "ok" in properties.get("properties", {}):
            content = '{"ok": true, "note": "ready"}'
        return FakeResponse({"message": {"content": content}}, self.status)

    def get(self, path):
        self.gets.append(path)
        return FakeResponse({"models": self.tags}, self.status)


def make_ollama(client: FakeClient | None = None, **kw) -> OllamaInterpreter:
    return OllamaInterpreter(
        cfg=LLMConfig(), ollama_cfg=OllamaConfig(),
        base_url="https://instance.vast.ai:8080", api_key="key",
        model="qwen3:32b", client=client or FakeClient(), **kw,
    )


# --------------------------------------------------------------- the contract
def test_both_backends_share_one_contract():
    # An `if provider == ...` scattered through the pipeline would let the two
    # drift; the base class is what stops that.
    assert issubclass(GeminiInterpreter, BaseInterpreter)
    assert issubclass(OllamaInterpreter, BaseInterpreter)


def test_interpret_delegates_to_the_schema_aware_call():
    ollama = make_ollama()
    result = ollama.interpret("prompt")
    assert isinstance(result, LLMResponse)
    assert result.stress_level.value == "moderate"
    assert result.user_summary.startswith("Tubuhmu")


# ------------------------------------------------- the structured-output guarantee
def test_sends_the_full_json_schema_not_the_string_json():
    # This is the whole reason for using the native /ollama route. `format: "json"`
    # would ask for "some JSON"; the schema constrains it to THIS shape, which is
    # what `response_schema` gives on Gemini.
    client = FakeClient()
    make_ollama(client).interpret("prompt")

    path, body = client.posts[0]
    assert path == "/api/chat"
    assert body["format"] != "json"
    assert body["format"]["properties"].keys() >= {
        "stress_level", "confidence", "reasoning", "references",
        "user_summary", "user_recommendation",
    }


def test_fails_loudly_when_the_server_ignores_the_schema():
    # Ollama below 0.5 accepts `format` and disregards it, answering in prose. The
    # call succeeds at the HTTP level, so nothing but this check would notice.
    client = FakeClient(chat_content="Sure! The stress level looks moderate.")
    with pytest.raises(ValueError, match="ignored the `format` schema"):
        make_ollama(client).interpret("prompt")


def test_fails_loudly_on_an_empty_reply():
    with pytest.raises(ValueError, match="empty response"):
        make_ollama(FakeClient(chat_content="   ")).interpret("prompt")


def test_rejects_json_that_does_not_match_the_schema():
    # Well-formed JSON of the wrong shape must not become a half-filled result.
    partial = json.dumps({"stress_level": "moderate", "confidence": 0.6})
    with pytest.raises(ValidationError):
        make_ollama(FakeClient(chat_content=partial)).interpret("prompt")


def test_confidence_outside_zero_to_one_is_refused():
    bad = json.dumps({**VALID_REPLY, "confidence": 1.7})
    with pytest.raises(ValidationError):
        make_ollama(FakeClient(chat_content=bad)).interpret("prompt")


# ------------------------------------------------------- the silent-truncation guard
def test_sends_a_context_window_large_enough_for_the_retrieved_chunks():
    # The failure this prevents is the worst kind: a prompt longer than num_ctx is
    # truncated, not rejected, so the retrieved knowledge silently never reaches
    # the model while it still returns a confident, well-formed answer. The system
    # would look like RAG while having stopped being RAG.
    client = FakeClient()
    make_ollama(client).interpret("prompt")
    _, body = client.posts[0]
    assert body["options"]["num_ctx"] >= 8192


def test_sends_a_fixed_seed_so_consistency_can_be_measured():
    client = FakeClient()
    make_ollama(client).interpret("prompt")
    _, body = client.posts[0]
    assert body["options"]["seed"] == OllamaConfig().seed
    assert body["stream"] is False


def test_temperature_can_be_overridden_per_call():
    # U3.5 sweeps temperature and T5.4 measures the spread it produces.
    client = FakeClient()
    make_ollama(client).interpret("prompt", temperature=0.7)
    _, body = client.posts[0]
    assert body["options"]["temperature"] == 0.7


# ------------------------------------------------------------------ provenance
def test_model_label_names_the_tag_before_the_digest_is_known():
    assert make_ollama().model_label == "ollama:qwen3:32b"


def test_model_label_carries_the_digest_once_check_has_run():
    # A tag can be re-pulled and point at different weights later; the digest is
    # the part that makes a reported result reproducible (U4.4).
    ollama = make_ollama()
    ollama.check()
    assert ollama.model_label.startswith("ollama:qwen3:32b@sha256:")


def test_check_refuses_a_model_that_was_never_pulled():
    client = FakeClient(tags=[{"name": "llama3.3:70b", "digest": "sha256:zzz"}])
    with pytest.raises(RuntimeError, match="not on the server"):
        make_ollama(client).check()


def test_check_reports_the_settings_that_would_corrupt_results_silently():
    report = make_ollama().check()
    assert report["num_ctx"] >= 8192
    assert report["digest"].startswith("sha256:")
    assert report["structured_output"] is True


# ----------------------------------------------------- retrying the right things
def test_a_rejected_key_fails_at_once_even_at_a_port_containing_503(monkeypatch):
    # The bug this pins down is not hypothetical. Vast.ai hands out arbitrary high
    # ports, and the retry layer used to decide by looking for "503" anywhere in
    # the error text — so a fatal 401 reached at http://host:11503/... was retried
    # five times across roughly four minutes before the real cause surfaced.
    slept: list[float] = []
    monkeypatch.setattr("hrv_rag.rag.rate_limit.time.sleep", slept.append)

    client = FakeClient(status=401)
    with pytest.raises(RuntimeError, match="Ollama HTTP 401"):
        make_ollama(client).interpret("prompt")

    assert slept == []
    assert len(client.posts) == 1


def test_a_busy_server_is_retried(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("hrv_rag.rag.rate_limit.time.sleep", slept.append)

    client = FakeClient(status=503)
    with pytest.raises(RuntimeError, match="Still failing after"):
        make_ollama(client).interpret("prompt")

    assert len(client.posts) == 5
    assert slept, "a 503 should back off before trying again"


def test_a_sleeping_instance_is_retried_but_a_bad_request_is_not():
    from hrv_rag.rag.llm import OllamaHTTPError, _is_retryable_ollama

    class ConnectError(Exception):
        pass

    assert _is_retryable_ollama(ConnectError("instance waking up")) is True
    assert _is_retryable_ollama(OllamaHTTPError(502, "bad gateway")) is True
    assert _is_retryable_ollama(OllamaHTTPError(404, "model not found")) is False
    assert _is_retryable_ollama(ValueError("malformed prompt")) is False


def test_gemini_keeps_its_original_retry_behaviour(monkeypatch):
    # The substring rule is still the best available for the Gemini SDK, which
    # reports its status only inside prose. Changing it was never the intention.
    from hrv_rag.rag.rate_limit import call_with_retry

    monkeypatch.setattr("hrv_rag.rag.rate_limit.time.sleep", lambda s: None)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("503 UNAVAILABLE: model overloaded")
        return "ok"

    assert call_with_retry(flaky) == "ok"
    assert attempts["n"] == 3


# ------------------------------------------------------------- configuration
def test_missing_base_url_says_what_to_do(monkeypatch):
    # The real .env is loaded by other test modules (test_api imports the app,
    # which calls load_dotenv), so its OPENWEBUI_BASE_URL would otherwise fill
    # the blank in and this test would pass only when run on its own.
    for name in ("OPENWEBUI_BASE_URL", "OLLAMA_BASE_URL", "VASTAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="OPENWEBUI_BASE_URL"):
        OllamaInterpreter(base_url="", api_key="k", model="m",
                          client=FakeClient())


def test_missing_model_refuses_rather_than_guessing(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)  # see the test above
    # No default tag on purpose: a wrong one would have the server answer with
    # whatever it does have, and the result would name a model that never ran.
    with pytest.raises(RuntimeError, match="OLLAMA_MODEL"):
        OllamaInterpreter(base_url="https://x", api_key="k", model="",
                          ollama_cfg=OllamaConfig(model=""), client=FakeClient())


def test_the_openwebui_route_can_be_selected(monkeypatch):
    # Two routes reach the same Ollama on a Vast.ai instance: its own mapped port,
    # and OpenWebUI's proxy. They differ only by a path prefix, and picking the
    # wrong one 404s — so which is in use is configuration, not an assumption.
    monkeypatch.setenv("OLLAMA_ROUTE", "openwebui")
    client = FakeClient()
    make_ollama(client).interpret("prompt")
    assert client.posts[0][0] == "/ollama/api/chat"


def test_the_direct_route_is_the_default(monkeypatch):
    # Default, because it needs no OpenWebUI account: the port is still fronted by
    # the instance portal, so the Vast access token authenticates it.
    monkeypatch.delenv("OLLAMA_ROUTE", raising=False)
    client = FakeClient()
    make_ollama(client).interpret("prompt")
    assert client.posts[0][0] == "/api/chat"


def test_a_pasted_portal_link_is_cleaned_of_its_query_string():
    # Vast.ai gives you the address with the access token attached, and pasting it
    # verbatim is the obvious thing to do. Left on, the query lands in the middle
    # of every request path and every call 404s for a reason nothing explains.
    ollama = OllamaInterpreter(
        cfg=LLMConfig(), ollama_cfg=OllamaConfig(),
        base_url="http://1.2.3.4:20703/?token=abc123&redir=false",
        api_key="sk-real", model="qwen3:32b", client=FakeClient(),
    )
    assert ollama.base_url == "http://1.2.3.4:20703"


def test_a_url_pasted_into_the_key_field_says_so():
    # The two values sit next to each other in .env and were in fact swapped. The
    # server answers 401, which reads as "wrong key" and sends you to regenerate a
    # key that was never the problem.
    with pytest.raises(RuntimeError, match="looks like a URL"):
        OllamaInterpreter(
            cfg=LLMConfig(), ollama_cfg=OllamaConfig(),
            base_url="http://1.2.3.4:20703",
            api_key="http://1.2.3.4:20160/?token=abc123",
            model="qwen3:32b", client=FakeClient(),
        )


def test_a_bare_host_without_a_scheme_still_works():
    ollama = OllamaInterpreter(
        cfg=LLMConfig(), ollama_cfg=OllamaConfig(), base_url="1.2.3.4:20703/",
        api_key="sk-real", model="qwen3:32b", client=FakeClient(),
    )
    assert ollama.base_url == "1.2.3.4:20703"


def test_factory_defaults_to_gemini_so_older_results_stay_reproducible(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("hrv_rag.rag.llm.load_dotenv", lambda *a, **k: None)
    created = {}
    monkeypatch.setattr("hrv_rag.rag.llm.GeminiInterpreter",
                        lambda cfg: created.setdefault("provider", "gemini"))
    make_interpreter(LLMConfig())
    assert created["provider"] == "gemini"


def test_factory_switches_backend_from_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setattr("hrv_rag.rag.llm.load_dotenv", lambda *a, **k: None)
    created = {}
    monkeypatch.setattr("hrv_rag.rag.llm.OllamaInterpreter",
                        lambda cfg: created.setdefault("provider", "ollama"))
    make_interpreter(LLMConfig())
    assert created["provider"] == "ollama"


def test_unknown_provider_is_refused():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        make_interpreter(LLMConfig(), provider="chatgpt")


# --------------------------------------------------- the pipeline records the truth
def test_pipeline_records_the_model_that_actually_answered(monkeypatch):
    # Before the second backend existed this field came from `cfg.model`, which is
    # the CONFIGURED name. With two backends those diverge, and a result that
    # names the wrong model is worse than one that names none.
    from hrv_rag.core.schemas import AssessmentInput, SignalQuality
    from hrv_rag.core.types import Modality, Phase
    from hrv_rag.rag import pipeline as pipeline_mod

    class FakeIndex:
        kb_version = "kb_v2.0"

        def search(self, query):
            return []

    class FakePrompt:
        pass

    monkeypatch.setattr(pipeline_mod, "build_query", lambda data: "q")
    monkeypatch.setattr(pipeline_mod, "build_prompt",
                        lambda data, chunks, version: "prompt text")

    pipe = pipeline_mod.AssessmentPipeline(
        index=FakeIndex(), interpreter=make_ollama(), cfg=LLMConfig()
    )
    result = pipe.assess(AssessmentInput(
        session_id="s1", segment_index=1, modality=Modality.PPG,
        device="Coospo HW9 armband", phase=Phase.QUESTION,
        features={"rmssd": 31.7}, reactivity={"rmssd": -24.0},
        signal_quality=SignalQuality(outlier_pct=2.4, is_acceptable=True),
    ))
    assert result.model == "ollama:qwen3:32b"
    assert result.model != LLMConfig().model



# ======================================================== OpenRouter (19 Oct 2026)
from hrv_rag.config.settings import OpenRouterConfig  # noqa: E402
from hrv_rag.rag.llm import (OpenRouterHTTPError,  # noqa: E402
                             OpenRouterInterpreter, _is_retryable_openrouter)


class FakeOpenRouterClient:
    """Stands in for httpx.Client on the OpenRouter route."""

    def __init__(self, content=None, status: int = 200, body=None,
                 model: str = "deepseek/deepseek-v4.1-flash-20261001") -> None:
        self.content = json.dumps(VALID_REPLY) if content is None else content
        self.status = status
        self.body = body
        self.model = model
        self.posts: list[tuple[str, dict]] = []

    def post(self, path, json=None):
        self.posts.append((path, json))
        if self.body is not None:
            return FakeResponse(self.body, self.status)
        return FakeResponse({
            "model": self.model,
            "choices": [{"message": {"content": self.content}}],
        }, self.status)


def make_openrouter(client: FakeOpenRouterClient | None = None,
                    **kw) -> OpenRouterInterpreter:
    return OpenRouterInterpreter(
        cfg=LLMConfig(), openrouter_cfg=OpenRouterConfig(),
        api_key="sk-or-test", model="deepseek/deepseek-v4.1-flash",
        client=client or FakeOpenRouterClient(), **kw,
    )


def test_openrouter_shares_the_contract():
    assert issubclass(OpenRouterInterpreter, BaseInterpreter)
    result = make_openrouter().interpret("prompt")
    assert isinstance(result, LLMResponse)
    assert result.stress_level.value == "moderate"


def test_openrouter_sends_the_schema_it_cannot_enforce_through_the_api():
    # json_object mode does not carry the schema, so the system message must, or
    # the model would guess the field names.
    client = FakeOpenRouterClient()
    make_openrouter(client).interpret("prompt")
    path, body = client.posts[0]
    assert path == "/chat/completions"
    assert body["response_format"] == {"type": "json_object"}
    system = body["messages"][0]
    assert system["role"] == "system"
    for field_name in ("stress_level", "user_summary", "user_recommendation"):
        assert field_name in system["content"]
    assert body["messages"][1] == {"role": "user", "content": "prompt"}


def test_openrouter_routes_like_the_ai_gateway():
    # require_parameters stops an upstream that silently ignores response_format;
    # data_collection=deny keeps session data away from training logs.
    client = FakeOpenRouterClient()
    make_openrouter(client).interpret("prompt")
    _, body = client.posts[0]
    assert body["provider"]["require_parameters"] is True
    assert body["provider"]["data_collection"] == "deny"
    assert body["reasoning"] == {"effort": "none"}
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == LLMConfig().max_output_tokens


def test_openrouter_temperature_can_be_overridden_per_call():
    client = FakeOpenRouterClient()
    make_openrouter(client).interpret("prompt", temperature=0.7)
    assert client.posts[0][1]["temperature"] == 0.7


def test_openrouter_records_the_model_that_actually_answered():
    interp = make_openrouter()
    assert interp.model_label == "openrouter:deepseek/deepseek-v4.1-flash"
    interp.interpret("prompt")
    assert (interp.model_label
            == "openrouter:deepseek/deepseek-v4.1-flash-20261001")


def test_openrouter_rejects_prose_instead_of_json():
    client = FakeOpenRouterClient(content="The stress level looks moderate.")
    with pytest.raises(ValueError, match="did not return JSON"):
        make_openrouter(client).interpret("prompt")


def test_openrouter_rejects_json_of_the_wrong_shape():
    partial = json.dumps({"stress_level": "moderate", "confidence": 0.6})
    with pytest.raises(ValidationError):
        make_openrouter(FakeOpenRouterClient(content=partial)).interpret("prompt")


def test_openrouter_accepts_valid_json_inside_a_code_fence():
    fenced = "```json\n" + json.dumps(VALID_REPLY) + "\n```"
    result = make_openrouter(FakeOpenRouterClient(content=fenced)).interpret("p")
    assert result.confidence == 0.6


def test_openrouter_fails_loudly_on_an_empty_reply():
    with pytest.raises(ValueError, match="empty response"):
        make_openrouter(FakeOpenRouterClient(content="  ")).interpret("prompt")


def test_openrouter_rejected_key_is_not_retried(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("hrv_rag.rag.rate_limit.time.sleep", slept.append)
    client = FakeOpenRouterClient(status=401,
                                  body={"error": {"message": "No auth"}})
    with pytest.raises(RuntimeError, match="OpenRouter HTTP 401"):
        make_openrouter(client).interpret("prompt")
    assert slept == []
    assert len(client.posts) == 1


def test_openrouter_busy_upstream_is_retried(monkeypatch):
    monkeypatch.setattr("hrv_rag.rag.rate_limit.time.sleep", lambda s: None)
    client = FakeOpenRouterClient(status=429,
                                  body={"error": {"message": "rate limited"}})
    with pytest.raises(RuntimeError, match="Still failing after"):
        make_openrouter(client).interpret("prompt")
    assert len(client.posts) == 5


def test_openrouter_error_inside_a_200_body_is_retried_not_parsed():
    assert _is_retryable_openrouter(OpenRouterHTTPError(None, "upstream")) is True
    assert _is_retryable_openrouter(OpenRouterHTTPError(400, "bad")) is False
    assert _is_retryable_openrouter(OpenRouterHTTPError(503, "busy")) is True


def test_openrouter_error_message_does_not_echo_the_prompt():
    # The body of a validation error can quote the request, which holds session
    # data. Only error.message is kept.
    client = FakeOpenRouterClient(status=400, body={
        "error": {"message": "invalid model", "metadata": {"raw": "SECRET PROMPT"}},
    })
    with pytest.raises(RuntimeError) as info:
        make_openrouter(client).interpret("prompt")
    assert "SECRET PROMPT" not in str(info.value)


def test_openrouter_without_a_model_refuses_rather_than_guessing(monkeypatch):
    monkeypatch.delenv("HRV_OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr("hrv_rag.rag.llm.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="HRV_OPENROUTER_MODEL"):
        OpenRouterInterpreter(api_key="k", openrouter_cfg=OpenRouterConfig(),
                              client=FakeOpenRouterClient())


def test_openrouter_without_a_key_says_what_to_do(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("hrv_rag.rag.llm.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterInterpreter(model="m", client=FakeOpenRouterClient())


def test_openrouter_model_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("HRV_OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
    monkeypatch.setattr("hrv_rag.rag.llm.load_dotenv", lambda *a, **k: None)
    interp = OpenRouterInterpreter(api_key="k", client=FakeOpenRouterClient())
    assert interp.model == "deepseek/deepseek-v4.1-flash"


def test_factory_builds_openrouter_from_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("hrv_rag.rag.llm.load_dotenv", lambda *a, **k: None)
    created = {}
    monkeypatch.setattr("hrv_rag.rag.llm.OpenRouterInterpreter",
                        lambda cfg: created.setdefault("provider", "openrouter"))
    make_interpreter(LLMConfig())
    assert created["provider"] == "openrouter"


# --------------------------------------------- the Gemini model from the environment
class _FakeGenai:
    class Client:
        def __init__(self, api_key):
            self.api_key = api_key


def _gemini(monkeypatch) -> GeminiInterpreter:
    import sys
    import types as _types
    google = _types.ModuleType("google")
    google.genai = _FakeGenai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", _FakeGenai)
    return GeminiInterpreter(LLMConfig(), api_key="k")


def test_gemini_model_can_be_set_from_hrv_gemini_model(monkeypatch):
    monkeypatch.setenv("HRV_GEMINI_MODEL", "gemini-3.5-flash")
    assert _gemini(monkeypatch).model_label == "gemini-3.5-flash"


def test_gemini_ignores_the_gateways_gemini_model(monkeypatch):
    # GEMINI_MODEL belongs to the AI Gateway. A copy of its .env pointing at a
    # different model must not silently re-run the thesis on that model.
    monkeypatch.delenv("HRV_GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    assert _gemini(monkeypatch).model_label == LLMConfig().model
