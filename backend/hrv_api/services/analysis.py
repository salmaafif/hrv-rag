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

from hrv_rag.config.settings import settings
from hrv_rag.core.session import Question, QuestionType, SessionTimeline
from hrv_rag.core.types import Modality, Phase
from hrv_rag.features.baseline import (BaselineProfile, BaselineVerdict,
                                       check_baseline)
from hrv_rag.features.extractor import extract_features
from hrv_rag.features.question import (arousal_index, cognitive_load_hint,
                                 measure_question)
from hrv_rag.features.dynamics import resilience_quadrant
from hrv_rag.features.stress_level import classify
from hrv_rag.features.signal_fitness import SignalFitness, assess_signal
from hrv_rag.preprocessing.intervals import (IntervalFormatError, parse_rr_csv,
                                       rr_series_from_intervals,
                                       split_baseline_and_task)

#: The threshold used to be redeclared here, and in `session_pipeline.py`, and in
#: two scripts — four copies of one number, none of them measured. It now lives in
#: `settings.baseline_gate` and is applied by `check_baseline`, so this service and
#: the offline pipeline cannot reach different verdicts about the same recording.


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

    #: The full judgement, kept so the response can report how much evidence the
    #: baseline stands on and not only whether it looked steady.
    baseline_verdict: BaselineVerdict = None  # type: ignore[assignment]

    #: Whether this recording's RMSSD deserves a voice in the label, decided
    #: from the signal itself (`features/signal_fitness.py`). Never from the
    #: device class: the project's own armband passed checks the WESAD wrist
    #: device failed, and sentencing it by class would have wasted it.
    signal_fitness: SignalFitness = None  # type: ignore[assignment]

    def scoring_reactivity(self, reactivity: dict) -> dict:
        """
        The reactivity the RULE is allowed to see.

        When the signal checks withheld trust in RMSSD, its delta becomes NaN
        here — the rule already reads NaN as "nothing measured" and scores
        from heart rate alone. Masked at the single point of scoring rather
        than deleted at the source, because the technical layer must keep
        REPORTING the measured value; only its vote is withdrawn.
        """
        if self.signal_fitness is None or self.signal_fitness.rmssd_trusted:
            return reactivity
        return {**reactivity, "delta_pct_rmssd": float("nan")}

    #: Where the resting period ended, measured from the first beat of the
    #: RECORDING. Not `baseline_minutes * 60`: the cut lands on a beat boundary.
    rest_end_sec: float = 0.0

    #: How much recording was already captured when the session clock reached
    #: zero. Zero for an uploaded file; non-zero whenever a Bluetooth sensor was
    #: connected before the person pressed start.
    offset_sec: float = 0.0

    @property
    def question_shift_sec(self) -> float:
        """
        Add this to a SESSION timestamp to get a TASK-TABLE timestamp.

        Three clocks meet here and only two of them ever appear in the API:

          recording : from the first beat the sensor produced
          session   : from the moment the person pressed start
          task table: from the first beat AFTER the resting period

        Callers speak in session seconds, because that is what the person's
        screen measured and what a human typing a timeline can actually observe.
        The segment table is indexed in task seconds, because segmentation runs on
        the task series alone and starts it at zero. This is the one number that
        joins them, and it is a property rather than a duplicated expression so
        the two endpoints cannot drift into disagreeing about where a question was.
        """
        return self.offset_sec - self.rest_end_sec


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
            session_id: str, offset_sec: float = 0.0) -> Prepared:
    """
    Turn a raw recording into a personal baseline plus a feature table.

    Failures here are reported as `AnalysisError` with a sentence a user could
    read, because every one of them is something they can act on: the wrong unit,
    a recording too short, a resting period too noisy to anchor anything.
    """
    intervals = _intervals_from_request(rr_ms, csv)
    rest_rr, task_rr, rest_end_sec = split_baseline_and_task(
        intervals, baseline_minutes, offset_sec
    )

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

    # The user-facing wording, never the technical one: the note travels into an
    # API response and from there onto a screen, where naming an interquartile
    # range would break the rule that a user never sees feature names (K4).
    verdict = check_baseline(baseline)

    fitness = assess_signal(rest.rr_ms, task.rr_ms, task.outlier_ratio)

    return Prepared(
        baseline=baseline, baseline_unstable=not verdict.is_acceptable,
        baseline_note=verdict.note_for_user(), baseline_verdict=verdict,
        signal_fitness=fitness,
        task_table=task_table,
        duration_sec=float(np.sum(intervals) / 1000.0),
        rest_end_sec=rest_end_sec, offset_sec=offset_sec,
    )


def baseline_block(prepared: Prepared) -> dict:
    """
    What the baseline was, and how much it is worth.

    `evidence` is reported beside `is_stable` rather than folded into it. The two
    say different things and a caller that conflates them will mislead somebody:
    `is_stable` means nothing looked wrong, `evidence` means how much was looked at.
    A baseline can be stable on four windows, and four windows is three times more
    likely to hide a bad reference than twelve.
    """
    verdict = prepared.baseline_verdict
    return {
        "rmssd_ms": round(prepared.baseline.values.get("rmssd", float("nan")), 2),
        "mean_hr_bpm": round(prepared.baseline.values.get("mean_hr", float("nan")), 1),
        "n_segments": prepared.baseline.n_segments,
        "is_stable": not prepared.baseline_unstable,
        "evidence": verdict.evidence.value,
        "warning": prepared.baseline_note or None,
    }


def _disagree(verdict) -> bool:
    return any("disagree" in line for line in verdict.evidence)


# ==================================================================== V1
def build_timeline(prepared: Prepared) -> dict:
    """
    Score every 60-second window after the resting period.

    `minute` is a display label and can be fractional, because windows advance
    every 30 seconds. `start_sec` and `end_sec` remain the authoritative fields —
    the contract says so, and rounding a half-minute away would make two distinct
    windows look like one.

    Times are reported in SESSION seconds, the same clock the caller supplies
    question timings in. This used to add `baseline_minutes * 60` to reach the
    same place, which was right only while the recording and the session started
    together — the assumption a connected Bluetooth sensor quietly breaks.
    `prepared.question_shift_sec` carries the real distance instead.
    """
    points, reactivities = [], []

    for _, row in prepared.task_table.iterrows():
        reactivity = prepared.baseline.reactivity(
            {c: row[c] for c in prepared.baseline.values if c in row}
        )
        verdict = classify(prepared.scoring_reactivity(reactivity))
        d_rmssd = reactivity.get("delta_pct_rmssd", float("nan"))
        d_hr = reactivity.get("delta_pct_mean_hr", float("nan"))

        start = float(row["start_sec"]) - prepared.question_shift_sec
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

    QUESTION TIMES ARRIVE IN SESSION SECONDS and are shifted here into the segment
    table's own clock. That shift was missing, and its absence was invisible: every
    question window landed `baseline_minutes * 60` seconds too late, so a question
    asked at 2:00 was scored from the recording at 4:00. The response stayed
    complete and well formed, the levels stayed plausible, and every one of them
    described a different moment than the one it named. Measured on a synthetic
    recording whose intervals fall steadily, the first question read 761 ms where
    the truth was 880 ms.
    """
    shift = prepared.question_shift_sec
    timeline = SessionTimeline(
        session_id="session", calibration_start_sec=0.0,
        calibration_end_sec=0.0, confounders=[],
    )
    for entry in questions:
        timeline.questions.append(Question(
            number=entry["number"], text=entry["text"],
            qtype=QuestionType(entry["type"]),
            answer_start_sec=float(entry["answer_start_sec"]) + shift,
            answer_end_sec=float(entry["answer_end_sec"]) + shift,
            # A zero-length gap means no quiet stretch was observed, which is a
            # different statement from a gap in which nothing happened. The
            # comparison stays in the caller's own clock, where it was written.
            gap_end_sec=(float(entry["gap_end_sec"]) + shift
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

        verdict = classify(prepared.scoring_reactivity(measurement.reactivity))
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
