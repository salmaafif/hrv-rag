"""
Tests for the ECG-versus-PPG agreement statistics.

These functions produced the modality comparison figures reported in the thesis —
the ICC of +0.986 for heart rate and +0.109 for RMSSD, and the +95 ms bias. Those
numbers are quoted as evidence that wrist optical sensing cannot carry RMSSD, so
they have to be right for reasons stronger than "the code ran".

Every case below has an answer that can be worked out by hand or reasoned from the
definition, rather than read off whatever the implementation currently returns.
The most important ones are the DISAGREEMENT cases: a correlation-shaped statistic
that quietly ignores a constant offset would report excellent agreement between a
sensor and the same sensor plus 95 ms, which is exactly the failure being measured.
"""

import numpy as np
import pytest

from hrv_rag.evaluation.modality import (bland_altman, compare_feature,
                                         icc_two_way_agreement, label_agreement)

RESTING_RMSSD = np.array([40.0, 45.0, 38.0, 52.0, 47.0, 41.0, 55.0, 43.0])


# ------------------------------------------------------------------- ICC
def test_identical_measurements_agree_perfectly():
    assert icc_two_way_agreement(RESTING_RMSSD, RESTING_RMSSD) == pytest.approx(1.0)


def test_a_constant_offset_destroys_agreement():
    """
    The property the whole modality comparison rests on.

    ICC(2,1) measures ABSOLUTE agreement, not consistency. A device reading a
    steady 95 ms too high tracks the reference perfectly — Pearson r stays at
    1.0 — while being useless for a threshold expressed in milliseconds. Had
    consistency been used instead, wrist PPG would have looked excellent.
    """
    shifted = RESTING_RMSSD + 95.0
    assert np.corrcoef(RESTING_RMSSD, shifted)[0, 1] == pytest.approx(1.0)
    assert icc_two_way_agreement(RESTING_RMSSD, shifted) < 0.3


def test_a_small_offset_is_tolerated_better_than_a_large_one():
    close = icc_two_way_agreement(RESTING_RMSSD, RESTING_RMSSD + 2.0)
    far = icc_two_way_agreement(RESTING_RMSSD, RESTING_RMSSD + 40.0)
    assert close > far


def test_unrelated_measurements_do_not_agree():
    rng = np.random.default_rng(0)
    noise = rng.normal(45.0, 12.0, RESTING_RMSSD.size)
    assert icc_two_way_agreement(RESTING_RMSSD, noise) < 0.5


def test_too_few_pairs_is_not_computable():
    """
    One pair cannot support a variance estimate. Returning a number anyway would
    put an agreement figure in a report that was never measured.
    """
    assert np.isnan(icc_two_way_agreement(np.array([40.0]), np.array([41.0])))


def test_incomplete_pairs_are_the_caller_s_job_not_this_function_s():
    """
    Pins WHERE missing data is handled, because it is handled in exactly one
    place and that is easy to forget.

    `icc_two_way_agreement` assumes clean input and returns NaN if it does not get
    it — no silent imputation, no quietly shrinking the sample. `compare_feature`
    is the entry point that drops incomplete pairs first, which is why every
    reported figure comes with the pair count it was actually computed from.

    Written down as a test because a future caller reaching past `compare_feature`
    — a notebook, or the backend — would otherwise get NaN with no clue why.
    """
    x = np.array([40.0, 45.0, np.nan, 52.0, 47.0])
    y = np.array([41.0, 44.0, 50.0, np.nan, 46.0])

    assert np.isnan(icc_two_way_agreement(x, y))

    # Through the entry point, the same data yields a real figure from 3 pairs.
    report = compare_feature(x, y, "rmssd")
    assert report.n_pairs == 3
    assert not np.isnan(report.icc)


# --------------------------------------------------------- Bland-Altman
def test_bias_is_the_mean_difference_second_minus_first():
    """
    Sign matters for reporting: the thesis states PPG reads +95 ms ABOVE ECG, so
    the second argument minus the first. Reversed, the same finding would read as
    the wrist under-reporting.
    """
    bias, _, _, _ = bland_altman(RESTING_RMSSD, RESTING_RMSSD + 10.0)
    assert bias == pytest.approx(10.0)

    bias_reversed, _, _, _ = bland_altman(RESTING_RMSSD + 10.0, RESTING_RMSSD)
    assert bias_reversed == pytest.approx(-10.0)


def test_limits_of_agreement_are_bias_plus_or_minus_1_96_sd():
    x = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    y = np.array([12.0, 21.0, 33.0, 41.0, 54.0])   # differences 2, 1, 3, 1, 4
    differences = y - x

    bias, lower, upper, _ = bland_altman(x, y)
    expected_sd = float(np.std(differences, ddof=1))

    assert bias == pytest.approx(float(np.mean(differences)))
    assert lower == pytest.approx(bias - 1.96 * expected_sd)
    assert upper == pytest.approx(bias + 1.96 * expected_sd)


def test_a_constant_offset_shows_no_proportional_bias():
    _, _, _, slope = bland_altman(RESTING_RMSSD, RESTING_RMSSD + 10.0)
    assert slope == pytest.approx(0.0, abs=1e-6)


def test_a_scaling_error_shows_as_proportional_bias():
    """
    A sensor reading 20% high has a difference that grows with the value. That is
    a different defect from a constant offset and needs a different fix, so the
    slope has to separate them.
    """
    _, _, _, slope = bland_altman(RESTING_RMSSD, RESTING_RMSSD * 1.2)
    assert slope > 0.1


# ----------------------------------------------------------- the report
def test_report_carries_the_pair_count_it_was_computed_from():
    report = compare_feature(RESTING_RMSSD, RESTING_RMSSD + 5.0, "rmssd")
    assert report.feature == "rmssd"
    assert report.n_pairs == RESTING_RMSSD.size


def test_report_counts_only_usable_pairs():
    # Quoting an agreement figure alongside an inflated n would overstate how
    # much evidence is behind it.
    x = np.array([40.0, 45.0, np.nan, 52.0])
    y = np.array([41.0, 44.0, 50.0, 53.0])
    assert compare_feature(x, y, "rmssd").n_pairs == 3


# -------------------------------------------------------- label agreement
def test_label_agreement_is_the_fraction_that_match():
    ecg = ["low", "high", "moderate", "high"]
    ppg = ["low", "high", "low", "high"]
    assert label_agreement(ecg, ppg) == pytest.approx(0.75)


def test_total_disagreement_scores_zero():
    assert label_agreement(["low", "low"], ["high", "high"]) == pytest.approx(0.0)


def test_no_labels_is_not_reported_as_perfect_agreement():
    """
    An empty comparison must not come back as 1.0. Two modalities that produced
    nothing agreed about nothing.
    """
    result = label_agreement([], [])
    assert result == 0.0 or np.isnan(result)
