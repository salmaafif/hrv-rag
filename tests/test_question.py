"""
Tests for grouping segments into questions and the derived indices.

These cover the layer that turns per-segment measurements into the per-question unit
the product actually reports on. None of it needs an API key, so it can be verified
whenever.
"""

import numpy as np
import pandas as pd
import pytest

from hrv_rag.core.session import Question, QuestionType
from hrv_rag.features.baseline import BaselineProfile
from hrv_rag.features.question import (arousal_index, cognitive_load_hint,
                                       measure_question, segments_for_window)


@pytest.fixture
def segments() -> pd.DataFrame:
    """
    Six sliding windows covering 0-180 s, advancing 30 s each.

    Midpoints land at 30, 60, 90, 120, 150 and 180 seconds.
    """
    return pd.DataFrame({
        "start_sec": [0, 30, 60, 90, 120, 150],
        "end_sec": [60, 90, 120, 150, 180, 210],
        "rmssd": [50.0, 40.0, 30.0, 28.0, 45.0, 50.0],
        "mean_hr": [70.0, 75.0, 85.0, 88.0, 74.0, 70.0],
        "outlier_pct": [1.0, 1.0, 2.0, 2.0, 1.0, 1.0],
    })


@pytest.fixture
def baseline() -> BaselineProfile:
    """Reference of RMSSD 50 ms and heart rate 70 bpm."""
    return BaselineProfile(
        subject="TEST",
        values={"rmssd": 50.0, "mean_hr": 70.0},
        spread={"rmssd": 5.0, "mean_hr": 2.0},
        n_segments=7,
    )


# ------------------------------------------------------- window selection
def test_window_selects_by_midpoint(segments):
    """
    A segment belongs to the window containing its MIDPOINT.

    Selecting by overlap instead would drag in segments that merely touch the edge
    of an answer while being mostly composed of something else.
    """
    rows = segments_for_window(segments, 45.0, 105.0)
    midpoints = ((rows["start_sec"] + rows["end_sec"]) / 2).tolist()
    assert midpoints == [60.0, 90.0]


def test_window_upper_bound_is_exclusive(segments):
    """A midpoint exactly on the upper bound belongs to the NEXT window."""
    rows = segments_for_window(segments, 0.0, 60.0)
    assert ((rows["start_sec"] + rows["end_sec"]) / 2).tolist() == [30.0]


def test_empty_window_returns_empty(segments):
    assert segments_for_window(segments, 500.0, 600.0).empty


# ---------------------------------------------------------- measurement
def test_question_uses_median_across_segments(segments, baseline):
    """
    Two answer segments (RMSSD 30 and 28) give a median of 29.

    The median is used so one noisy segment cannot distort the whole question.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=45.0, answer_end_sec=105.0)
    m = measure_question(q, segments, baseline)
    assert m.n_segments == 2
    assert m.features["rmssd"] == pytest.approx(35.0)   # median of 30 and 40


def test_reactivity_computed_against_baseline(segments, baseline):
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=75.0, answer_end_sec=135.0)
    m = measure_question(q, segments, baseline)
    # segments at midpoints 90 and 120 -> RMSSD 30 and 28 -> median 29
    assert m.features["rmssd"] == pytest.approx(29.0)
    assert m.reactivity["delta_pct_rmssd"] == pytest.approx(-42.0)


def test_recovery_computed_when_gap_exists(segments, baseline):
    """
    Answer covers midpoints 90 and 120 (RMSSD median 29), gap covers midpoint 150
    (RMSSD 45). Baseline 50, so the deviation was 21 and 16 of it returned: 76.2%.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=75.0, answer_end_sec=135.0,
                 gap_end_sec=165.0, is_difficult=True)
    m = measure_question(q, segments, baseline)
    assert m.recovery.is_computable
    assert m.recovery.percent == pytest.approx(76.19, abs=0.1)


def test_no_gap_means_recovery_not_computable(segments, baseline):
    """
    Without a gap window, recovery is NOT reported — as opposed to reported as zero.
    Zero would claim the person failed to settle, which was never measured.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=75.0, answer_end_sec=135.0)
    m = measure_question(q, segments, baseline)
    assert not m.recovery.is_computable
    assert m.recovery.percent is None


def test_question_without_usable_segments(segments, baseline):
    q = Question(number=9, text="?", qtype=QuestionType.TECHNICAL,
                 answer_start_sec=900.0, answer_end_sec=960.0)
    m = measure_question(q, segments, baseline)
    assert not m.has_data
    assert m.n_segments == 0


# ------------------------------------------------------- derived indices
def test_arousal_follows_heart_rate():
    assert arousal_index({"delta_pct_mean_hr": 18.0}) == pytest.approx(18.0)


def test_arousal_missing_is_nan():
    assert np.isnan(arousal_index({}))


def test_cognitive_hint_depends_on_question_type():
    """
    The code cannot separate mental effort from social pressure — their HRV
    signatures are identical. It only reports how big the reaction was and what kind
    of task produced it, and the attribution stays a sentence rather than a score.
    """
    reactivity = {"delta_pct_rmssd": -30.0, "delta_pct_mean_hr": 20.0}

    _, technical = cognitive_load_hint(QuestionType.TECHNICAL, reactivity)
    _, personal = cognitive_load_hint(QuestionType.INTRODUCTION, reactivity)

    assert "mental effort" in technical
    assert "social-evaluative" in personal


def test_reaction_magnitude_ignores_direction():
    """Magnitude measures how big the disturbance was, not which way it went."""
    magnitude, _ = cognitive_load_hint(
        QuestionType.TECHNICAL,
        {"delta_pct_rmssd": -30.0, "delta_pct_mean_hr": 20.0},
    )
    assert magnitude == pytest.approx(25.0)   # mean of |−30| and |20|


def test_question_type_cognitive_flags():
    assert QuestionType.TECHNICAL.leans_cognitive
    assert QuestionType.NUMERICAL.leans_cognitive
    assert not QuestionType.INTRODUCTION.leans_cognitive
    assert not QuestionType.SITUATIONAL.leans_cognitive
