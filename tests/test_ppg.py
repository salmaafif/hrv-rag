"""
Tests for the PPG branch — the optical modality.

This file existed as a gap for a long time, and the gap was demonstrated rather
than assumed: replacing the bandpass filter with a BANDSTOP left the whole suite
green. A filter inverted that way removes the pulse and keeps the noise, and every
number downstream would still have arrived looking like a plausible heart rate.

Three things genuinely differ from the ECG branch, and each is checked here:

  - the passband stops at 8 Hz instead of 40, because a pulse waveform has no
    sharp QRS-like edge and everything above that is noise;
  - peaks are systolic rather than R peaks, so their timing is inherently
    softer — which is why PRV is not simply HRV measured somewhere else;
  - beats recorded during arm movement are rejected, using acceleration, since
    optical sensing is dominated by motion artefact.

No dataset is needed. The signals are synthesised so the right answer is known
before the code runs.
"""

import numpy as np
import pytest

from hrv_rag.core.types import Modality
from hrv_rag.preprocessing.ppg import PPGPreprocessor

FS = 64          # WESAD wrist BVP rate, and typical for optical sensors
SECONDS = 30


def pulse_wave(bpm: float = 70.0, fs: int = FS, seconds: int = SECONDS,
               noise_hz: float | None = None) -> np.ndarray:
    """
    A crude but honest stand-in for a photoplethysmogram.

    The fundamental plus one harmonic gives the asymmetric, rounded shape of a
    real pulse without pretending to model haemodynamics. What matters for these
    tests is that the energy sits where a pulse's energy sits.
    """
    t = np.arange(0, seconds, 1 / fs)
    f = bpm / 60.0
    wave = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    if noise_hz is not None:
        wave = wave + 0.8 * np.sin(2 * np.pi * noise_hz * t)
    return wave


def band_power(signal: np.ndarray, low: float, high: float,
               fs: int = FS) -> float:
    """Energy in one frequency band, via the periodogram."""
    spectrum = np.abs(np.fft.rfft(signal)) ** 2
    freqs = np.fft.rfftfreq(signal.size, 1 / fs)
    return float(spectrum[(freqs >= low) & (freqs < high)].sum())


# ------------------------------------------------------------------ filter
def test_the_pulse_survives_the_filter():
    """
    The most basic property, and the one whose absence hid for so long: whatever
    comes out must still contain the heartbeat.
    """
    pre = PPGPreprocessor(sampling_rate=FS)
    raw = pulse_wave(bpm=70)
    filtered = pre.filter_signal(raw)

    # 70 bpm is 1.17 Hz.
    assert band_power(filtered, 0.8, 2.0) > 0.5 * band_power(raw, 0.8, 2.0)


def test_high_frequency_noise_is_removed():
    """
    A 20 Hz component is far above anything a pulse produces. The ECG branch
    would pass it — its band reaches 40 Hz — which is precisely why the two
    modalities cannot share one filter.
    """
    pre = PPGPreprocessor(sampling_rate=FS)
    raw = pulse_wave(bpm=70, noise_hz=20.0)
    filtered = pre.filter_signal(raw)

    assert band_power(filtered, 18.0, 22.0) < 0.01 * band_power(raw, 18.0, 22.0)


def test_slow_drift_is_removed():
    """
    Baseline wander from breathing and skin contact sits below 0.5 Hz. Left in, it
    dominates the signal and drags peak detection off the pulse.
    """
    pre = PPGPreprocessor(sampling_rate=FS)
    t = np.arange(0, SECONDS, 1 / FS)
    drift = 5.0 * np.sin(2 * np.pi * 0.05 * t)
    filtered = pre.filter_signal(pulse_wave() + drift)

    assert band_power(filtered, 0.0, 0.2) < 0.05 * band_power(pulse_wave() + drift,
                                                              0.0, 0.2)


def test_the_filter_passes_the_band_rather_than_blocking_it():
    """
    Guards against the inversion that the suite once missed entirely.

    A bandstop with the same edges would strip the pulse and keep everything
    else — so the test compares the two regions directly rather than checking
    either in isolation.
    """
    pre = PPGPreprocessor(sampling_rate=FS)
    raw = pulse_wave(bpm=70, noise_hz=20.0)
    filtered = pre.filter_signal(raw)

    inside = band_power(filtered, 0.8, 2.0)
    outside = band_power(filtered, 18.0, 22.0)
    assert inside > 100 * outside


# ------------------------------------------------------------ peak detection
def test_peaks_are_found_at_roughly_the_right_rate():
    pre = PPGPreprocessor(sampling_rate=FS)
    peaks = pre.detect_peaks(pre.filter_signal(pulse_wave(bpm=70, seconds=60)))

    # 60 seconds at 70 bpm is about 70 beats; detection is never exact.
    assert 55 < peaks.size < 85


def test_intervals_derived_from_those_peaks_are_physiological():
    pre = PPGPreprocessor(sampling_rate=FS)
    peaks = pre.detect_peaks(pre.filter_signal(pulse_wave(bpm=70, seconds=60)))
    rr_ms, _ = pre.peaks_to_intervals(peaks)

    assert np.median(rr_ms) == pytest.approx(857, rel=0.15)


def test_the_branch_declares_itself_as_ppg():
    """
    The modality travels all the way into the prompt so the model can weigh an
    optical reading more cautiously. Mislabelling it would raise confidence on
    exactly the signal that deserves less.
    """
    assert PPGPreprocessor(sampling_rate=FS).modality is Modality.PPG


# ------------------------------------------------- motion artefact rejection
def steady_arm(n: int) -> np.ndarray:
    """A raised, motionless arm: constant acceleration from gravity alone."""
    return np.tile(np.array([0.0, 0.0, 9.81]), (n, 1))


def test_a_motionless_raised_arm_is_not_mistaken_for_movement():
    """
    The reason movement is measured as the CHANGE in acceleration rather than its
    magnitude. Gravity contributes a constant to any static posture, so a raw
    magnitude would reject every beat from someone simply holding their arm up.
    """
    signal = pulse_wave(seconds=20)
    pre = PPGPreprocessor(sampling_rate=FS, accelerometer=steady_arm(signal.size))

    peaks = pre.detect_peaks(pre.filter_signal(signal))
    unfiltered = PPGPreprocessor(sampling_rate=FS).detect_peaks(
        pre.filter_signal(signal)
    )
    assert peaks.size == unfiltered.size


def test_beats_during_a_burst_of_movement_are_dropped():
    signal = pulse_wave(seconds=20)
    acc = steady_arm(signal.size)
    # Shake the arm for two seconds in the middle.
    shake = np.arange(8 * FS, 10 * FS)
    acc[shake, 0] = 6.0 * np.sin(np.arange(shake.size) * 1.5)

    moving = PPGPreprocessor(sampling_rate=FS, accelerometer=acc)
    still = PPGPreprocessor(sampling_rate=FS, accelerometer=steady_arm(signal.size))

    filtered = moving.filter_signal(signal)
    assert moving.detect_peaks(filtered).size < still.detect_peaks(filtered).size


def test_rejected_beats_are_the_ones_inside_the_movement():
    """
    Dropping the right COUNT is not enough; they have to be the right beats.
    Rejecting beats from a quiet stretch would remove good data and leave the
    corrupted stretch in place.
    """
    signal = pulse_wave(seconds=20)
    acc = steady_arm(signal.size)
    shake = np.arange(8 * FS, 10 * FS)
    acc[shake, 0] = 6.0 * np.sin(np.arange(shake.size) * 1.5)

    pre = PPGPreprocessor(sampling_rate=FS, accelerometer=acc)
    filtered = pre.filter_signal(signal)
    kept = pre.detect_peaks(filtered)
    all_peaks = PPGPreprocessor(sampling_rate=FS).detect_peaks(filtered)

    dropped = set(all_peaks.tolist()) - set(kept.tolist())
    assert dropped, "the shake should have cost at least one beat"
    for index in dropped:
        # Allow the smoothing window to spill either side of the burst.
        assert 7.5 * FS <= index <= 10.5 * FS


def test_no_accelerometer_means_no_rejection():
    """
    Absent movement data is not evidence of stillness. Rejecting nothing is the
    honest response; inventing a motion estimate would silently discard beats.
    """
    signal = pulse_wave(seconds=20)
    pre = PPGPreprocessor(sampling_rate=FS)
    filtered = pre.filter_signal(signal)
    assert pre.detect_peaks(filtered).size > 0


def test_perfectly_constant_acceleration_does_not_divide_by_zero():
    # Spread of exactly zero appears with synthetic or stuck-sensor data.
    signal = pulse_wave(seconds=10)
    pre = PPGPreprocessor(sampling_rate=FS,
                          accelerometer=np.zeros((signal.size, 3)))
    assert pre.detect_peaks(pre.filter_signal(signal)).size > 0


def test_a_shorter_accelerometer_channel_does_not_read_past_its_end():
    """
    Peak indices come from the pulse signal, and acceleration is recorded on its
    own clock — 32 Hz against 64 Hz in WESAD — so after resampling the last beats
    can fall beyond the end of the acceleration channel.

    The channel here is cut short by a full second so that several peaks really
    do land past it. Trimming by a sample or two, as an earlier version of this
    test did, left the boundary untouched and the guard untested.
    """
    signal = pulse_wave(seconds=10)

    # The channel must also VARY. A perfectly rigid arm gives zero spread, and
    # the mask returns early before it ever indexes anything — which is how an
    # earlier version of this test passed while leaving the boundary untouched.
    rng = np.random.default_rng(1)
    short = steady_arm(signal.size - FS)          # one second short
    short[:, 0] += rng.normal(0, 0.05, short.shape[0])

    pre = PPGPreprocessor(sampling_rate=FS, accelerometer=short)
    filtered = pre.filter_signal(signal)
    all_peaks = PPGPreprocessor(sampling_rate=FS).detect_peaks(filtered)

    assert all_peaks.max() >= short.shape[0], (
        "the fixture must produce peaks beyond the accelerometer, or the "
        "boundary this test exists for is never reached"
    )
    assert float(np.std(short[:, 0])) > 0, (
        "the fixture must have some movement, or the mask exits before indexing"
    )

    # Must not raise. Judging a beat against whatever memory follows the array
    # would be worse than crashing, because it would quietly succeed.
    assert pre.detect_peaks(filtered).size > 0


def test_a_stricter_threshold_rejects_more():
    """
    The threshold is in standard deviations above the recording's own median
    movement, not in absolute g — devices differ in scaling and placement, so a
    fixed g value would mean something different on every one.
    """
    signal = pulse_wave(seconds=20)
    acc = steady_arm(signal.size)
    rng = np.random.default_rng(0)
    acc[:, 0] += rng.normal(0, 1.5, signal.size)

    filtered = PPGPreprocessor(sampling_rate=FS).filter_signal(signal)
    lenient = PPGPreprocessor(sampling_rate=FS, accelerometer=acc,
                              acc_threshold=6.0).detect_peaks(filtered)
    strict = PPGPreprocessor(sampling_rate=FS, accelerometer=acc,
                             acc_threshold=1.0).detect_peaks(filtered)

    assert strict.size < lenient.size
