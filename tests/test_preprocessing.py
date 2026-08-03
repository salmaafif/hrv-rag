"""
U1.3 — Ectopic correction tested with deliberately injected artefacts.

Because we inject the problem beats ourselves, we know exactly which beats ought to
be flagged. That is what lets this suite prove correctness rather than merely
observe plausibility.

It also locks in the Stage 1 finding: comparing against "the last accepted interval"
made rejection cascade to 59.5%. `test_flagging_does_not_cascade` fails if that bug
ever returns.
"""

import numpy as np
import pytest

from hrv_rag.preprocessing.ecg import ECGPreprocessor


@pytest.fixture
def pre():
    """An ECG preprocessor; only ectopic correction is exercised here."""
    return ECGPreprocessor(sampling_rate=700)


def test_clean_series_flags_nothing(pre):
    """A steady 800 ms series must produce no outliers at all."""
    rr = np.full(50, 800.0)
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.sum() == 0


def test_normal_variation_not_flagged(pre):
    """
    Normal HRV changes gradually and must NOT be treated as artefact.
    Variation of about +-2.5% sits far below the 20% threshold.
    """
    rng = np.random.default_rng(42)
    rr = 800.0 + rng.normal(0, 20, size=200)      # ~2.5% spread
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.sum() == 0


def test_ectopic_beat_is_flagged(pre):
    """
    Inject one ectopic beat: 800 -> 400 -> 800.

    Beat 10 (400 ms) deviates 50% from its predecessor, and beat 11 deviates 100%
    from 400 ms. BOTH must be flagged — that is the intended behaviour, since a
    single ectopic beat normally corrupts two intervals (a short one, then a
    compensatory long one).
    """
    rr = np.full(30, 800.0)
    rr[10] = 400.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier[10]
    assert outlier[11]


def test_ectopic_value_repaired_towards_neighbours(pre):
    """After interpolation the beat that was 400 ms must return to about 800."""
    rr = np.full(30, 800.0)
    rr[10] = 400.0
    corrected, _ = pre.correct_ectopic(rr)
    assert corrected[10] == pytest.approx(800.0, abs=1.0)


def test_physiological_lower_bound(pre):
    """RR of 250 ms (240 bpm) is outside the 0.3 s bound — physiologically impossible."""
    rr = np.full(30, 800.0)
    rr[5] = 250.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier[5]


def test_physiological_upper_bound(pre):
    """RR of 2500 ms (24 bpm) is outside the 2.0 s bound."""
    rr = np.full(30, 800.0)
    rr[5] = 2500.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier[5]


def test_flagging_does_not_cascade(pre):
    """
    REGRESSION TEST for the Stage 1 bug.

    A gently rising series (+2% per beat, entirely plausible) with one artefact in
    the middle. Only a FEW beats should be flagged — those around the artefact. The
    buggy version flagged more than half the series because its reference froze.
    """
    rr = 700.0 * (1.02 ** np.arange(40))     # rising 2% per beat
    rr[20] = 300.0                            # a single artefact
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.mean() < 0.20, (
        f"too many beats flagged ({outlier.mean():.1%}) — "
        f"cascading may have returned"
    )


def test_comparison_uses_original_values(pre):
    """
    Flagging must be computed from the ORIGINAL array, never from already-corrected
    values. Otherwise the decision for beat i depends on how beat i-1 was repaired,
    which is exactly how cascading starts.

    Two distant artefacts: the number flagged must stay small.
    """
    rr = np.full(60, 800.0)
    rr[10] = 400.0
    rr[40] = 1300.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.sum() <= 4


def test_empty_series_does_not_crash(pre):
    corrected, outlier = pre.correct_ectopic(np.array([]))
    assert corrected.size == 0 and outlier.size == 0
