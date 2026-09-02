"""
question.py — Aggregates segments into per-question measurements.

This is where the segment-level world meets the question-level world. Everything
here is deterministic: it selects segments, summarises them, and computes recovery
and the derived indices. No interpretation happens — that remains the LLM's job.

A question's answer window usually spans two overlapping segments. They are combined
with the MEDIAN rather than the mean, for the same reason the baseline is: a single
noisy segment should not drag the number for the whole question.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config.settings import DynamicsConfig, settings
from ..core.session import Question, QuestionType
from .baseline import BaselineProfile
from .dynamics import RecoveryResult, recovery_percent


@dataclass
class QuestionMeasurement:
    """Everything computed for one question, ready to be interpreted."""

    question: Question
    n_segments: int
    features: dict[str, float]          # median across the answer segments
    reactivity: dict[str, float]        # percent change against the baseline
    recovery: RecoveryResult
    signal_quality_pct: float           # mean outlier percentage
    notes: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.n_segments > 0


def _median_features(rows: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    """Median of each feature across a question's segments."""
    out = {}
    for col in columns:
        if col not in rows.columns:
            continue
        values = rows[col].dropna()
        if not values.empty:
            out[col] = float(values.median())
    return out


def segments_for_window(segments: pd.DataFrame, start_sec: float,
                        end_sec: float) -> pd.DataFrame:
    """
    Select segments that lie MOSTLY inside a time window.

    A segment counts when more than half of it falls within the window. With
    60-second segments sliding every 30 seconds, a segment that merely touches the
    edge of an answer is mostly made of something else — silence, or the previous
    question — so it would describe the wrong moment.

    This used to test whether the segment's MIDPOINT landed inside, which is the
    same rule everywhere except at an exact tie, and the tie is not rare: it is
    precisely what the configured session timing produces. With a 90-second answer
    followed by a 60-second gap, the segment spanning [60, 120) has its midpoint at
    90.0 — the very instant the gap begins — so it was counted as recovery data
    despite being half answer data. Recovery was then measured partly from the
    stress it was supposed to be measuring the retreat from, which understated it.
    On the reference S2 numbers that turned 53% recovery into 40%, and flipped the
    reported resilience quadrant from "responsive but flexible" to "low resilience".
    The user would have been told the opposite of what the recording showed.

    Requiring a strict majority also restores what `SessionConfig` claims: a
    60-second gap yields exactly one recovery segment, not two.

    A consequence worth stating rather than hiding: a window shorter than HALF a
    segment can never be satisfied, so it returns nothing and the caller reports
    "not computable". A 60-second measurement cannot describe a 25-second stretch,
    and this is the same reasoning that already sets `short_gap_sec` deliberately
    too short to produce a recovery figure for ordinary questions.

    CORRECTION, 1 September 2026. This paragraph used to claim the floor was 60
    seconds — "no segment can ever satisfy a window shorter than the segment
    itself". That is wrong, and wrong in the direction that matters: the test is a
    strict majority of the SEGMENT, so the real floor is 30 seconds, and a window
    of 31 seconds passes. Measured by sweeping answer lengths through the live
    pipeline: 30 s yields nothing, 31 s yields every question. The number in a
    docstring this long gets believed without being re-measured, which is exactly
    what happened.

    THE FLOOR IS NO LONGER REACHED THROUGH THIS FUNCTION for a question's
    reaction; see `reaction_window()` below. It still governs recovery, which is
    what the strict-majority rule was written for.
    """
    if segments.empty:
        return segments

    seg_start = segments["start_sec"]
    seg_end = segments["end_sec"]
    overlap = (
        np.minimum(seg_end, end_sec) - np.maximum(seg_start, start_sec)
    ).clip(lower=0.0)
    return segments[overlap > (seg_end - seg_start) / 2.0]


def reaction_window(question: Question,
                    length_sec: int | None = None) -> tuple[float, float]:
    """
    The stretch of recording a question's REACTION is read from.

    NOT the same window as the answer, and that is the whole point. Anchoring
    the measurement to when somebody stopped talking assumes their heart stopped
    with them. It does not: the cardiac response to an evaluative question peaks
    and decays over tens of seconds, so the moments just after an answer ends are
    often where the reaction is largest. Meanwhile the person is still sitting
    there and the sensor is still recording, so that stretch costs nothing to
    read.

    WHAT THIS FIXES. Measured against the live pipeline on 1 September 2026, an
    answer of 30 seconds or less produced no usable segment, and a session where
    every answer was that short produced no result at all — a 422 the interface
    then reported as the module being unavailable. Real users are far below the
    90 seconds `SessionConfig.answer_sec` assumes; the first person to run the
    integrated app finished every question inside a minute.

    THE WINDOW IS CAPPED AT THE NEXT QUESTION, never allowed to run past it. So
    it borrows the quiet gap that follows an answer, and nothing else. A short
    answer with a short gap is therefore still limited by the cycle it lives in:
    when answer plus gap is under 30 seconds there genuinely is not half a
    segment belonging to that question, and "not measurable" is the true answer
    rather than a shortfall of this code.

    RECOVERY THEN STARTS WHERE THIS ENDS, not where the answer ended — see
    `measure_question`. That is not tidiness, it is the only thing keeping the
    old contamination bug shut. Widening the reaction window into the gap means
    both windows now cover the same quiet seconds, and a single 60-second segment
    CAN hold a strict majority of each: an answer of 5 seconds followed by a
    45-second gap put segment 1 in both, measured. Handing the two windows a
    shared boundary makes them disjoint, and a 60-second segment cannot spend
    more than 30 seconds inside each of two disjoint windows, so no segment is
    ever counted twice.

    The price is stated plainly: when the answer was so short that the reaction
    had to borrow the gap, there is no gap left to measure recovery from, and
    recovery is reported as not computable. That is the truth about a
    twenty-second answer, not a shortfall.
    """
    length = length_sec or settings.segmentation.length_sec
    # Never shorter than one segment, so a brief answer still has something to
    # sit in; never longer than the answer itself when the answer was generous.
    wanted = max(question.answer_end_sec, question.answer_start_sec + length)
    horizon = (question.gap_end_sec if question.gap_end_sec is not None
               else float("inf"))
    return question.answer_start_sec, min(wanted, horizon)


def measure_question(question: Question, segments: pd.DataFrame,
                     baseline: BaselineProfile,
                     cfg: DynamicsConfig | None = None) -> QuestionMeasurement:
    """
    Compute one question's measurements from the session's segment table.

    TWO WINDOWS, TWO RULES. The reaction is read from `reaction_window()`, which
    starts when the question appeared and runs a full segment length unless the
    next question arrives first. Recovery is read from the gap after the answer,
    selected by the strict-majority rule. They cannot overlap by construction —
    see the invariant in `reaction_window()`.

    Recovery compares the answer window against the gap that follows it. When the
    gap was too short to produce a segment, recovery is reported as not computable
    rather than as zero — the two mean very different things, and conflating them
    would misrepresent the user.
    """
    cfg = cfg or settings.dynamics
    feature_names = list(baseline.values.keys())

    window_start, window_end = reaction_window(question)
    answer_rows = segments_for_window(segments, window_start, window_end)
    notes: list[str] = []

    if answer_rows.empty:
        notes.append("no segment survived the quality gates for this answer")
        return QuestionMeasurement(question, 0, {}, {},
                                   RecoveryResult(None, "no answer data"),
                                   float("nan"), notes)

    features = _median_features(answer_rows, feature_names)
    reactivity = baseline.reactivity(features)

    # --- recovery, only when a quiet window followed ---
    recovery = RecoveryResult(None, "no quiet gap followed this question")
    if question.has_recovery_window:
        # Starts at the END OF THE REACTION WINDOW, not at the end of the
        # answer. The two windows would otherwise overlap and one segment could
        # satisfy both — reintroducing exactly the contamination this file's
        # strict-majority rule was written to remove.
        gap_rows = segments_for_window(segments, window_end,
                                       question.gap_end_sec)
        if gap_rows.empty:
            recovery = RecoveryResult(None, "gap produced no usable segment")
        else:
            gap_features = _median_features(gap_rows, [cfg.primary_feature])
            key = cfg.primary_feature
            if key in features and key in gap_features and key in baseline.values:
                recovery = recovery_percent(
                    baseline=baseline.values[key],
                    stressed=features[key],
                    recovered=gap_features[key],
                    cfg=cfg,
                )

    quality = float(answer_rows["outlier_pct"].mean()) if "outlier_pct" in answer_rows else float("nan")
    if quality == quality and quality > 5.0:
        notes.append(f"{quality:.0f}% of beats were interpolated")

    return QuestionMeasurement(
        question=question,
        n_segments=len(answer_rows),
        features=features,
        reactivity=reactivity,
        recovery=recovery,
        signal_quality_pct=quality,
        notes=notes,
    )


# ===========================================================================
# DERIVED INDICES
# ===========================================================================
def arousal_index(reactivity: dict[str, float]) -> float:
    """
    How activated the body was, relative to this person's own baseline.

    BE CLEAR ABOUT WHAT THIS IS: it returns the heart-rate change unchanged. It is a
    RELABELLING, not a second measurement, and it must never be displayed beside the
    heart-rate column as though the two were independent findings — doing so would
    manufacture the appearance of corroboration where there is none.

    It exists as a named concept because "arousal" is the term the knowledge base and
    the literature use, and the prompt reads better for it. The honest framing is
    "arousal is read from heart rate", not "arousal is computed from features".

    Built from heart rate, because heart rate is the most directionally consistent
    marker in the data: it rose in all five development subjects under TSST, whereas
    RMSSD moved the expected way in only three.

    Deliberately VALENCE-NEUTRAL. Arousal says how activated someone is, not whether
    the experience was pleasant. Excitement and fear raise it equally, which is why
    this number alone can never establish that pressure was negative — the situation
    has to supply that, and here the situation is an evaluative interview.

    Returns the percentage rise in heart rate; NaN when unavailable.
    """
    hr = reactivity.get("delta_pct_mean_hr")
    return float(hr) if hr is not None and hr == hr else float("nan")


def cognitive_load_hint(question_type: QuestionType,
                        reactivity: dict[str, float]) -> tuple[float, str]:
    """
    Magnitude of the reaction, plus what the question type suggests caused it.

    An honest name for an honest limitation. The code CANNOT separate cognitive load
    from social-evaluative pressure, because their physiological signatures are the
    same. All it can do is report how large the reaction was and note what kind of
    task produced it.

    The attribution therefore travels as a hypothesis in words, never as a separate
    number that would imply a measurement was made. Returning a "cognitive load
    score" would be exactly the kind of false precision this project avoids.
    """
    rmssd = reactivity.get("delta_pct_rmssd", float("nan"))
    hr = reactivity.get("delta_pct_mean_hr", float("nan"))

    parts = [abs(v) for v in (rmssd, hr) if v == v]
    magnitude = float(np.mean(parts)) if parts else float("nan")

    if question_type.leans_cognitive:
        hint = ("a technical or numerical question, so mental effort is the more "
                "likely driver")
    elif question_type is QuestionType.SITUATIONAL:
        hint = "a situational question, so effort and self-image both plausibly apply"
    else:
        hint = ("a question about the person themselves, so social-evaluative "
                "pressure is the more likely driver")
    return magnitude, hint
