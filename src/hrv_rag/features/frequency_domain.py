"""
frequency_domain.py — Frequency-domain HRV features, computed TWO ways.

The underlying problem: classical spectral analysis assumes evenly spaced samples,
but an RR series is not evenly spaced — the gap between samples IS the RR interval
itself (800 ms, then 750 ms, then 820 ms).

There are two ways out, and decision K2 uses both and compares them:

  (a) Welch after resampling to 4 Hz
      The RR series is first "straightened" onto a grid with one sample every
      0.25 s using cubic-spline interpolation. This is the most common and most
      citable approach. Weakness: interpolation invents values between beats, and
      those invented values contribute energy that is not in the data.

  (b) Lomb-Scargle directly on the uneven series
      Invents nothing. Weakness: less common in the HRV literature, so there are
      fewer published results to compare against.

If the two agree, that is evidence the features are robust. If they diverge
markedly, that is a finding worth discussing at the defence.

A WARNING that applies to BOTH methods: on 60-second segments the LF band
(0.04-0.15 Hz) is unstable, because a single slow LF cycle takes 25 seconds and
therefore fits only twice inside the window. Treat LF/HF as supporting evidence,
never as the deciding factor.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import lombscargle, welch

from ..config.settings import FrequencyConfig, settings

#: Names of the features produced by this module.
FREQ_FEATURES = ("lf_welch", "hf_welch", "lf_hf_welch",
                 "lf_ls", "hf_ls", "lf_hf_ls")

#: Minimum number of beats for a spectrum to be meaningful at all.
_MIN_BEATS = 20


def _beat_times(rr_ms: np.ndarray) -> np.ndarray:
    """
    Cumulative time of each beat (seconds), used as the x-axis.

    An RR series is a sequence of time differences, so the moment each beat occurs
    is the running sum of those differences.
    """
    return np.cumsum(rr_ms) / 1000.0


def _band_power(freq: np.ndarray, psd: np.ndarray,
                band: tuple[float, float]) -> float:
    """
    Power in one band = the area under the PSD curve across that range.

    Computed with the trapezoidal rule. The lower bound is inclusive and the upper
    bound exclusive, so the LF and HF bands do not both claim the point at 0.15 Hz.
    """
    lo, hi = band
    mask = (freq >= lo) & (freq < hi)
    if mask.sum() < 2:
        return float("nan")
    return float(np.trapezoid(psd[mask], freq[mask]))


def welch_bands(rr_ms: np.ndarray,
                cfg: FrequencyConfig | None = None) -> dict[str, float]:
    """
    Method (a): resample to 4 Hz, then compute a Welch periodogram.

    Why 4 Hz? The highest band of interest is HF up to 0.4 Hz. Nyquist demands at
    least 0.8 Hz; 4 Hz leaves generous headroom without wasting computation, and it
    is the customary choice in the HRV literature.

    Why cubic spline rather than linear interpolation? The HRV signal varies
    smoothly. Linear interpolation introduces a sharp corner at every beat, and
    those corners inject spurious energy at high frequencies — precisely the HF
    band being measured.

    Note: `nperseg` is set to the full data length (a single window). Splitting
    60 seconds into sub-windows would reduce variance but degrade frequency
    resolution until the LF band was no longer represented. For segments this
    short, resolution is the more valuable property.
    """
    cfg = cfg or settings.frequency
    if rr_ms.size < _MIN_BEATS:
        return {"lf_welch": np.nan, "hf_welch": np.nan, "lf_hf_welch": np.nan}

    t = _beat_times(rr_ms)

    # Uniform time grid spanning the data.
    n_samples = int((t[-1] - t[0]) * cfg.resample_hz)
    if n_samples < 8:
        return {"lf_welch": np.nan, "hf_welch": np.nan, "lf_hf_welch": np.nan}
    t_uniform = np.linspace(t[0], t[-1], n_samples)

    rr_uniform = CubicSpline(t, rr_ms)(t_uniform)

    # detrend="linear" removes a straight-line trend (for example RR lengthening
    # gradually across the segment). Without it, that trend appears as spurious
    # energy at very low frequencies and contaminates the LF band.
    freq, psd = welch(
        rr_uniform, fs=cfg.resample_hz,
        nperseg=len(rr_uniform), detrend="linear",
    )

    lf = _band_power(freq, psd, cfg.lf_band)
    hf = _band_power(freq, psd, cfg.hf_band)
    return {
        "lf_welch": lf,
        "hf_welch": hf,
        "lf_hf_welch": lf / hf if hf and hf > 0 else np.nan,
    }


def lombscargle_bands(rr_ms: np.ndarray,
                      cfg: FrequencyConfig | None = None) -> dict[str, float]:
    """
    Method (b): Lomb-Scargle periodogram, computed directly on uneven samples.

    Lomb-Scargle fits sine and cosine waves to the data at each trial frequency
    without caring whether the samples are evenly spaced. That is precisely why no
    interpolation is required.

    About the units: the raw output of `scipy.signal.lombscargle` is not on the same
    ms^2/Hz scale as Welch. A Parseval scaling is applied here — the whole spectrum
    is scaled so its total power equals the variance of the RR series. That makes LF
    and HF power comparable between the two methods. The LF/HF ratio itself is
    unaffected by any scaling.
    """
    cfg = cfg or settings.frequency
    nan = {"lf_ls": np.nan, "hf_ls": np.nan, "lf_hf_ls": np.nan}
    if rr_ms.size < _MIN_BEATS:
        return nan

    t = _beat_times(rr_ms)
    x = rr_ms - np.mean(rr_ms)          # remove the DC component
    if np.allclose(x, 0):
        return nan

    # Dense frequency grid spanning the bands of interest.
    freq = np.linspace(cfg.lf_band[0], cfg.hf_band[1], 512)
    pgram = lombscargle(t, x, 2.0 * np.pi * freq, precenter=True)

    # Parseval scaling: force the total area to equal the signal variance.
    area = np.trapezoid(pgram, freq)
    if area <= 0:
        return nan
    psd = pgram * (np.var(x, ddof=1) / area)

    lf = _band_power(freq, psd, cfg.lf_band)
    hf = _band_power(freq, psd, cfg.hf_band)
    return {
        "lf_ls": lf,
        "hf_ls": hf,
        "lf_hf_ls": lf / hf if hf and hf > 0 else np.nan,
    }


def frequency_features(rr_ms: np.ndarray,
                       cfg: FrequencyConfig | None = None) -> dict[str, float]:
    """Compute both methods for one segment."""
    return {**welch_bands(rr_ms, cfg), **lombscargle_bands(rr_ms, cfg)}
