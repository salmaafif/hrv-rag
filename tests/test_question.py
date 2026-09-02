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
                                       measure_question, reaction_window,
                                       segments_for_window)


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


# ------------------------------------------------- the reaction window
# `reaction_window()` exists because real KARIRLINK candidates answer in well
# under the 90 seconds `SessionConfig.answer_sec` assumes — the first person to
# run the integrated app finished every question inside a minute, and the
# module answered 422. These tests pin the window arithmetic the fix rests on.

def test_reaction_window_extends_a_short_answer_to_one_segment():
    """
    A 15-second answer is read from a full segment length of recording. The
    heart does not stop reacting when the person stops talking, and the sensor
    is still recording — so the window borrows the quiet stretch that follows.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=10.0, answer_end_sec=25.0)
    assert reaction_window(q) == (10.0, 70.0)


def test_reaction_window_is_capped_at_the_next_question():
    """The borrowed stretch is the gap and NOTHING past it — the next question's
    reaction must never leak into this one's window."""
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=10.0, answer_end_sec=25.0, gap_end_sec=50.0)
    assert reaction_window(q) == (10.0, 50.0)


def test_reaction_window_of_a_generous_answer_is_the_answer_itself():
    """
    Answers of a segment length or more keep their old window exactly, which is
    why every pre-existing test in this file still passes unchanged: the fix
    widens short windows and touches nothing else.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=10.0, answer_end_sec=100.0, gap_end_sec=160.0)
    assert reaction_window(q) == (10.0, 100.0)


def test_a_short_answer_is_now_measurable(segments, baseline):
    """
    THE FIX ITSELF. A 15-second answer used to select no segment at all (window
    shorter than half a segment), so a session of quick answers produced a 422
    the interface reported as "module unavailable". With the reaction window it
    selects the segment the answer sits in.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=60.0, answer_end_sec=75.0, gap_end_sec=180.0)

    # The old window, answer-only, still selects nothing — this line is what
    # keeps the test honest about which behaviour changed.
    assert segments_for_window(segments, 60.0, 75.0).empty

    m = measure_question(q, segments, baseline)
    assert m.has_data
    # Window [60,120) holds exactly segment [60,120): RMSSD 30 vs baseline 50.
    assert m.n_segments == 1
    assert m.reactivity["delta_pct_rmssd"] == pytest.approx(-40.0)


def test_reaction_and_recovery_windows_never_share_a_segment(segments, baseline):
    """
    The invariant that keeps the old contamination bug shut. Widening the
    reaction into the gap means both windows cover the same quiet seconds, and
    a single segment CAN hold a strict majority of each — an answer of 5 s
    followed by a 45-s gap put segment one in both, measured, before recovery
    was re-anchored. Handing the two windows a shared boundary makes them
    disjoint, and a 60-s segment cannot spend more than 30 s inside each of two
    disjoint windows.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=60.0, answer_end_sec=65.0, gap_end_sec=110.0)
    start, end = reaction_window(q)

    reaction_rows = segments_for_window(segments, start, end)
    recovery_rows = segments_for_window(segments, end, q.gap_end_sec)
    shared = set(reaction_rows["start_sec"]) & set(recovery_rows["start_sec"])
    assert shared == set()

    # The OLD recovery anchor (the answer's end) would have double-counted:
    # segment [60,120) spends 45 s in [65,110) — a strict majority — while
    # already carrying the reaction. The line above is not vacuous.
    old_rows = segments_for_window(segments, q.answer_end_sec, q.gap_end_sec)
    assert set(reaction_rows["start_sec"]) & set(old_rows["start_sec"])


def test_a_short_answer_that_borrowed_its_gap_reports_no_recovery(segments,
                                                                  baseline):
    """
    The price of the fix, stated plainly: when the reaction had to borrow the
    whole gap, there is nothing left to measure recovery from — and "not
    computable" is the truth about a five-second answer, not a shortfall.
    """
    q = Question(number=1, text="?", qtype=QuestionType.BEHAVIOURAL,
                 answer_start_sec=60.0, answer_end_sec=65.0, gap_end_sec=110.0)
    m = measure_question(q, segments, baseline)
    assert m.has_data
    assert not m.recovery.is_computable
    assert m.recovery.percent is None


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
