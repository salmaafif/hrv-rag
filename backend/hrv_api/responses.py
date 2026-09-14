"""
responses.py — assembling what goes back over the wire.

The frontend keeps presentation helpers in `lib/` rather than inside the screens;
this is the same idea. The envelope and the rule about withholding the technical
layer live here rather than in the route, so the route stays a statement of what
the endpoint promises.
"""

from __future__ import annotations

from hrv_rag.core.types import Modality
from .services.analysis import BPM, Prepared, baseline_block

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

#: Tier of a session scored from heart rate alone, whatever its modality.
#:
#: A value of its own rather than "T1". A beat-interval armband session is T1 and
#: can still earn RMSSD a vote when its signal passes the checks; this tier never
#: measures variability, recovery, or the resilience quadrant at all. Reusing T1
#: would also change what every archived T1 session means.
TIER_HEART_RATE_ONLY = "T1-BPM"


def tier_for(prepared: Prepared, modality: Modality) -> str:
    """The product surface this session may render."""
    if prepared.source == BPM:
        return TIER_HEART_RATE_ONLY
    return TIER_FOR_MODALITY[modality]


def build_response(request, prepared: Prepared, body: dict, narrative: dict,
                   meta: dict, modality: Modality,
                   debug_scope: bool = False) -> dict:
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
        "tier": tier_for(prepared, modality),
        # Which path produced the numbers: "beat_intervals" or "bpm".
        "source": prepared.source,
        # Instrument facts, not person facts: which features this recording
        # earned a vote for, and why. Integrators render tiers from `tier`;
        # this block is the measured justification behind it.
        "signal_fitness": prepared.signal_fitness.block(),
        "baseline": baseline_block(prepared),
        **body,
        "narrative": narrative,
        "meta": meta,
    }
    if not (request.include_technical and debug_scope):
        payload = strip_technical(payload)
    return payload


def strip_technical(payload: dict) -> dict:
    """
    Remove the developer-only numbers from every per-question entry.

    `features_disagree` deliberately STAYS. It is not a measurement — it is a
    warning that the two markers pointed opposite ways, and the interface needs it
    to avoid presenting an uncertain reading as a confident one.
    """
    for entry in payload.get("questions", []):
        for field in TECHNICAL_FIELDS:
            entry.pop(field, None)

    # The session-level reading carries the same developer numbers as a question
    # and must be stripped by the same rule. It is a dict rather than a list, so
    # a loop written for the questions would have walked its KEYS and silently
    # stripped nothing — leaking the exact values users must never be shown.
    whole = payload.get("session_level")
    if isinstance(whole, dict):
        for field in TECHNICAL_FIELDS:
            whole.pop(field, None)
    return payload
