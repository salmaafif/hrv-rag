"""
ppg.py — PPG preprocessing branch (the modality validated against ECG).

PPG records blood volume changes optically rather than the heart's electrical
activity. Three things genuinely differ from the ECG branch, which is why CLAUDE.md
requires a separate file rather than an `if` inside one:

1. **Filter band 0.5-8 Hz** instead of 0.5-40 Hz. The PPG waveform is smooth and has
   nothing as sharp as a QRS complex, so passing frequencies up to 40 Hz would admit
   noise without admitting any signal. There is also no mains notch: an optical
   sensor does not pick up 50 Hz interference the way skin electrodes do.

2. **Systolic peak detection** instead of R-peak detection. Systolic peaks are broad
   and rounded, so their timing is inherently less certain than an R peak's. This is
   the physical reason PRV is not simply HRV measured elsewhere.

3. **Motion artefact removal.** Optical sensors are highly sensitive to movement.
   WESAD records wrist acceleration alongside BVP, so windows with strong movement
   can be identified and their beats excluded rather than silently corrupting the
   interval series.

Everything after this stage is shared: the output is an `RRSeries` exactly like the
ECG branch produces, so features, RAG, and evaluation are reused unchanged. Only the
`modality` attribute differs, and it travels all the way into the prompt so the LLM
can lower its confidence accordingly (Mandatory Rule #5).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt

import neurokit2 as nk

from ..config.settings import PPGFilterConfig, QualityConfig, settings
from ..core.types import Modality
from .base import BasePreprocessor


class PPGPreprocessor(BasePreprocessor):
    """Raw PPG/BVP signal -> clean inter-beat interval series."""

    modality = Modality.PPG

    def __init__(self, sampling_rate: int,
                 filter_cfg: PPGFilterConfig | None = None,
                 quality: QualityConfig | None = None,
                 accelerometer: np.ndarray | None = None,
                 acc_threshold: float = 3.0) -> None:
        """
        `accelerometer` is optional wrist acceleration, shaped (n_samples, 3) and
        already resampled to the PPG rate. When supplied, beats occurring during
        strong movement are flagged as artefacts.

        `acc_threshold` is expressed in standard deviations above that recording's
        own median movement, not in absolute g. Devices differ in scaling and
        placement, and a fixed g threshold would be arbitrary across them; a
        relative threshold adapts to whatever the recording itself looks like.
        """
        super().__init__(sampling_rate, quality)
        self.filter_cfg = filter_cfg or settings.ppg_filter
        self.accelerometer = accelerometer
        self.acc_threshold = acc_threshold

    def filter_signal(self, raw: np.ndarray) -> np.ndarray:
        """
        Order-2 Butterworth bandpass, 0.5-8 Hz.

        The upper edge sits at 8 Hz because the pulse waveform's useful harmonics
        die out well below that; anything higher is noise. No notch filter is
        applied, since an optical sensor is not coupled to mains interference.

        filtfilt is used for the same reason as in the ECG branch: it cancels its
        own phase shift, so peak positions are not displaced. Timing accuracy
        matters even more here, because systolic peaks are already blunt.
        """
        cfg = self.filter_cfg
        nyq = 0.5 * self.fs
        b, a = butter(cfg.order,
                      [cfg.lowcut_hz / nyq, cfg.highcut_hz / nyq],
                      btype="band")
        return filtfilt(b, a, raw)

    def detect_peaks(self, filtered: np.ndarray) -> np.ndarray:
        """
        Detect systolic peaks with NeuroKit2, then drop those hit by movement.

        Peak detection runs on the full signal first and motion filtering is applied
        afterwards, rather than blanking the signal beforehand. Zeroing a stretch of
        waveform would create artificial edges that the detector would read as
        peaks — the same splicing problem the dataset loader avoids.
        """
        _, info = nk.ppg_peaks(filtered, sampling_rate=self.fs)
        peaks = np.asarray(info["PPG_Peaks"])

        if self.accelerometer is None or peaks.size == 0:
            return peaks
        return peaks[~self._motion_mask(peaks)]

    def _motion_mask(self, peaks: np.ndarray) -> np.ndarray:
        """
        Flag peaks that occurred during strong wrist movement.

        Movement is measured as the magnitude of the change in acceleration, not the
        magnitude of acceleration itself. Gravity contributes a constant component to
        any static posture, so a raw magnitude would mark a motionless raised arm as
        movement; its derivative is near zero unless the wrist is actually moving.
        """
        acc = np.asarray(self.accelerometer, dtype=float)
        if acc.ndim == 1:
            acc = acc.reshape(-1, 1)

        magnitude = np.linalg.norm(acc, axis=1)
        movement = np.abs(np.diff(magnitude, prepend=magnitude[0]))

        # Smooth over a quarter second so a single spike does not reject a beat.
        window = max(1, int(0.25 * self.fs))
        smoothed = np.convolve(movement, np.ones(window) / window, mode="same")

        median = float(np.median(smoothed))
        spread = float(np.std(smoothed))
        if spread == 0:
            return np.zeros(peaks.size, dtype=bool)

        limit = median + self.acc_threshold * spread
        # Peak indices can exceed the accelerometer length by rounding; clip them.
        idx = np.clip(peaks, 0, smoothed.size - 1)
        return smoothed[idx] > limit
