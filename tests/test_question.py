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
def test_window_selects_segments_mostly_inside(segments):
    """
    A segment belongs to a window when MORE THAN HALF of it lies inside.

    Anything looser drags in segments that merely touch the edge of a window while
    being mostly composed of something else.
    """
    rows = segments_for_window(segments, 45.0, 105.0)
    assert rows["start_sec"].tolist() == [30, 60]


def test_window_rejects_segment_exactly_half_inside(segments):
    """
    An exact 50/50 split does NOT count — "half inside" is not "mostly inside".

    This is the tie the configured session timing actually produces, and treating it
    as a member is what let answer data leak into the recovery window.
    """
    # Segment [60,120) is precisely half inside [90,150).
    rows = segments_for_window(segments, 90.0, 150.0)
    assert 60 not in rows["start_sec"].tolist()
    assert rows["start_sec"].tolist() == [90]


def test_window_shorter_than_a_segment_selects_nothing(segments):
    """
    A 60-second segment cannot describe a 30-second window, so none is returned.

    The caller then reports "not computable" rather than quoting a number measured
    over the wrong span.
    """
    assert segments_for_window(segments, 90.0, 120.0).empty


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
    Answer [75,135) takes segments 60 and 90 (RMSSD 30 and 28, median 29). The gap
    is 60 s — the length `SessionConfig.recovery_gap_sec` actually schedules — and
    takes segments 120 and 150 (RMSSD 45 and 50, median 47.5).

    Baseline 50, so the deviation was 21 ms and 18.5 of it came back: 88.1%.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=75.0, answer_end_sec=135.0,
                 gap_end_sec=195.0, is_difficult=True)
    m = measure_question(q, segments, baseline)
    assert m.recovery.is_computable
    assert m.recovery.percent == pytest.approx(88.10, abs=0.1)


def test_recovery_ignores_segment_still_half_inside_the_answer(baseline):
    """
    Regression test for the contamination that flipped a user-visible verdict.

    Timing here is exactly what the real configuration produces: a 90-second answer
    followed by a 60-second gap. Segment [60,120) straddles the boundary — half
    answer, half gap — and its midpoint sits precisely on the instant the gap opens.
    Counting it as recovery drags the stressed value into the measurement it is
    supposed to be compared against, which understates how much the person settled.

    The clean gap segment alone reports 100% recovery. Including the straddler
    dropped that to 55%, which is the difference between telling someone they
    recovered fully and telling someone they barely recovered at all.
    """
    segments = pd.DataFrame({
        "start_sec": [0, 30, 60, 90],
        "end_sec": [60, 90, 120, 150],
        # Answer segments sit at 30 ms; the clean gap segment is back at baseline.
        "rmssd": [30.0, 30.0, 40.0, 50.0],
        "mean_hr": [85.0, 85.0, 78.0, 70.0],
        "outlier_pct": [1.0, 1.0, 1.0, 1.0],
    })
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=0.0, answer_end_sec=90.0,
                 gap_end_sec=150.0, is_difficult=True)
    m = measure_question(q, segments, baseline)

    assert m.recovery.is_computable
    # Only segment [90,150) counts, so recovery is (30-50)/(30-50) = 100%.
    assert m.recovery.percent == pytest.approx(100.0, abs=0.1)


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
