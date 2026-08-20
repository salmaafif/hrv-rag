"""
test_session_clock.py — the three clocks, and the two bugs that lived between them.

Both bugs here were invisible from the outside: the response stayed complete, the
levels stayed plausible, and every number described a different moment than the
one it was labelled with. Nothing failed, so nothing was noticed.

  recording : from the first beat the sensor produced
  session   : from the moment the person pressed start
  task table: from the first beat AFTER the resting period

BUG 1 — the missing shift. Question times arrive in session seconds; the segment
table is indexed in task seconds. No conversion happened, so every question window
landed `baseline_minutes * 60` seconds late. A question asked at 2:00 was scored
from the recording at 4:00.

BUG 2 — the unmeasured offset. A Bluetooth sensor streams from the moment it
pairs, but `clearIntervals` was never called, so the array began at connection
while every timestamp began at start. The distance between them was unbounded and
unrecorded.

The recordings below have intervals that fall steadily with time, which turns
"which stretch was measured" into a number you can read off the answer.
"""

from __future__ import annotations

import numpy as np
import pytest

from hrv_api.services.analysis import build_session, build_timeline, prepare
from hrv_rag.core.types import Modality
from hrv_rag.preprocessing.intervals import split_baseline_and_task

REST_MS = 900.0
SLOPE_MS_PER_SEC = 1.0     # intervals fall 1 ms per second once the task starts


def ramp(duration_sec: float, start_ms: float, slope: float = 0.0,
         seed: int = 0) -> list[float]:
    """A recording whose interval length changes at a known rate."""
    rng = np.random.default_rng(seed)
    beats, t = [], 0.0
    while t < duration_sec:
        value = start_ms - slope * t + rng.normal(0, 8)
        beats.append(float(value))
        t += value / 1000.0
    return beats


def recording(rest_sec: float = 120.0, task_sec: float = 420.0,
              prelude_sec: float = 0.0) -> list[float]:
    """Prelude and rest at a steady 900 ms, then a task that falls steadily."""
    return (ramp(prelude_sec, REST_MS) + ramp(rest_sec, REST_MS, seed=1)
            + ramp(task_sec, REST_MS, SLOPE_MS_PER_SEC, seed=2))


def question(start: float, end: float, gap_end: float) -> dict:
    return {"number": 1, "text": "?", "type": "introduction",
            "answer_start_sec": start, "answer_end_sec": end,
            "gap_end_sec": gap_end, "is_difficult": False}


def measured_mean_rr(prepared, start: float, end: float) -> float:
    """
    Median meanRR of the segments a question window actually selected.

    Routed through `build_session`, NOT through a private helper that applies the
    shift itself. A first version of this file did the latter and every test still
    passed with the shift deleted — it was exercising the arithmetic it had just
    written rather than the code under test. Going through the real entry point is
    what makes these tests able to fail.
    """
    _, measurements = build_session(prepared, [question(start, end, end)])
    assert measurements, "no segment selected — the window fell off the table"
    _, measurement, _, _ = measurements[0]
    return float(measurement.features["mean_rr"])


# --------------------------------------------------------- bug 1: the shift
def test_a_question_is_scored_from_the_moment_it_names():
    # The task begins at session 120 s at 900 ms and falls 1 ms per second, so
    # the window 120-210 averages about 855 ms. Before the fix this read the
    # recording 120 s later and returned roughly 760.
    prepared = prepare(recording(), None, 2.0, Modality.ECG, "s")
    assert measured_mean_rr(prepared, 120, 210) == pytest.approx(855, abs=25)


def test_a_later_question_reads_lower_than_an_earlier_one():
    # Direction alone catches a shift that a tolerance might absorb.
    prepared = prepare(recording(), None, 2.0, Modality.ECG, "s")
    early = measured_mean_rr(prepared, 120, 210)
    late = measured_mean_rr(prepared, 360, 450)
    assert late < early - 100


def test_the_shift_is_the_resting_period_not_the_requested_minutes():
    # The cut lands on a beat boundary, so the true shift is a few hundred
    # milliseconds away from `baseline_minutes * 60`. Deriving it a second time
    # from the request would reintroduce a small, permanent error.
    prepared = prepare(recording(), None, 2.0, Modality.ECG, "s")
    assert prepared.question_shift_sec == pytest.approx(-prepared.rest_end_sec)
    assert prepared.rest_end_sec == pytest.approx(120, abs=1.5)
    assert prepared.rest_end_sec != 120.0


def test_timeline_windows_use_the_same_clock_as_question_windows():
    # V1 reported recording seconds while V2 consumed task seconds. An API whose
    # request and response disagree about the origin cannot be integrated against.
    prepared = prepare(recording(), None, 2.0, Modality.ECG, "s")
    body = build_timeline(prepared)
    first = body["timeline"][0]
    assert first["start_sec"] == pytest.approx(prepared.rest_end_sec, abs=1.0)


# -------------------------------------------------------- bug 2: the offset
def test_a_sensor_connected_early_does_not_move_the_questions():
    # THE REGRESSION TEST FOR THE LIVE PATH. Same session, same timings; the only
    # difference is three minutes of sitting still before the person pressed
    # start. The answer must not move.
    plain = prepare(recording(), None, 2.0, Modality.ECG, "s")
    early = prepare(recording(prelude_sec=180.0), None, 2.0, Modality.ECG, "s",
                    offset_sec=180.0)
    assert (measured_mean_rr(early, 120, 210)
            == pytest.approx(measured_mean_rr(plain, 120, 210), abs=25))


def test_ignoring_the_offset_is_what_moved_them():
    # Proves the previous test is not passing by luck: told nothing about the
    # prelude, the same recording reads a different stretch entirely.
    #
    # The threshold is five times the 8 ms of beat-to-beat noise these recordings
    # carry, not a round number. The measured gap is about 59 ms — smaller than a
    # first guess suggests, because a flat prelude makes the blind version land on
    # the tail of the resting period rather than somewhere wilder. Small is not
    # the same as harmless: it is a seven-sigma shift in a reading the user is
    # shown as their own.
    honest = prepare(recording(prelude_sec=180.0), None, 2.0, Modality.ECG, "s",
                     offset_sec=180.0)
    blind = prepare(recording(prelude_sec=180.0), None, 2.0, Modality.ECG, "s")
    assert abs(measured_mean_rr(blind, 120, 210)
               - measured_mean_rr(honest, 120, 210)) > 40


def test_the_prelude_is_recovered_into_the_baseline():
    # The minutes before start are resting data — the person was fitting the
    # sensor. A two-minute baseline is short enough that recovering them matters.
    without = prepare(recording(), None, 2.0, Modality.ECG, "s")
    with_prelude = prepare(recording(prelude_sec=120.0), None, 2.0,
                           Modality.ECG, "s", offset_sec=120.0)
    assert with_prelude.baseline.n_segments > without.baseline.n_segments


def test_the_prelude_may_not_outweigh_the_observed_rest():
    # It is only PROBABLY resting: nobody watched. Capping it at the length of
    # the rest that was actually asked for keeps the unverified half at fifty
    # percent, and needs no threshold of its own.
    rr = np.asarray(recording(prelude_sec=600.0))
    rest, _, _ = split_baseline_and_task(rr, baseline_minutes=2.0,
                                         offset_sec=600.0)
    assert float(np.sum(rest) / 1000.0) == pytest.approx(240, abs=10)


def test_an_upload_behaves_exactly_as_before():
    # offset_sec defaults to zero, so a file — where the recording and the
    # session start together — is unaffected by any of this.
    rr = np.asarray(recording())
    a = split_baseline_and_task(rr, 2.0)
    b = split_baseline_and_task(rr, 2.0, offset_sec=0.0)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_the_session_endpoint_survives_a_prelude(monkeypatch):
    # End to end through build_session, not only through the helper.
    prepared = prepare(recording(prelude_sec=90.0), None, 2.0, Modality.ECG, "s",
                       offset_sec=90.0)
    body, measurements = build_session(prepared, [question(120, 210, 270)])
    assert body["questions"], "the question produced no result"
    assert measurements
