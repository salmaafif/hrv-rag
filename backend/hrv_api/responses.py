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

#: Product tier a modality earns, per the T0/T1/T2 table in
#: docs/ARSITEKTUR_KARIRLINK_HRV.md A4 (A5: "tier ikut ke setiap keluaran").
#: T0 ("tanpa sensor") has no entry — this endpoint is never reached without a
#: modality, so a caller cannot land there through this contract at all.
#: T1/T2 exist because §4.13 of development_journey.md found PPG agrees with
#: ECG on heart rate but not on RMSSD-derived variability: a client must be
#: able to tell which surface it is allowed to render without guessing from
#: field presence, which is the whole point of carrying the tier explicitly
#: rather than leaving it implicit in `modality`.
TIER_FOR_MODALITY = {
    Modality.PPG: "T1",
    Modality.ECG: "T2",
}


def build_response(request, prepared: Prepared, body: dict, narrative: dict,
                   meta: dict, modality: Modality,
                   include_duration: bool, debug_scope: bool = False) -> dict:
    """
    Assemble the response, withholding the technical layer by default.

    `request.include_technical` alone is NOT the enforcement of decision K4 —
    it is a body flag, and any caller can set it on itself (A6,
    docs/ARSITEKTUR_KARIRLINK_HRV.md §3.1). The real gate is `debug_scope`,
    which `deps.require_api_key` derives from the CALLER's own key
    (`HRV_API_KEYS_DEBUG`) and which the caller cannot influence by anything
    it sends in the request. A careless integrator that flips
    `include_technical` on a normal key is silently ignored here rather than
    rejected, so a misconfiguration costs it nothing but the data — not a
    500 in production.
    """
    payload = {
        "session_id": request.session_id,
        "modality": modality.value,
        "tier": TIER_FOR_MODALITY[modality],
        # Instrument facts, not person facts: which features this recording
        # earned a vote for, and why. Integrators render tiers from `tier`;
        # this block is the measured justification behind it.
        "signal_fitness": prepared.signal_fitness.block(),
        "baseline": baseline_block(prepared),
        **body,
        "narrative": narrative,
        "meta": meta,
    }
    if include_duration:
        payload["duration_sec"] = round(prepared.duration_sec, 1)

    if not (request.include_technical and debug_scope):
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

    # The session-level reading carries the same developer numbers as a question
    # and must be stripped by the same rule. It is a dict rather than a list, so
    # the loop above would have walked its KEYS and silently stripped nothing —
    # a new field leaking the exact values K4 exists to withhold.
    whole = payload.get("session_level")
    if isinstance(whole, dict):
        for field in TECHNICAL_FIELDS:
            whole.pop(field, None)
    return payload
