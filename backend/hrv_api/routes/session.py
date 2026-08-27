"""
session.py — V2 and V3: score each interview question against the baseline.

V3 is not a different analysis from V2. The only difference is where the question
timeline comes from: in V2 the person types it in, in V3 the app already knows
because it ran the interview. One endpoint therefore serves both.
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
    """V2 and V3: score each interview question against the person's baseline."""
    modality = Modality(request.modality)
    try:
        prepared = prepare(request.rr_ms, request.csv, request.baseline_minutes,
                           modality, request.session_id,
                           request.offset_sec)
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
                          include_duration=False, debug_scope=debug_scope)
    # After the response is fully built, never before: the archive keeps what
    # the person was actually shown. Failure to archive never fails the call.
    archive_session(request.model_dump(), response)
    return response
