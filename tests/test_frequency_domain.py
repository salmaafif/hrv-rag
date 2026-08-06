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
                                               lombscargle_bands, uniform_grid,
                                               welch_bands)


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


def test_band_power_conserves_the_signal_variance():
    """
    Parseval: all the power of a pure oscillation must be recovered by the band
    that contains it. This is what makes a band power a POWER rather than a shape.

    The modulation sits at 0.05 Hz, just inside the low edge of LF, because that is
    where the failure this locks in actually shows. Band power used to be computed
    with the trapezoidal rule, which interpolates between bin CENTRES and so
    discards half a bin at each edge. At the resolution of a 60-second window
    (0.017 Hz) LF holds about six bins, so a quarter of the band went missing — and
    real HRV power piles up at exactly this low edge. Measured on S2 the loss was
    13% of LF, 8% of HF, and a 6% skew in the ratio.

    Mid-band frequencies would NOT catch it: at 0.10 and 0.25 Hz the two rules
    agree to three decimals. Only an edge-weighted spectrum separates them
    (0.999x here versus 0.916x).
    """
    rr = synth_modulated_rr(freq_hz=0.05, amplitude=50.0, duration_sec=120.0)
    result = welch_bands(rr)
    recovered = result["lf_welch"] + result["hf_welch"]
    assert recovered / np.var(rr, ddof=1) == pytest.approx(1.0, abs=0.05)


def test_resample_grid_really_has_the_rate_welch_is_told():
    """
    The grid handed to `welch` must be sampled at the rate `welch` is told about.

    Any mismatch scales the entire frequency axis by that ratio without raising
    anything. Asking `linspace` for `span * fs` points instead of `span * fs + 1`
    put the real rate at 3.98 Hz against a declared 4.0.
    """
    grid = uniform_grid(0.0, 60.0, 4.0)
    assert np.allclose(np.diff(grid), 0.25)
    assert 1.0 / (grid[1] - grid[0]) == pytest.approx(4.0)


def test_the_two_methods_agree_on_magnitude_not_just_direction():
    """
    K2 exists to compare the two methods, which requires them to be on one scale.

    Lomb-Scargle output is unitless, so it is Parseval-scaled to the signal
    variance. That scaling used to run over the 0.04-0.40 Hz slice alone while the
    variance it was matched against covered EVERY frequency, so all the power
    living outside the band was crammed into whatever sat inside it — LF came out
    2.3x the Welch value and HF 1.7x on real data.

    The signal here deliberately carries a 0.012 Hz component below the LF band.
    It has to be an oscillation rather than a drift: both methods remove a linear
    trend, so a ramp would be subtracted before it could expose anything. With
    genuine out-of-band power the old scaling inflates LF to 3.8x Welch, while
    scaling across the full analysable range holds it to about 1.0x.
    """
    t, values = 0.0, []
    while t < 180.0:
        rr = (800.0
              + 50.0 * np.sin(2.0 * np.pi * 0.10 * t)     # inside LF
              + 90.0 * np.sin(2.0 * np.pi * 0.012 * t))   # below LF
        values.append(rr)
        t += rr / 1000.0

    result = frequency_features(np.asarray(values))
    assert result["lf_ls"] == pytest.approx(result["lf_welch"], rel=0.30)


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
