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
    Select segments whose midpoint falls inside a time window.

    The MIDPOINT is used rather than the start or the end. With 60-second windows
    sliding every 30 seconds, a segment that merely touches the edge of an answer
    is mostly made of something else — silence, or the previous question. Requiring
    the midpoint to land inside means the segment is genuinely dominated by the
    window it is assigned to.
    """
    if segments.empty:
        return segments
    midpoint = (segments["start_sec"] + segments["end_sec"]) / 2.0
    return segments[(midpoint >= start_sec) & (midpoint < end_sec)]


def measure_question(question: Question, segments: pd.DataFrame,
                     baseline: BaselineProfile,
                     cfg: DynamicsConfig | None = None) -> QuestionMeasurement:
    """
    Compute one question's measurements from the session's segment table.

    Recovery compares the answer window against the gap that follows it. When the
    gap was too short to produce a segment, recovery is reported as not computable
    rather than as zero — the two mean very different things, and conflating them
    would misrepresent the user.
    """
    cfg = cfg or settings.dynamics
    feature_names = list(baseline.values.keys())

    answer_rows = segments_for_window(segments, question.answer_start_sec,
                                      question.answer_end_sec)
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
        gap_rows = segments_for_window(segments, question.answer_end_sec,
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
