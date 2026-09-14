"""
session.py — score each interview question against the person's baseline.

The only analysis endpoint. The app that ran the interview knows when each
question was asked, so it sends that timeline alongside the recording.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from hrv_rag.core.types import Modality
from ..deps import require_api_key
from ..responses import build_response
from ..services.archive import archive_session
from ..schemas import SessionRequest
from ..services.analysis import AnalysisError, build_session, prepare
from ..services.narrative import write_session_narrative

router = APIRouter()


@router.post("/api/v1/analyze/session")
def analyze_session(request: SessionRequest,
                    debug_scope: bool = Depends(require_api_key)) -> dict:
    """Score each interview question against the person's baseline."""
    modality = Modality(request.modality)
    try:
        prepared = prepare(
            request.rr_ms, request.csv, request.baseline_minutes,
            modality, request.session_id, request.offset_sec,
            bpm_samples=([s.model_dump() for s in request.bpm_samples]
                         if request.bpm_samples else None),
            rr_coverage=request.rr_coverage,
        )
        body, measurements = build_session(
            prepared, [q.model_dump() for q in request.questions]
        )
    except AnalysisError as exc:
        # A consented recording that FAILS analysis is still a recording — often
        # the more valuable kind, because failures are what the field metrics
        # count. One real session was lost exactly here before this line existed.
        archive_session(request.model_dump(), {"error": str(exc)})
        raise HTTPException(422, str(exc)) from None

    narrative, meta = write_session_narrative(prepared, body, measurements,
                                              modality, request.session_id)
    response = build_response(request, prepared, body, narrative, meta, modality,
                              debug_scope=debug_scope)
    # After the response is fully built, never before: the archive keeps what
    # the person was actually shown. Failure to archive never fails the call.
    archive_session(request.model_dump(), response)
    return response
