"""
ecg.py — ECG preprocessing branch (the reference / gold-standard modality).

What is specific to ECG and does NOT apply to PPG:
  - A 0.5-40 Hz band, because the QRS complex has sharp components up to ~40 Hz
  - A 50 Hz notch, because ECG electrodes pick up mains interference
  - R-peak detection (not systolic-peak detection); R peaks are narrow and tall
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch

import neurokit2 as nk

from ..config.settings import ECGFilterConfig, QualityConfig, settings
from ..core.types import Modality
from .base import BasePreprocessor


class ECGPreprocessor(BasePreprocessor):
    """Raw ECG signal -> clean RR series."""

    modality = Modality.ECG

    def __init__(self, sampling_rate: int,
                 filter_cfg: ECGFilterConfig | None = None,
                 quality: QualityConfig | None = None) -> None:
        super().__init__(sampling_rate, quality)
        self.filter_cfg = filter_cfg or settings.ecg_filter

    def filter_signal(self, raw: np.ndarray) -> np.ndarray:
        """
        Order-2 Butterworth bandpass (0.5-40 Hz) plus a 50 Hz notch.

        Why filtfilt rather than lfilter? filtfilt runs the filter forward and then
        backward, so the phase shifts cancel out. This is not a cosmetic detail: an
        ordinary filter displaces R-peak positions by a few milliseconds, and since
        RMSSD is computed from differences between intervals, a shift that small
        contaminates the system's primary feature directly.
        """
        cfg = self.filter_cfg
        nyq = 0.5 * self.fs

        b, a = butter(
            cfg.order,
            [cfg.lowcut_hz / nyq, cfg.highcut_hz / nyq],
            btype="band",
        )
        filtered = filtfilt(b, a, raw)

        b_notch, a_notch = iirnotch(cfg.notch_hz, cfg.notch_q, self.fs)
        return filtfilt(b_notch, a_notch, filtered)

    def detect_peaks(self, filtered: np.ndarray) -> np.ndarray:
        """
        Detect R peaks using NeuroKit2 (a Pan-Tompkins variant).

        An established library is used rather than a hand-written detector, because
        QRS detection is a long-solved and extensively validated problem. This
        thesis contributes at the RAG stage, not by reimplementing a detector.
        """
        _, info = nk.ecg_peaks(filtered, sampling_rate=self.fs)
        return np.asarray(info["ECG_R_Peaks"])
