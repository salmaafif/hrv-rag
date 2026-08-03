"""
conftest.py — Shared setup for the whole test suite.

Holds the import path and a few synthetic-data factories. The testing principle in
this project: **test with inputs whose answers are known in advance**, not with
WESAD data. Testing against real data only shows that results "look plausible" — it
cannot prove the arithmetic is correct.

That matters because Mandatory Rule #1 makes the CODE the source of truth for every
number. If the code miscomputes, the whole thesis claim collapses and the LLM
cannot be blamed for it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_rag.core.types import (Modality, Phase,  # noqa: E402
                                QualityReport, RRSeries)


@pytest.fixture
def clean_quality() -> QualityReport:
    """A passing quality report, for tests that are not about signal quality."""
    return QualityReport(clipping_ratio=0.0, flatline_ratio=0.0,
                         is_acceptable=True)


@pytest.fixture
def make_series(clean_quality):
    """
    Factory for synthetic `RRSeries` objects.

    By default it produces beats of exactly 1000 ms, so each beat lands on a whole
    second — which makes the expected number of segments easy to work out by hand.
    """
    def _make(n_beats: int = 181, rr_value: float = 1000.0,
              outlier_mask: np.ndarray | None = None,
              phase: Phase = Phase.CALIBRATION) -> RRSeries:
        rr = np.full(n_beats, rr_value, dtype=float)
        t = np.cumsum(rr) / 1000.0
        mask = (outlier_mask if outlier_mask is not None
                else np.zeros(n_beats, dtype=bool))
        return RRSeries(rr_ms=rr, t_sec=t, modality=Modality.ECG,
                        subject="TEST", phase=phase,
                        quality=clean_quality, is_outlier=mask)
    return _make


def synth_modulated_rr(freq_hz: float, duration_sec: float = 120.0,
                       mean_rr: float = 800.0, amplitude: float = 50.0
                       ) -> np.ndarray:
    """
    Build an RR series modulated by a sine wave at a chosen frequency.

    Used to test the spectral analysis: if the RR series oscillates at 0.25 Hz, its
    spectral power MUST appear in the HF band (0.15-0.40 Hz). This proves the
    frequency code is correct without comparing against another library.

    Beat times are built up iteratively because the length of each RR interval is
    itself what determines when the next beat occurs.
    """
    t, values = 0.0, []
    while t < duration_sec:
        rr = mean_rr + amplitude * np.sin(2.0 * np.pi * freq_hz * t)
        values.append(rr)
        t += rr / 1000.0
    return np.asarray(values)
