"""
app.py — the HTTP surface KARIRLINK's gateway calls.

Two endpoints, matching `frontend/src/types/api.ts` field for field. That file is
the contract handed to the web team, and their PRD lists the output format of each
FastAPI module as an open question — so this is the answer to it, not a
reinterpretation of it.

WHAT THIS SERVICE IS RESPONSIBLE FOR, AND WHAT IT IS NOT. It computes every number
and writes the Indonesian prose. It cannot enforce how any of that is DISPLAYED,
and two of the project's rules are about display: the user must not be shown
feature names or scores, and the output is an indication of physiological pressure
rather than a diagnosis of anxiety. Once this is an API those become the caller's
obligations, so the technical layer is withheld unless it is explicitly asked for
— the safe thing is the default, rather than something the integrator has to
remember.

GRACEFUL DEGRADATION IS DELIBERATE. The label comes from a deterministic rule that
needs no API key. If Gemini is unreachable, out of quota, or caught inventing a
number, the measurements are still returned and only the prose is missing. The
KARIRLINK PRD treats this module as an optional dependency that must fail softly,
and this is what that means in practice.

Running it:
    uvicorn hrv_rag.api.app:app --reload
Environment:
    GEMINI_API_KEY   required only for the narrative
    HRV_API_KEYS     comma-separated keys this service will accept
    HRV_CORS_ORIGINS comma-separated origins allowed to call it
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .analysis import AnalysisError, build_session, build_timeline, prepare
from .narrative import write_session_narrative, write_timeline_narrative
from .schemas import SessionRequest, TimelineRequest
from ..core.types import Modality

log = logging.getLogger(__name__)

app = FastAPI(
    title="KARIRLINK — HRV stress indication",
    version="1.0",
    description=(
        "Interprets heart-rate variability during interview practice. Returns an "
        "indication of physiological pressure, NOT a diagnosis of anxiety."
    ),
)

# The gateway lives on another origin, so the browser will preflight. Origins are
# configured rather than wildcarded: this endpoint spends a real Gemini quota, and
# `*` would let any page on the internet spend it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("HRV_CORS_ORIGINS", "").split(",") if o],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """
    Reject callers without a key this service issued.

    Not optional, even during development. The Gemini quota behind this endpoint
    belongs to one person, and an open URL is an open invitation to exhaust it
    before the team has finished testing.

    When `HRV_API_KEYS` is unset the service refuses everything rather than
    allowing everything, because the failure mode of the opposite default is
    silent and expensive.
    """
    allowed = {k.strip() for k in os.getenv("HRV_API_KEYS", "").split(",") if k.strip()}
    if not allowed:
        raise HTTPException(503, "service not configured: HRV_API_KEYS is unset")
    if x_api_key not in allowed:
        raise HTTPException(401, "invalid or missing X-API-Key")


@app.get("/health")
def health() -> dict:
    """Liveness only. Says nothing about Gemini, which may be down separately."""
    return {"status": "ok"}


@app.post("/api/v1/analyze/timeline", dependencies=[Depends(require_api_key)])
def analyze_timeline(request: TimelineRequest) -> dict:
    """V1: score every 60-second window after the resting period."""
    modality = Modality(request.modality)
    try:
        prepared = prepare(request.rr_ms, request.csv, request.baseline_minutes,
                           modality, request.session_id)
        body = build_timeline(prepared, request.baseline_minutes)
    except AnalysisError as exc:
        # 422, not 500: the recording is the problem, and the message says how.
        raise HTTPException(422, str(exc)) from None

    narrative, meta = write_timeline_narrative(prepared, body, modality,
                                               request.session_id)
    return _respond(request, prepared, body, narrative, meta, modality,
                    include_duration=True)


@app.post("/api/v1/analyze/session", dependencies=[Depends(require_api_key)])
def analyze_session(request: SessionRequest) -> dict:
    """V2 and V3: score each interview question against the person's baseline."""
    modality = Modality(request.modality)
    try:
        prepared = prepare(request.rr_ms, request.csv, request.baseline_minutes,
                           modality, request.session_id)
        body, measurements = build_session(
            prepared, [q.model_dump() for q in request.questions]
        )
    except AnalysisError as exc:
        raise HTTPException(422, str(exc)) from None

    narrative, meta = write_session_narrative(prepared, body, measurements,
                                              modality, request.session_id)
    return _respond(request, prepared, body, narrative, meta, modality,
                    include_duration=False)


def _respond(request, prepared, body, narrative, meta, modality,
             include_duration: bool) -> dict:
    """
    Assemble the response, withholding the technical layer by default.

    `include_technical` has to be asked for. The rule that users never see RMSSD
    or a raw score cannot be enforced from here, so the next best thing is to make
    the compliant response the one an integrator gets without thinking about it.
    """
    from .analysis import _baseline_block

    payload = {
        "session_id": request.session_id,
        "modality": modality.value,
        "baseline": _baseline_block(prepared),
        **body,
        "narrative": narrative,
        "meta": meta,
    }
    if include_duration:
        payload["duration_sec"] = round(prepared.duration_sec, 1)

    if not request.include_technical:
        payload = _strip_technical(payload)
    return payload


#: Fields that belong to the developer view only (decision K4).
TECHNICAL_FIELDS = ("score", "delta_rmssd_pct", "delta_hr_pct", "evidence")


def _strip_technical(payload: dict) -> dict:
    """
    Remove the developer-only numbers from every per-window or per-question entry.

    `features_disagree` deliberately STAYS. It is not a measurement — it is a
    warning that the two markers pointed opposite ways, and the interface needs it
    to avoid presenting an uncertain reading as a confident one.
    """
    for key in ("timeline", "questions"):
        for entry in payload.get(key, []):
            for field in TECHNICAL_FIELDS:
                entry.pop(field, None)
    return payload
