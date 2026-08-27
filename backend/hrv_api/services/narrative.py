"""
narrative.py — the Indonesian prose, and what happens when it cannot be written.

ONE MODEL CALL PER SESSION, not one per window. That is the hybrid design: the
rule assigns the label, so the model is asked a single question about the session
as a whole rather than being consulted about every sixty seconds. It also keeps a
practice session inside a free-tier quota that a per-segment approach would empty
in a day.

EVERY FAILURE HERE IS SURVIVABLE. The numbers were already computed offline and
deterministically. So a missing API key, an exhausted quota, an unreachable model,
or a guard catching an invented figure costs the words and nothing else — the
caller still receives the measurements, and `meta.trustworthy` says whether the
prose can be shown as it stands.

That last field matters more than it looks. `trustworthy: false` does not mean the
numbers are wrong; it means the model wrote something the guards could not tie back
to what it was given, and the sentences should not be displayed unedited.
"""

from __future__ import annotations

import logging

from .analysis import Prepared
from hrv_rag.config.settings import settings
from hrv_rag.core.types import Modality
from hrv_rag.features.stress_level import RULE_VERSION

log = logging.getLogger(__name__)

#: Shown when the model could not be reached. Deliberately not an apology and not
#: an error: for the person on the other end, the measurement still succeeded.
UNAVAILABLE = (
    "Penjelasan otomatis sedang tidak tersedia. Hasil pengukuranmu di atas tetap "
    "sahih dan bisa dibaca apa adanya."
)


def _fallback_meta(reason: str) -> dict:
    return {"kb_version": "", "model": "", "trustworthy": False,
            "narrative_error": reason,
            # The rule already ran and produced every number in the response
            # before the narrative was even attempted (see module docstring),
            # so its version is known regardless of what happened here.
            # `prompt_version` names the template that WOULD have been used —
            # deterministic from config, not from a result object that does
            # not exist in this branch.
            "rule_version": RULE_VERSION,
            "prompt_version": settings.llm.narrative_prompt}


def _meta(result) -> dict:
    return {
        "kb_version": result.kb_version,
        "model": result.model,
        # False when a guard caught an invented number or a citation for a chunk
        # that was never retrieved.
        "trustworthy": result.is_trustworthy,
        # A6/§3.3, docs/ARSITEKTUR_KARIRLINK_HRV.md: reproducing a past result
        # needs the exact rule thresholds (K16, frozen — see StressRuleConfig)
        # and the exact prompt template, not just the KB and model name.
        "rule_version": RULE_VERSION,
        "prompt_version": result.prompt_name,
    }


def write_session_narrative(prepared: Prepared, body: dict, measurements: list,
                            modality: Modality, session_id: str
                            ) -> tuple[dict, dict]:
    """
    Ask the model to describe the session, then fill each question's prose.

    The per-question sentences are written in the SAME call as the summary, so the
    model sees the whole session at once. Describing each question in isolation
    would lose the comparison that makes the feedback useful — "you settled faster
    after the second one than the first" cannot be written one question at a time.
    """
    try:
        from hrv_rag.rag.narrative import NarrativeInput, NarrativeWriter
    except Exception as exc:                      # pragma: no cover - import guard
        return _empty_session(body), _fallback_meta(f"unavailable: {exc}")

    inputs = [
        NarrativeInput(
            question_no=question.number,
            question_type=question.qtype.value,
            verdict=verdict,
            reactivity=measurement.reactivity,
            recovery_pct=(measurement.recovery.percent
                          if measurement.recovery.is_computable else None),
            recovery_note=measurement.recovery.reason,
            attribution_hint=hint,
        )
        for question, measurement, verdict, hint in measurements
    ]

    summary = body["summary"]
    try:
        result = NarrativeWriter().write(
            inputs=inputs,
            session_id=session_id,
            modality=modality.value,
            device=f"{modality.value} sensor",
            signal_quality="acceptable",
            resilience=summary.get("resilience") or "not determined",
            most_triggering=summary.get("most_triggering_question"),
            recovery_summary=(
                f"median recovery {summary['median_recovery_pct']}%"
                if summary.get("median_recovery_pct") is not None
                else "recovery was not measurable"
            ),
            confounders=[],
            baseline_note=prepared.baseline_note,
        )
    except Exception as exc:
        # Quota, network, malformed JSON — all the same to the caller, who still
        # gets every number.
        log.warning("session narrative unavailable: %s", exc)
        return _empty_session(body), _fallback_meta(str(exc))

    by_number = {q.question_no: q for q in result.narrative.questions}
    for entry in body["questions"]:
        written = by_number.get(entry["number"])
        entry["penjelasan"] = written.explanation if written else UNAVAILABLE
        entry["saran"] = written.suggestion if written else ""

    return (
        {
            "ringkasan_sesi": result.narrative.session_summary,
            "penyemangat": result.narrative.encouragement,
        },
        _meta(result),
    )


def write_timeline_narrative(prepared: Prepared, body: dict, modality: Modality,
                             session_id: str) -> tuple[dict, dict]:
    """
    Describe a recording that has no question structure.

    V1 knows only that pressure rose and fell over time, so the whole recording is
    presented to the model as a single stretch rather than dressed up as questions
    it never asked. That keeps the prompt honest about what was actually observed.
    """
    try:
        from hrv_rag.features.stress_level import classify
        from hrv_rag.rag.narrative import NarrativeInput, NarrativeWriter
    except Exception as exc:                      # pragma: no cover - import guard
        return _empty_timeline(), _fallback_meta(f"unavailable: {exc}")

    summary = body["summary"]
    median = summary.get("median_reactivity_pct")
    if median is None:
        return _empty_timeline(), _fallback_meta("nothing measurable to describe")

    reactivity = {"delta_pct_rmssd": float(median)}
    overall = NarrativeInput(
        question_no=1,
        question_type="situational",
        verdict=classify(reactivity),
        reactivity=reactivity,
        recovery_pct=None,
        recovery_note="this recording has no question structure, so no quiet gap "
                      "could be isolated",
        attribution_hint="whole recording, not a single question",
    )

    try:
        result = NarrativeWriter().write(
            inputs=[overall], session_id=session_id, modality=modality.value,
            device=f"{modality.value} sensor", signal_quality="acceptable",
            resilience="not determined",
            most_triggering=summary.get("peak_minute"),
            recovery_summary="recovery was not measurable for this recording",
            confounders=[], baseline_note=prepared.baseline_note,
        )
    except Exception as exc:
        log.warning("timeline narrative unavailable: %s", exc)
        return _empty_timeline(), _fallback_meta(str(exc))

    written = result.narrative.questions[0] if result.narrative.questions else None
    return (
        {
            "ringkasan": result.narrative.session_summary,
            "rekomendasi": written.suggestion if written else "",
            "penyemangat": result.narrative.encouragement,
        },
        _meta(result),
    )


def _empty_session(body: dict) -> dict:
    for entry in body["questions"]:
        entry["penjelasan"] = UNAVAILABLE
        entry["saran"] = ""
    return {"ringkasan_sesi": UNAVAILABLE, "penyemangat": ""}


def _empty_timeline() -> dict:
    return {"ringkasan": UNAVAILABLE, "rekomendasi": "", "penyemangat": ""}
