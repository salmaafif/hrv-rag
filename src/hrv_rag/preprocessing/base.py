"""
base.py — Shared contract for the ECG and PPG preprocessing branches.

Some steps are IDENTICAL for both, however — ectopic correction and quality
checking operate on the interval series, not on the waveform. Those live here so
they are written once and cannot drift apart between the two branches.

Division of responsibility:
    parent class  : quality check, ectopic correction, assembling RRSeries
    subclass      : filtering and peak detection specific to its modality
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..config.settings import QualityConfig, settings
from ..core.types import Modality, Phase, QualityReport, RRSeries


class BasePreprocessor(ABC):
    """Preprocessing skeleton: raw signal -> clean RRSeries."""

    modality: Modality

    def __init__(self, sampling_rate: int,
                 quality: QualityConfig | None = None) -> None:
        self.fs = sampling_rate
        self.quality_cfg = quality or settings.quality

    # ================================================ subclass must provide
    @abstractmethod
    def filter_signal(self, raw: np.ndarray) -> np.ndarray:
        """Clean the signal according to its modality's characteristics."""

    @abstractmethod
    def detect_peaks(self, filtered: np.ndarray) -> np.ndarray:
        """Return the sample indices of each beat's peak."""

    # ============================================================ main flow
    def run(self, raw: np.ndarray, subject: str, phase: Phase) -> RRSeries:
        """
        Run the whole preprocessing chain.

        The order is the same for both modalities:
            quality check -> filter -> peak detection -> interval series
            -> ectopic correction
        """
        report = self.check_quality(raw)
        filtered = self.filter_signal(raw)
        peaks = self.detect_peaks(filtered)
        rr_ms, t_sec = self.peaks_to_intervals(peaks)
        rr_ms, is_outlier = self.correct_ectopic(rr_ms)

        return RRSeries(
            rr_ms=rr_ms, t_sec=t_sec, modality=self.modality,
            subject=subject, phase=phase, quality=report,
            is_outlier=is_outlier,
        )

    # ========================================================= shared steps
    def check_quality(self, raw: np.ndarray) -> QualityReport:
        """
        Inspect the RAW signal, before any filtering.

        This must happen before filtering, because filtering disguises damage: a
        flat stretch caused by a detached electrode looks perfectly reasonable
        after a bandpass, even though it carries no information at all.

        Two defects are detected:
        1. Clipping — samples pinned at the limits of the ADC range. Truncated
           peaks shift the apparent peak position and corrupt the intervals.
        2. Flat-line — windows with no variation whatsoever, indicating a
           detached electrode or sensor.
        """
        notes: list[str] = []

        # --- clipping: fraction of samples at the extremes ---
        lo, hi = float(np.min(raw)), float(np.max(raw))
        span = hi - lo
        if span == 0:
            return QualityReport(0.0, 1.0, False, ["signal is entirely constant"])
        # Allow 0.1% of the range as tolerance for quantisation noise.
        tol = 0.001 * span
        clipping_ratio = float(
            np.mean((raw >= hi - tol) | (raw <= lo + tol))
        )

        # --- flat-line: consecutive windows with no variation ---
        win = max(1, int(self.quality_cfg.flatline_window_sec * self.fs))
        n_win = raw.size // win
        if n_win > 0:
            blocks = raw[: n_win * win].reshape(n_win, win)
            flat_blocks = np.std(blocks, axis=1) < (1e-6 * span)
            flatline_ratio = float(flat_blocks.mean())
        else:
            flatline_ratio = 0.0

        if clipping_ratio > self.quality_cfg.max_clipping_ratio:
            notes.append(f"clipping {clipping_ratio:.1%} exceeds threshold")
        if flatline_ratio > self.quality_cfg.max_flatline_ratio:
            notes.append(f"flat-line {flatline_ratio:.1%} exceeds threshold")

        return QualityReport(
            clipping_ratio=clipping_ratio,
            flatline_ratio=flatline_ratio,
            is_acceptable=not notes,
            notes=notes,
        )

    def peaks_to_intervals(self, peaks: np.ndarray
                           ) -> tuple[np.ndarray, np.ndarray]:
        """
        Convert peak indices into an interval series (ms) plus their timestamps.

        Each interval is timestamped at the SECOND peak of its pair, because that
        is the moment the interval finished being measured. This timestamp is what
        segmentation later uses.
        """
        if peaks.size < 2:
            return np.array([]), np.array([])
        rr_ms = np.diff(peaks) / self.fs * 1000.0
        t_sec = peaks[1:] / self.fs
        return rr_ms, t_sec

    def correct_ectopic(self, rr_ms: np.ndarray
                        ) -> tuple[np.ndarray, np.ndarray]:
        """
        Flag and repair ectopic or misdetected beats.

        Two criteria per CLAUDE.md:
        1. Outside the physiological range 0.3-2.0 seconds (200 bpm to 30 bpm).
        2. Differing by more than 20% from the immediately preceding interval.

        The second criterion is evaluated against the ORIGINAL (uncorrected)
        values throughout. Two consequences matter:

        - Using original values stops flagging from cascading: the decision for
          beat i does not depend on how beat i-1 was corrected.
        - A single ectopic beat normally produces two deviant intervals (one short,
          then a compensatory long one). This criterion flags both, which is
          exactly the desired behaviour.

        Historical note: an earlier version of this code compared against "the last
        accepted interval" in an attempt to prevent cascading. That was wrong — the
        reference value could freeze and reject beats in a long chain (measured at
        59.5% on S2 under stress, where the literal criterion gives only 1.5%).

        Flagged values are replaced by linear interpolation from the valid beats
        around them. Interpolation is preferred over deletion so the time axis stays
        intact; deleting beats would silently shorten the segment.
        """
        n = rr_ms.size
        if n == 0:
            return rr_ms, np.zeros(0, dtype=bool)

        cfg = self.quality_cfg
        rr = rr_ms.astype(float).copy()
        is_outlier = np.zeros(n, dtype=bool)

        # --- Criterion 1: physiological bounds ---
        lo_ms, hi_ms = cfg.rr_min_sec * 1000.0, cfg.rr_max_sec * 1000.0
        is_outlier |= (rr < lo_ms) | (rr > hi_ms)

        # --- Criterion 2: >20% jump from the preceding interval ---
        # Computed in one pass over the original array rather than in a loop, so no
        # corrected value can ever become a reference.
        rel_diff = np.abs(np.diff(rr_ms)) / rr_ms[:-1]
        is_outlier[1:] |= rel_diff > cfg.max_rel_diff

        # --- Repair by interpolation ---
        n_bad = int(is_outlier.sum())
        if 0 < n_bad < n:
            idx = np.arange(n)
            rr[is_outlier] = np.interp(
                idx[is_outlier], idx[~is_outlier], rr[~is_outlier]
            )

        return rr, is_outlier
