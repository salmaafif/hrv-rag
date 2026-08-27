"""
Tests for the per-signal RMSSD fitness check (features/signal_fitness.py).

The design point worth protecting: the verdict is about THIS recording, judged
by ratios, never about a device class. The same 7 ms clock that is fine for a
person with resting RMSSD 45 ms genuinely is too coarse for one at 12 ms — and
a blanket per-device rule would get one of those two people wrong whichever way
it ruled.
"""

import numpy as np
import pytest

from hrv_rag.config.settings import SignalFitnessConfig
from hrv_rag.features.signal_fitness import assess_signal


def steady(n: int, base: float = 850.0, jitter: float = 30.0) -> np.ndarray:
    """A clean series with millisecond-fine steps and honest variability."""
    wobble = jitter * np.sin(np.arange(n) * 0.7) + (np.arange(n) * 37 % 11)
    return base + wobble


def test_a_clean_recording_keeps_its_rmssd():
    fitness = assess_signal(steady(150), steady(300), task_outlier_ratio=0.02)

    assert fitness.rmssd_trusted
    assert fitness.reasons == []


def test_unreliable_beat_detection_while_answering_withholds_trust():
    """
    The check that separated the two devices in measured data: the WESAD wrist
    sensor hit 16-37% flagged beats under stress, the field armband stayed at
    2-7% while its wearer spoke.
    """
    fitness = assess_signal(steady(150), steady(300), task_outlier_ratio=0.25)

    assert not fitness.rmssd_trusted
    assert any("beat detection" in r for r in fitness.reasons)


def test_missed_beats_withhold_trust():
    """
    A missed beat forges a successive difference of a whole beat's length —
    the exact quantity RMSSD squares. A detector that keeps missing them makes
    every jitter figure fiction.
    """
    task = steady(300)
    task[::20] = 1700.0                        # 5% of intervals = two beats fused
    fitness = assess_signal(steady(150), task, task_outlier_ratio=0.02)

    assert not fitness.rmssd_trusted
    assert any("missed beat" in r for r in fitness.reasons)


def test_the_clock_is_judged_against_the_person_not_in_the_abstract():
    """
    THE REASON THIS MODULE EXISTS INSTEAD OF A PER-DEVICE BAN. One and the same
    100 ms clock: too coarse for a person whose resting RMSSD is comparable to
    its noise floor, perfectly serviceable for one whose variability dwarfs it.
    """
    # Alternating +/-50 ms on a 100 ms grid: RMSSD 100 ms, floor 40.8 ms.
    coarse_low = 950.0 + 50.0 * (-1) ** np.arange(150)
    fitness = assess_signal(coarse_low, coarse_low[:300],
                            task_outlier_ratio=0.02)
    assert not fitness.rmssd_trusted
    assert any("clock too coarse" in r for r in fitness.reasons)

    # Same 100 ms grid, but variability that dwarfs the 40.8 ms floor:
    # RMSSD ~331 ms, ratio 0.12 — trusted. The grid did not change; the person did.
    coarse_high = np.tile([800.0, 1100.0, 1000.0, 1300.0], 40)
    fitness = assess_signal(coarse_high, coarse_high, task_outlier_ratio=0.02)
    assert fitness.quantization_step_ms == 100.0
    assert fitness.rmssd_trusted


def test_a_flat_series_is_not_punished_for_showing_no_step():
    """No observable step means no evidence either way, not a failure."""
    flat = np.full(150, 900.0)
    fitness = assess_signal(flat, flat, task_outlier_ratio=0.0)

    assert fitness.rmssd_trusted
    assert fitness.quantization_step_ms == 0.0


def test_thresholds_come_from_config_not_from_the_code():
    tight = SignalFitnessConfig(max_task_outlier_ratio=0.01)
    fitness = assess_signal(steady(150), steady(300),
                            task_outlier_ratio=0.05, cfg=tight)
    assert not fitness.rmssd_trusted


def test_the_api_block_names_the_verdict_and_the_numbers_behind_it():
    block = assess_signal(steady(150), steady(300),
                          task_outlier_ratio=0.02).block()
    assert block["rmssd_trusted"] is True
    for key in ("reasons", "quantization_step_ms", "missed_beat_ratio",
                "task_outlier_ratio"):
        assert key in block
