"""
segmentation.py — Splits an RR series into 60-second analysis segments.

Segmentation uses a SLIDING WINDOW: 60 seconds long, advancing 30 seconds at a
time. Window 1 covers seconds 0-60, window 2 covers 30-90, and so on.

Why sliding rather than consecutive? With consecutive segments (0-60, 60-120), a
surge of pressure occurring between seconds 45 and 105 would be split across two
windows and fully captured by neither. A sliding window doubles temporal
resolution to 30 seconds without shortening the analysis window itself.

CONSEQUENCE that must be stated when reporting metrics: neighbouring windows share
half their data, so segments are NOT independent (BACKLOG L2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config.settings import QualityConfig, SegmentationConfig, settings
from ..core.types import RRSeries


@dataclass(frozen=True)
class Segment:
    """One analysis window together with its provenance."""

    index: int                 # window number (starting at 1)
    start_sec: float           # window start, relative to the phase start
    end_sec: float
    rr_ms: np.ndarray          # intervals inside the window
    outlier_ratio: float       # fraction of beats that were interpolated

    @property
    def n_beats(self) -> int:
        return int(self.rr_ms.size)


@dataclass
class SegmentationResult:
    """Segmentation output plus a record of how many windows were dropped and why."""

    segments: list[Segment]
    n_dropped_short: int = 0       # too few beats
    n_dropped_noisy: int = 0       # outliers above threshold

    @property
    def n_kept(self) -> int:
        return len(self.segments)

    @property
    def n_total(self) -> int:
        return self.n_kept + self.n_dropped_short + self.n_dropped_noisy

    def summary(self) -> str:
        return (f"{self.n_kept}/{self.n_total} windows kept "
                f"(dropped: {self.n_dropped_short} too few beats, "
                f"{self.n_dropped_noisy} too noisy)")


def segment_rr_series(
    series: RRSeries,
    seg_cfg: SegmentationConfig | None = None,
    qual_cfg: QualityConfig | None = None,
) -> SegmentationResult:
    """
    Cut one `RRSeries` into a list of `Segment`s that pass the quality gates.

    Splitting is done by TIME, not by beat count, so every window really does
    represent 60 seconds of recording. Splitting by beat count would give people
    with fast heart rates shorter windows — and HRV features are highly sensitive
    to window length.

    Two quality gates are applied here:
      1. Windows with fewer than `min_beats` beats are dropped (failed detection).
      2. Windows with more than `max_outlier_ratio` outliers are dropped (T1.6).
         Computing RMSSD from a series that is half interpolated means measuring
         guesswork rather than measuring a heart.
    """
    seg_cfg = seg_cfg or settings.segmentation
    qual_cfg = qual_cfg or settings.quality

    result = SegmentationResult(segments=[])
    if series.n_beats == 0:
        return result

    t0 = float(series.t_sec[0])
    duration = float(series.t_sec[-1]) - t0
    if duration < seg_cfg.length_sec:
        return result

    # Number of full windows that fit. Any tail shorter than 60 seconds is
    # deliberately discarded so that every segment has an equal duration.
    n_windows = int((duration - seg_cfg.length_sec) // seg_cfg.hop_sec) + 1

    kept: list[Segment] = []
    for i in range(n_windows):
        start = t0 + i * seg_cfg.hop_sec
        end = start + seg_cfg.length_sec

        window = (series.t_sec >= start) & (series.t_sec < end)
        rr = series.rr_ms[window]
        outliers = series.is_outlier[window]

        if rr.size < seg_cfg.min_beats:
            result.n_dropped_short += 1
            continue

        ratio = float(outliers.mean())
        if ratio > qual_cfg.max_outlier_ratio:
            result.n_dropped_noisy += 1
            continue

        kept.append(Segment(
            index=len(kept) + 1,
            start_sec=start - t0,
            end_sec=end - t0,
            rr_ms=rr,
            outlier_ratio=ratio,
        ))

    result.segments = kept
    return result
