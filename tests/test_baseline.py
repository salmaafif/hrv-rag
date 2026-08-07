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


# ----------------------------------------------- resting-phase sampling
def test_baseline_samples_the_resting_period_more_densely(make_series):
    """
    `from_series` uses the finer resting hop; `extract_features` does not.

    That split is the whole point, and getting it wrong is silent. Applying the
    finer hop inside `extract_features` looks harmless — but on WESAD the resting
    rows are ALSO the low-stress class the system is scored against, so doubling
    them doubled one side of the classification set and moved macro-F1 from 0.851
    to 0.797 without a single measurement having changed.

    Two jobs, two sampling rates: the baseline wants the steadiest central value
    it can extract from a short recording, the classification set wants segments
    as independent as the design allows.
    """
    from hrv_rag.core.types import Phase
    from hrv_rag.features.extractor import extract_features

    resting = make_series(n_beats=241, phase=Phase.CALIBRATION)   # 240 s

    table, _ = extract_features(resting)
    profile = BaselineProfile.from_series("TEST", resting)

    # 240 s: hop 30 gives 7 windows, hop 15 gives 13.
    assert len(table) == 7
    assert profile.n_segments == 13


def test_task_phase_is_not_sampled_densely(make_series):
    from hrv_rag.core.types import Phase
    from hrv_rag.features.extractor import extract_features

    table, _ = extract_features(make_series(n_beats=241, phase=Phase.QUESTION))
    assert len(table) == 7


def test_one_minute_of_rest_yields_no_baseline_at_all(make_series):
    """
    The hard floor, and the reason the resting period cannot be shortened to a
    minute however much anyone would like it to be.

    Features are computed over 60-second windows, and 60 seconds of beats spans
    only about 59 seconds — measured first beat to last, not from when the timer
    started. Nothing fits. The result is not a weaker baseline but NO baseline,
    which leaves the whole session unscoreable, because every number this system
    reports is a change relative to the person's own quiet state.

    A finer hop does not rescue it: zero windows stay zero.
    """
    from hrv_rag.core.types import Phase

    one_minute = make_series(n_beats=60, rr_value=1000.0, phase=Phase.CALIBRATION)
    with pytest.raises(ValueError, match="no baseline can be built"):
        BaselineProfile.from_series("TEST", one_minute)


def test_two_minutes_of_rest_does_yield_a_baseline(make_series):
    """Two minutes is the floor that works, and only with the finer hop."""
    from hrv_rag.core.types import Phase

    two_minutes = make_series(n_beats=120, rr_value=1000.0, phase=Phase.CALIBRATION)
    profile = BaselineProfile.from_series("TEST", two_minutes)
    assert profile.n_segments >= 2


def test_configured_resting_duration_actually_produces_a_baseline(make_series):
    """
    Guards the setting itself, not just the code that reads it.

    `SessionConfig.calibration_sec` has been shortened three times for the sake of
    the person waiting, and each cut brought it nearer the floor. Below two
    minutes it stops producing any windows at all — silently, since a shorter wait
    looks like an improvement right up until the analysis has nothing to divide
    by. This runs the configured duration through the real segmentation and fails
    if it yields nothing.
    """
    from hrv_rag.config.settings import settings
    from hrv_rag.core.types import Phase

    seconds = settings.session.calibration_sec
    resting = make_series(n_beats=seconds, rr_value=1000.0,
                          phase=Phase.CALIBRATION)

    profile = BaselineProfile.from_series("TEST", resting)
    assert profile.n_segments >= 2, (
        f"calibration_sec={seconds} yields only {profile.n_segments} window(s); "
        f"the median needs at least two to reject a noisy one"
    )
