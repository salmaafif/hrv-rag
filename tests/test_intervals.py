"""
Tests for the uploaded-recording entry point.

The agreed upload format carries no header and no unit marker — just a column of
numbers — because that is what heart-rate apps export. The cost of that choice is
that a file in the wrong unit is indistinguishable from a correct one by shape
alone, so the checks below are what stands between a user and a complete,
confident, entirely wrong report about their own body.

The heart-rate case is the one that matters most. Beats per minute and inter-beat
intervals are INVERSES, so reading one as the other does not merely rescale the
answer — it reverses it. A racing heart would be reported as a slow one, and rising
pressure would read as settling down.
"""

import numpy as np
import pytest

from hrv_rag.core.types import Modality, Phase
from hrv_rag.preprocessing.intervals import (IntervalFormatError,
                                             check_looks_like_milliseconds,
                                             parse_rr_csv,
                                             rr_series_from_intervals,
                                             split_baseline_and_task)


def rr(n: int = 60, value: float = 850.0) -> np.ndarray:
    """A plausible resting series: 850 ms is about 70 bpm."""
    return np.full(n, value, dtype=float)


# --------------------------------------------------------------- parsing
def test_plain_column_of_numbers():
    assert parse_rr_csv("856\n842\n871\n").tolist() == [856.0, 842.0, 871.0]


def test_header_line_is_tolerated():
    """Someone may reasonably have labelled the column before uploading."""
    assert parse_rr_csv("rr_ms\n856\n842\n").tolist() == [856.0, 842.0]


def test_blank_lines_are_ignored():
    assert parse_rr_csv("856\n\n842\n\n").tolist() == [856.0, 842.0]


def test_second_column_is_ignored():
    """A two-column export still parses; the first column is the interval."""
    assert parse_rr_csv("856,0\n842,1\n").tolist() == [856.0, 842.0]


def test_decimals_are_accepted():
    assert parse_rr_csv("856.5\n842.25\n").tolist() == [856.5, 842.25]


def test_corruption_midway_is_refused_not_skipped():
    """
    Silently dropping an unreadable line would shorten the recording without
    saying so, shifting every subsequent timestamp earlier than it really was.
    """
    with pytest.raises(IntervalFormatError, match="line 3"):
        parse_rr_csv("856\n842\nhalo\n871\n")


# ------------------------------------------------------------ unit checks
def test_milliseconds_are_accepted():
    check_looks_like_milliseconds(rr())


def test_seconds_are_refused():
    with pytest.raises(IntervalFormatError, match="SECONDS"):
        check_looks_like_milliseconds(rr(value=0.85))


def test_heart_rate_is_refused():
    """
    70 bpm is a perfectly believable number in a perfectly believable range, and
    it is the inverse of the 857 ms it represents. Nothing downstream could
    detect it, and the resulting report would be backwards yet self-consistent.
    """
    with pytest.raises(IntervalFormatError, match="HEART RATE"):
        check_looks_like_milliseconds(rr(value=70.0))


def test_implausibly_long_intervals_are_refused():
    with pytest.raises(IntervalFormatError):
        check_looks_like_milliseconds(rr(value=2500.0))


def test_a_few_artefacts_do_not_change_the_verdict():
    """The check uses a median so a handful of bad beats cannot swing it."""
    values = rr()
    values[:5] = 40.0            # dropped beats, looking like bpm
    check_looks_like_milliseconds(values)


def test_a_recording_too_short_for_one_window_is_refused():
    with pytest.raises(IntervalFormatError, match="at least 30"):
        check_looks_like_milliseconds(rr(n=12))


# ------------------------------------------------------------ conversion
def test_series_carries_the_declared_modality():
    """
    Processing is identical for both modalities here — the device already did
    peak detection — but the label still travels into the prompt so the model can
    discount an optical reading (Mandatory Rule #5).
    """
    series = rr_series_from_intervals(rr(), Modality.PPG, "me", Phase.QUESTION)
    assert series.modality is Modality.PPG


def test_quality_report_admits_no_waveform_was_seen():
    """
    Clipping and flat-line are properties of a raw signal, and there is none here.
    Reporting 0.0 would claim a check that never ran.
    """
    series = rr_series_from_intervals(rr(), Modality.ECG, "me", Phase.QUESTION)
    assert np.isnan(series.quality.clipping_ratio)
    assert np.isnan(series.quality.flatline_ratio)
    assert series.quality.notes


def test_ectopic_correction_is_applied():
    values = rr()
    values[30] = 250.0                       # below the physiological floor
    series = rr_series_from_intervals(values, Modality.ECG, "me", Phase.QUESTION)
    assert series.is_outlier[30]
    assert series.rr_ms[30] == pytest.approx(850.0)


# ----------------------------------------------------------------- split
def test_split_is_by_elapsed_time_not_beat_count():
    """
    Splitting on beats would give a fast heart a shorter resting period than a
    slow one — shrinking the very reference its reactivity is measured against.

    600 ms beats fit 100 into a minute, 1000 ms beats only 60. Both must yield one
    minute of baseline, not the same number of beats.
    """
    fast, _, _ = split_baseline_and_task(rr(300, 600.0), baseline_minutes=1.0)
    slow, _, _ = split_baseline_and_task(rr(300, 1000.0), baseline_minutes=1.0)

    assert fast.sum() == pytest.approx(60_000, abs=600)
    assert slow.sum() == pytest.approx(60_000, abs=1000)
    assert fast.size > slow.size


def test_split_returns_everything_after_the_baseline():
    rest, task, _ = split_baseline_and_task(rr(300, 1000.0), baseline_minutes=1.0)
    assert rest.size + task.size == 300
