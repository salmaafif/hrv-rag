"""
llm.py — The Gemini interpretation call (T4.4).

The response schema is enforced by the API rather than requested in prose. Gemini
is given the `LLMResponse` model as a structured-output schema, so the reply is
constrained to that shape instead of being politely asked for JSON. That removes an
entire class of failure — malformed or truncated JSON — from the pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from ..config.settings import LLMConfig, settings
from ..core.schemas import LLMResponse
from .rate_limit import RateLimiter, call_with_retry


class GeminiInterpreter:
    """
    Thin wrapper around the Gemini generation call.

    A class because it holds reusable state — the API client and the generation
    configuration — not because there is any variation to abstract over (K12).
    """

    def __init__(self, cfg: LLMConfig | None = None,
                 api_key: str | None = None) -> None:
        self.cfg = cfg or settings.llm

        if api_key is None:
            load_dotenv(Path(__file__).resolve().parents[3] / ".env")
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

    def interpret(self, prompt: str,
                  temperature: float | None = None) -> LLMResponse:
        """
        Send the prompt and return the parsed response.

        `temperature` can be overridden per call, which is what the U3.5 sweep and
        the run-to-run consistency measurement (T5.4) need. The default is 0.0 for
        maximum determinism — though determinism is never assumed, only measured.
        """
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMResponse,
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

        parsed = response.parsed
        if parsed is None:
            # Should not happen with a schema attached, but if the model returns
            # nothing usable it must fail loudly rather than yield a silent default.
            raise ValueError(
                f"Model returned no parsable response. Raw text: {response.text!r}"
            )
        return parsed
