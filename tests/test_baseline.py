"""
U1.6 — Personal baseline and reactivity.

The most important test in this file: a segment whose values match the baseline
exactly MUST yield 0% reactivity. If it does not, every reactivity figure in the
project is systematically shifted.
"""

import numpy as np
import pandas as pd
import pytest

from hrv_rag.features.baseline import BaselineProfile


@pytest.fixture
def calibration() -> pd.DataFrame:
    """
    Synthetic calibration feature table with an easily computed median.

    RMSSD = [40, 45, 50, 55, 60] -> median 50 (the middle value)
    """
    return pd.DataFrame({
        "rmssd": [40.0, 45.0, 50.0, 55.0, 60.0],
        "sdnn": [50.0, 55.0, 60.0, 65.0, 70.0],
        "mean_hr": [70.0, 70.0, 70.0, 70.0, 70.0],
    })


def test_baseline_uses_median(calibration):
    profile = BaselineProfile.from_segments("TEST", calibration)
    assert profile.values["rmssd"] == pytest.approx(50.0)


def test_median_resists_outliers(calibration):
    """
    Why the median is used instead of the mean.

    One noisy segment with RMSSD 500 ms drags the mean from 50 to 125 — a 150%
    distortion. The median only moves from 50 to 52.5, about 5%. Since every
    reactivity figure is divided by this reference, its stability determines the
    stability of every result downstream.

    The value 52.5 arises because with six data points the median is the average of
    the two middle values: (50 + 55) / 2.
    """
    dirty = pd.concat([calibration, pd.DataFrame({"rmssd": [500.0]})],
                      ignore_index=True)
    profile = BaselineProfile.from_segments("TEST", dirty)
    assert profile.values["rmssd"] == pytest.approx(52.5)
    assert dirty["rmssd"].mean() == pytest.approx(125.0)   # the mean is ruined


def test_reactivity_zero_when_equal_to_baseline(calibration):
    """THE KEY SANITY CHECK — identical values must give 0%."""
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 50.0, "sdnn": 60.0, "mean_hr": 70.0})
    assert result["delta_pct_rmssd"] == pytest.approx(0.0)
    assert result["delta_pct_sdnn"] == pytest.approx(0.0)


def test_reactivity_negative_when_lower(calibration):
    """RMSSD of 25 against a reference of 50 is a 50% drop."""
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 25.0})
    assert result["delta_pct_rmssd"] == pytest.approx(-50.0)


def test_reactivity_positive_when_higher(calibration):
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 75.0})
    assert result["delta_pct_rmssd"] == pytest.approx(50.0)


def test_reactivity_does_not_fuse_features(calibration):
    """
    The code produces reactivity PER FEATURE only — there is no combined score
    column. Fusing them is the LLM's job, working from the knowledge base. If the
    code did the fusing, the LLM would merely be reading a threshold and the RAG
    approach would lose its reason to exist.
    """
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 25.0, "sdnn": 30.0, "mean_hr": 90.0})
    assert all(k.startswith("delta_pct_") for k in result)


def test_empty_calibration_rejected():
    """
    Without calibration segments no baseline can be built, and every reactivity
    figure becomes meaningless. Failing loudly beats silently using an arbitrary
    number.
    """
    with pytest.raises(ValueError, match="no baseline can be built"):
        BaselineProfile.from_segments("TEST", pd.DataFrame())


def test_spread_flags_unsteady_baseline(calibration):
    """
    Relative IQR serves as a warning flag. On the real WESAD data, S10 produced 52%
    — far above the other subjects at 14-17% — and S10 was also the subject whose
    response pattern turned out inverted.
    """
    profile = BaselineProfile.from_segments("TEST", calibration)
    # RMSSD [40..60]: quartiles 45 and 55 -> IQR 10, reference 50 -> 20%
    assert profile.relative_spread("rmssd") == pytest.approx(0.20)


def test_nan_feature_does_not_crash(calibration):
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": np.nan})
    assert np.isnan(result["delta_pct_rmssd"])
