"""
timeline.py — V1: score every 60-second window after the resting period.

One file per endpoint, mirroring the frontend's one file per screen. The route is
deliberately thin: parse, delegate, translate failures. Everything it calls lives
in `services/`, so this file stays readable as a statement of what the endpoint
promises rather than of how the promise is kept.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from hrv_rag.core.types import Modality
from ..deps import require_api_key
from ..responses import build_response
from ..schemas import TimelineRequest
from ..services.analysis import AnalysisError, build_timeline, prepare
from ..services.narrative import write_timeline_narrative

router = APIRouter()


@router.post("/api/v1/analyze/timeline")
def analyze_timeline(request: TimelineRequest,
                     debug_scope: bool = Depends(require_api_key)) -> dict:
    """V1: score every 60-second window after the resting period."""
    modality = Modality(request.modality)
    try:
        prepared = prepare(request.rr_ms, request.csv, request.baseline_minutes,
                           modality, request.session_id,
                           request.offset_sec)
        body = build_timeline(prepared)
    except AnalysisError as exc:
        # 422, not 500: the recording is the problem, and the message says how.
        raise HTTPException(422, str(exc)) from None

    narrative, meta = write_timeline_narrative(prepared, body, modality,
                                               request.session_id)
    return build_response(request, prepared, body, narrative, meta, modality,
                          include_duration=True, debug_scope=debug_scope)
