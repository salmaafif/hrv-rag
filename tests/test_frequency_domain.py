"""
U1.2 — Frequency-domain features tested with synthetic signals of known frequency.

The idea: if an RR series is deliberately made to oscillate at 0.25 Hz, its
spectral power MUST land in the HF band (0.15-0.40 Hz), not in LF. Likewise a
0.10 Hz oscillation must land in the LF band (0.04-0.15 Hz).

This proves the code correct without comparing against another library — the truth
comes from signal physics we control ourselves.

Both methods (Welch and Lomb-Scargle) face the same criteria, because they must
agree on something this basic. If either failed here, the K2 comparison would be
meaningless.
"""

import numpy as np
import pytest

from conftest import synth_modulated_rr
from hrv_rag.features.frequency_domain import (frequency_features,
                                               lombscargle_bands, welch_bands)


@pytest.fixture(scope="module")
def rr_hf():
    """RR series oscillating at 0.25 Hz — the heart of the HF band."""
    return synth_modulated_rr(freq_hz=0.25)


@pytest.fixture(scope="module")
def rr_lf():
    """RR series oscillating at 0.10 Hz — the heart of the LF band."""
    return synth_modulated_rr(freq_hz=0.10)


# ----------------------------------------------------------------- Welch
def test_welch_places_025hz_in_hf_band(rr_hf):
    result = welch_bands(rr_hf)
    assert result["hf_welch"] > result["lf_welch"]
    assert result["lf_hf_welch"] < 1.0


def test_welch_places_010hz_in_lf_band(rr_lf):
    result = welch_bands(rr_lf)
    assert result["lf_welch"] > result["hf_welch"]
    assert result["lf_hf_welch"] > 1.0


# ---------------------------------------------------------- Lomb-Scargle
def test_lombscargle_places_025hz_in_hf_band(rr_hf):
    result = lombscargle_bands(rr_hf)
    assert result["hf_ls"] > result["lf_ls"]
    assert result["lf_hf_ls"] < 1.0


def test_lombscargle_places_010hz_in_lf_band(rr_lf):
    result = lombscargle_bands(rr_lf)
    assert result["lf_ls"] > result["hf_ls"]
    assert result["lf_hf_ls"] > 1.0


# ----------------------------------------------------------- both methods
def test_both_methods_agree_on_direction(rr_hf, rr_lf):
    """
    They may differ in magnitude (~37% was observed on the WESAD data), but they
    must NOT differ in direction. If one says HF dominates and the other says LF,
    something is broken.
    """
    for rr in (rr_hf, rr_lf):
        result = frequency_features(rr)
        welch_hf_dominant = result["lf_hf_welch"] < 1.0
        ls_hf_dominant = result["lf_hf_ls"] < 1.0
        assert welch_hf_dominant == ls_hf_dominant


def test_too_short_segment_returns_nan():
    """
    A very short series cannot yield a meaningful spectrum.

    What comes back MUST be NaN, not 0. A zero would read as "there is no LF power"
    — a measurement — when the truth is "this could not be measured". Keeping the
    two apart is what stops bad segments from quietly entering the metrics.
    """
    result = frequency_features(np.full(5, 800.0))
    assert all(np.isnan(v) for v in result.values())


def test_flat_series_does_not_crash():
    """A series with no variation at all must not raise."""
    result = frequency_features(np.full(60, 800.0))
    assert set(result) == {"lf_welch", "hf_welch", "lf_hf_welch",
                           "lf_ls", "hf_ls", "lf_hf_ls"}
