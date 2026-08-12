"""
analysis.py — recording in, response out. No HTTP anywhere in this file.

Deliberately separate from `app.py` so the whole analysis can be tested without
starting a server, and so the KARIRLINK gateway is never the only way to exercise
it. Everything here is orchestration: the numbers come from `features/`, the words
come from `rag/`, and nothing new is computed.

THE ONE RULE THAT SHAPES THIS FILE. The stress label is decided by
`features/stress_level.py`, which is deterministic and runs offline. The LLM is
asked only for Indonesian prose. That means a failed model call, an exhausted
quota, or a guard catching an invented number costs the WORDS but never the
numbers — so the response degrades to a measurement without an explanation, rather
than to nothing at all. The KARIRLINK PRD asks for exactly that behaviour from an
optional module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config.settings import settings
from ..core.session import Question, QuestionType, SessionTimeline
from ..core.types import Modality, Phase
from ..features.baseline import BaselineProfile
from ..features.extractor import extract_features
from ..features.question import (arousal_index, cognitive_load_hint,
                                 measure_question)
from ..features.dynamics import resilience_quadrant
from ..features.stress_level import classify
from ..preprocessing.intervals import (IntervalFormatError, parse_rr_csv,
                                       rr_series_from_intervals,
                                       split_baseline_and_task)

#: Relative IQR above which the resting period is called unsteady.
#: Matches the threshold `SessionPipeline` already uses, so the warning the user
#: sees and the caveat the model is given are the same judgement.
UNSTABLE_BASELINE_IQR = 0.40


class AnalysisError(ValueError):
    """The recording cannot be analysed, with a reason fit to show a user."""


@dataclass
class Prepared:
    """A recording split into its resting and working halves, features computed."""

    baseline: BaselineProfile
    baseline_unstable: bool
    baseline_note: str
    task_table: pd.DataFrame
    duration_sec: float


def _intervals_from_request(rr_ms: list[float] | None, csv: str | None
                            ) -> np.ndarray:
    """
    Accept either source, and refuse politely when neither is usable.

    `rr_ms` wins when both are present, matching the frontend rule that a live
    sensor beats a previously uploaded file: it is the later, more deliberate
    choice, and its timing lines up with the interview because one clock produced
    both.
    """
    if rr_ms:
        return np.asarray(rr_ms, dtype=float)
    if csv:
        try:
            return parse_rr_csv(csv)
        except IntervalFormatError as exc:
            raise AnalysisError(str(exc)) from None
    raise AnalysisError(
        "no recording supplied: send either rr_ms or csv"
    )


def prepare(rr_ms: list[float] | None, csv: str | None,
            baseline_minutes: float, modality: Modality,
            session_id: str) -> Prepared:
    """
    Turn a raw recording into a personal baseline plus a feature table.

    Failures here are reported as `AnalysisError` with a sentence a user could
    read, because every one of them is something they can act on: the wrong unit,
    a recording too short, a resting period too noisy to anchor anything.
    """
    intervals = _intervals_from_request(rr_ms, csv)
    rest_rr, task_rr = split_baseline_and_task(intervals, baseline_minutes)

    try:
        rest = rr_series_from_intervals(rest_rr, modality, session_id,
                                        Phase.CALIBRATION)
        task = rr_series_from_intervals(task_rr, modality, session_id,
                                        Phase.QUESTION)
    except IntervalFormatError as exc:
        raise AnalysisError(str(exc)) from None

    # Densely sampled, because the resting period is short by design and the
    # median across its windows is what every later percentage divides by.
    try:
        baseline = BaselineProfile.from_series(session_id, rest)
    except ValueError:
        raise AnalysisError(
            "the resting period produced no usable window, so there is no "
            "personal reference to compare against"
        ) from None

    task_table, _ = extract_features(task)
    if task_table.empty:
        raise AnalysisError(
            "nothing after the resting period could be measured — the recording "
            "may stop there, or those minutes were too noisy"
        )

    spread = baseline.relative_spread(settings.dynamics.primary_feature)
    unstable = bool(spread == spread and spread > UNSTABLE_BASELINE_IQR)
    note = (
        f"periode tenang di awal kurang stabil (IQR relatif {spread:.0%}), "
        f"jadi angka di bawah ini kurang pasti dari biasanya"
        if unstable else ""
    )

    return Prepared(
        baseline=baseline, baseline_unstable=unstable, baseline_note=note,
        task_table=task_table,
        duration_sec=float(np.sum(intervals) / 1000.0),
    )


def _baseline_block(prepared: Prepared) -> dict:
    return {
        "rmssd_ms": round(prepared.baseline.values.get("rmssd", float("nan")), 2),
        "mean_hr_bpm": round(prepared.baseline.values.get("mean_hr", float("nan")), 1),
        "n_segments": prepared.baseline.n_segments,
        "is_stable": not prepared.baseline_unstable,
        "warning": prepared.baseline_note or None,
    }


def _disagree(verdict) -> bool:
    return any("disagree" in line for line in verdict.evidence)


# ==================================================================== V1
def build_timeline(prepared: Prepared, baseline_minutes: float) -> dict:
    """
    Score every 60-second window after the resting period.

    `minute` is a display label and can be fractional, because windows advance
    every 30 seconds. `start_sec` and `end_sec` remain the authoritative fields —
    the contract says so, and rounding a half-minute away would make two distinct
    windows look like one.
    """
    points, reactivities = [], []

    for _, row in prepared.task_table.iterrows():
        reactivity = prepared.baseline.reactivity(
            {c: row[c] for c in prepared.baseline.values if c in row}
        )
        verdict = classify(reactivity)
        d_rmssd = reactivity.get("delta_pct_rmssd", float("nan"))
        d_hr = reactivity.get("delta_pct_mean_hr", float("nan"))

        start = baseline_minutes * 60.0 + float(row["start_sec"])
        points.append({
            "minute": round(start / 60.0 + 1.0, 1),
            "start_sec": round(start, 1),
            "end_sec": round(start + settings.segmentation.length_sec, 1),
            "level": verdict.level.value,
            "score": verdict.points,
            "delta_rmssd_pct": _clean(d_rmssd),
            "delta_hr_pct": _clean(d_hr),
            "evidence": list(verdict.evidence),
            "features_disagree": _disagree(verdict),
        })
        if d_rmssd == d_rmssd:
            reactivities.append((abs(d_rmssd), points[-1]["minute"], d_rmssd))

    levels = [p["level"] for p in points]
    peak = max(reactivities, default=None)

    return {
        "timeline": points,
        "summary": {
            # The largest reaction in EITHER direction. Two of five development
            # subjects show RMSSD rising under load, and for them the signed
            # minimum would name the calmest window as the peak.
            "peak_minute": peak[1] if peak else None,
            "median_reactivity_pct": (
                round(float(np.median([r[2] for r in reactivities])), 1)
                if reactivities else None
            ),
            "count_low": levels.count("low"),
            "count_moderate": levels.count("moderate"),
            "count_high": levels.count("high"),
        },
    }


# ==================================================================== V3
def build_session(prepared: Prepared, questions: list[dict]) -> tuple[dict, list]:
    """
    Score each question against the person's own baseline.

    Returns the response body alongside the per-question measurements, so the
    caller can hand those to the narrative writer without measuring twice.
    """
    timeline = SessionTimeline(
        session_id="session", calibration_start_sec=0.0,
        calibration_end_sec=0.0, confounders=[],
    )
    for entry in questions:
        timeline.questions.append(Question(
            number=entry["number"], text=entry["text"],
            qtype=QuestionType(entry["type"]),
            answer_start_sec=float(entry["answer_start_sec"]),
            answer_end_sec=float(entry["answer_end_sec"]),
            # A zero-length gap means no quiet stretch was observed, which is a
            # different statement from a gap in which nothing happened.
            gap_end_sec=(float(entry["gap_end_sec"])
                         if entry["gap_end_sec"] > entry["answer_end_sec"]
                         else None),
            is_difficult=bool(entry.get("is_difficult", False)),
        ))

    results, measurements = [], []
    reactivities, recoveries = [], []

    for question in timeline.questions:
        measurement = measure_question(question, prepared.task_table,
                                       prepared.baseline)
        if not measurement.has_data:
            continue

        verdict = classify(measurement.reactivity)
        d_rmssd = measurement.reactivity.get("delta_pct_rmssd", float("nan"))
        d_hr = measurement.reactivity.get("delta_pct_mean_hr", float("nan"))
        _, hint = cognitive_load_hint(question.qtype, measurement.reactivity)

        results.append({
            "number": question.number,
            "text": question.text,
            "type": question.qtype.value,
            "level": verdict.level.value,
            "score": verdict.points,
            "delta_rmssd_pct": _clean(d_rmssd),
            "delta_hr_pct": _clean(d_hr),
            "recovery_pct": (round(measurement.recovery.percent, 1)
                             if measurement.recovery.is_computable else None),
            "recovery_note": ("" if measurement.recovery.is_computable
                              else measurement.recovery.reason),
            "evidence": list(verdict.evidence),
            "features_disagree": _disagree(verdict),
            # Filled in by the narrative step; left empty when it cannot run.
            "penjelasan": "",
            "saran": "",
        })
        measurements.append((question, measurement, verdict, hint))

        if d_rmssd == d_rmssd:
            reactivities.append((question.number, d_rmssd))
        if measurement.recovery.is_computable:
            recoveries.append(measurement.recovery.percent)

    if not results:
        raise AnalysisError(
            "no question had a usable window — the recording and the question "
            "timings may not line up"
        )

    median_reactivity = float(np.median([d for _, d in reactivities])) if reactivities else float("nan")
    median_recovery = float(np.median(recoveries)) if recoveries else None
    # Largest reaction in either direction, for the same reason as V1.
    most_triggering = (max(reactivities, key=lambda pair: abs(pair[1]))[0]
                       if reactivities else None)
    quadrant = resilience_quadrant(median_reactivity, median_recovery)

    body = {
        "questions": results,
        "summary": {
            "most_triggering_question": most_triggering,
            "resilience": quadrant.value if quadrant else None,
            "median_reactivity_pct": (round(median_reactivity, 1)
                                      if median_reactivity == median_reactivity
                                      else None),
            "median_recovery_pct": (round(median_recovery, 1)
                                    if median_recovery is not None else None),
        },
    }
    return body, measurements


def _clean(value: float) -> float | None:
    """
    JSON has no NaN. A missing measurement travels as null, never as zero.

    Serialising NaN would either break the parse or arrive as the string "NaN";
    turning it into 0 would claim the feature was measured and did not move.
    """
    return round(float(value), 1) if value == value else None
