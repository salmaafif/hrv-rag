"""
U1.4 & U1.5 — Sliding-window segmentation and the quality gates.

The expected number of windows can be worked out by hand:

    n = floor((duration - 60) / 30) + 1

With beats of exactly 1000 ms:
    181 beats -> 180 s -> floor(120/30) + 1 = 5 windows
    121 beats -> 120 s -> floor( 60/30) + 1 = 3 windows
     61 beats ->  60 s -> floor(  0/30) + 1 = 1 window
     45 beats ->  44 s -> shorter than one window -> 0
"""

import numpy as np
import pytest

from hrv_rag.features.segmentation import segment_rr_series


@pytest.mark.parametrize("n_beats, expected", [
    (181, 5),
    (121, 3),
    (61, 1),
    (45, 0),
])
def test_window_count_matches_formula(make_series, n_beats, expected):
    result = segment_rr_series(make_series(n_beats=n_beats))
    assert result.n_kept == expected


def test_windows_advance_by_30_seconds(make_series):
    """
    Window n must start 30 seconds after the previous one, while staying 60 seconds
    long. That is what "30-second overlap" means in practice.
    """
    result = segment_rr_series(make_series(n_beats=181))
    starts = [s.start_sec for s in result.segments]
    assert np.allclose(np.diff(starts), 30.0)
    for seg in result.segments:
        assert seg.end_sec - seg.start_sec == pytest.approx(60.0)


def test_neighbouring_windows_share_data(make_series):
    """
    The consequence of overlapping that must stay visible (BACKLOG L2): neighbouring
    windows share half their data, so segments are NOT independent. This test
    documents that property rather than complaining about it.
    """
    result = segment_rr_series(make_series(n_beats=181))
    a, b = result.segments[0], result.segments[1]
    assert a.end_sec > b.start_sec          # the ranges overlap


def test_trailing_remainder_discarded(make_series):
    """
    A 175 s duration gives floor(115/30)+1 = 4 full windows, and the remaining 25
    seconds are discarded. Every segment must be a uniform 60 seconds, because HRV
    features are highly sensitive to window length.
    """
    result = segment_rr_series(make_series(n_beats=176))
    assert result.n_kept == 4
    assert result.segments[-1].end_sec <= 175.0


# ------------------------------------------------------------ quality gates
def test_too_noisy_segment_discarded(make_series):
    """
    U1.4 — segments with more than 10% outliers must be DISCARDED, not used.

    Here about 33% of beats are flagged across the whole series, so every window
    must fall and be recorded under `n_dropped_noisy`.
    """
    n = 181
    mask = np.zeros(n, dtype=bool)
    mask[::3] = True                        # ~33% outliers
    result = segment_rr_series(make_series(n_beats=n, outlier_mask=mask))
    assert result.n_kept == 0
    assert result.n_dropped_noisy == 5


def test_few_outliers_still_pass(make_series):
    """5% outliers is below the 10% threshold, so windows are kept."""
    n = 181
    mask = np.zeros(n, dtype=bool)
    mask[::20] = True                       # ~5%
    result = segment_rr_series(make_series(n_beats=n, outlier_mask=mask))
    assert result.n_kept == 5
    assert result.n_dropped_noisy == 0


def test_too_few_beats_discarded(make_series):
    """
    Beats of 2500 ms (24 bpm) give only 24 beats per 60 seconds, below the
    threshold of 30. The window must fall, because its features cannot be trusted.
    """
    result = segment_rr_series(make_series(n_beats=100, rr_value=2500.0))
    assert result.n_kept == 0
    assert result.n_dropped_short > 0


def test_window_numbers_survive_a_dropped_window(make_series):
    """
    A window's number names a MOMENT, and dropping an earlier window must not
    renumber the ones after it.

    Beats 0-9 carry outliers, which only window 1 contains, so window 1 falls at
    16.7% and windows 2-5 are untouched. Their numbers must still be 2, 3, 4, 5.

    They used to be 1, 2, 3, 4 — the rank among survivors rather than the window
    number. The same label then pointed at different moments depending on signal
    quality, which is how the ECG/PPG comparison paired segments recorded minutes
    apart, and how the assessment cache could return one window's answer when asked
    about another. `start_sec` is the cross-check: window k always starts at
    (k-1) * 30 seconds.
    """
    mask = np.zeros(181, dtype=bool)
    mask[:10] = True
    result = segment_rr_series(make_series(n_beats=181, outlier_mask=mask))

    assert result.n_dropped_noisy == 1
    assert [s.index for s in result.segments] == [2, 3, 4, 5]
    for seg in result.segments:
        assert seg.start_sec == pytest.approx((seg.index - 1) * 30.0)


def test_summary_counts_every_window(make_series):
    """n_total must cover both the kept and the discarded windows."""
    result = segment_rr_series(make_series(n_beats=181))
    assert result.n_total == (result.n_kept + result.n_dropped_short
                              + result.n_dropped_noisy)


def test_empty_series_yields_no_segments(make_series):
    result = segment_rr_series(make_series(n_beats=1))
    assert result.n_kept == 0
