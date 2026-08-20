"""
responses.py — assembling what goes back over the wire.

The frontend keeps presentation helpers in `lib/` rather than inside the screens;
this is the same idea. Both endpoints answer with the same envelope, and the rule
about withholding the technical layer applies to both, so it lives once here
instead of being duplicated in two route files that could drift apart.
"""

from __future__ import annotations

from hrv_rag.core.types import Modality
from .services.analysis import Prepared, baseline_block

#: Fields that belong to the developer view only (decision K4).
TECHNICAL_FIELDS = ("score", "delta_rmssd_pct", "delta_hr_pct", "evidence")


def build_response(request, prepared: Prepared, body: dict, narrative: dict,
                   meta: dict, modality: Modality,
                   include_duration: bool) -> dict:
    """
    Assemble the response, withholding the technical layer by default.

    `include_technical` has to be asked for. The rule that users never see RMSSD
    or a raw score cannot be enforced from here, so the next best thing is to make
    the compliant response the one an integrator gets without thinking about it.
    """
    payload = {
        "session_id": request.session_id,
        "modality": modality.value,
        "baseline": baseline_block(prepared),
        **body,
        "narrative": narrative,
        "meta": meta,
    }
    if include_duration:
        payload["duration_sec"] = round(prepared.duration_sec, 1)

    if not request.include_technical:
        payload = strip_technical(payload)
    return payload


def strip_technical(payload: dict) -> dict:
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
