"""
bpm.py — the fourth entry point: a device that reports heart rate and nothing finer.

Most smartwatches broadcast a heart-rate value about once a second and never the
interval between two beats. Everything after preprocessing in this project works on
an interval series, cut into 60-second windows, gated, split into rest and task.
Writing a second copy of that machinery for bpm would mean a second place for the
clock and window arithmetic to go wrong — the arithmetic that has already put
question windows in the wrong place twice.

So this file rebuilds a beat series from the bpm curve and hands it to the same
machinery. THE REBUILT SERIES IS NOT A RECORDING OF BEATS. Its intervals are equal
wherever the reported rate is flat, so any variability feature computed from it
(RMSSD, SDNN, pNN50, the LF/HF family) describes the reconstruction, not the heart.
Those features are deleted before anything can read them — see
`BaselineProfile.restricted_to` and `BPM_TIER_FEATURES`. The one quantity the
series carries honestly is RATE: over any window, its mean heart rate equals the
time-weighted mean of the bpm the device reported.

THREE RULES, each the reason for one part of the code:

1. The phase is carried across samples. Restarting the beat count at every sample
   silently truncates the fractional beat: 70 bpm reported once a second becomes
   exactly one beat per second, i.e. 60 bpm, with nothing to show for the error.

2. Time is preserved exactly. The rebuilt intervals sum to the span between the
   first sample and the last beat, so a question asked at minute seven is read from
   minute seven.

3. A hole in the stream is flagged, never passed off as measurement. The device's
   own reporting cadence is read from the data (the median spacing), and any
   spacing well beyond it means reports went missing. Beats bridging such a hole
   are emitted — dropping them would compress every later second of the session —
   but each one is marked, and downstream they count exactly as an interpolated
   beat counts on the interval path: a window where they exceed the outlier limit
   is discarded, and what cannot be measured is reported as not measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..config.settings import TierConfig, settings


@dataclass(frozen=True)
class ReconstructedBeats:
    """A beat series rebuilt from heart-rate samples, with its holes marked."""

    #: Interval ending at each rebuilt beat, milliseconds.
    rr_ms: np.ndarray
    #: True for a beat inside a stretch the device never reported.
    in_gap: np.ndarray
    #: The unreported stretches, in seconds from the first sample.
    gaps_sec: list[tuple[float, float]] = field(default_factory=list)


def beats_from_bpm(at_sec, bpm, cfg: TierConfig | None = None) -> ReconstructedBeats:
    """
    Rebuild a beat series from heart-rate samples.

    Each sample's rate holds until the next sample. Inside a gap the rate moves in a
    straight line between the two samples that bound it, in steps of the device's
    own cadence, so a bridged stretch never drags a window towards one stale value.
    """
    cfg = cfg or settings.tier
    t = np.asarray(at_sec, dtype=float)
    rate = np.asarray(bpm, dtype=float)

    if t.size != rate.size:
        raise ValueError("every heart-rate sample needs both a time and a value")
    if t.size < 2:
        raise ValueError("at least two heart-rate samples are needed")
    spacing = np.diff(t)
    if np.any(spacing <= 0):
        raise ValueError("heart-rate sample times must strictly increase")
    if np.any(rate <= 0):
        raise ValueError("heart-rate values must be positive")

    cadence = float(np.median(spacing))
    t0 = float(t[0])

    # Piecewise-constant stretches: (start, end, bpm, bridged).
    stretches: list[tuple[float, float, float, bool]] = []
    gaps: list[tuple[float, float]] = []
    for i, step in enumerate(spacing):
        start, end = float(t[i]), float(t[i + 1])
        if step <= cfg.sample_gap_factor * cadence:
            stretches.append((start, end, float(rate[i]), False))
            continue
        n = math.ceil(step / cadence)
        width = step / n
        for k in range(n):
            share = k / n
            stretches.append((start + k * width, start + (k + 1) * width,
                              float(rate[i] + (rate[i + 1] - rate[i]) * share),
                              k > 0))
        # The first cadence after a sample is that sample's own report.
        gaps.append((start + width - t0, end - t0))

    beat_times: list[float] = []
    bridged: list[bool] = []
    phase = 0.0                  # fraction of a beat already elapsed
    for start, end, bpm_value, is_bridged in stretches:
        seconds_per_beat = 60.0 / bpm_value
        clock = start
        while True:
            to_next = (1.0 - phase) * seconds_per_beat
            if clock + to_next > end:
                phase += (end - clock) / seconds_per_beat
                break
            clock += to_next
            beat_times.append(clock)
            bridged.append(is_bridged)
            phase = 0.0

    edges = np.concatenate(([t0], np.asarray(beat_times, dtype=float)))
    return ReconstructedBeats(
        rr_ms=np.diff(edges) * 1000.0,
        in_gap=np.asarray(bridged, dtype=bool),
        gaps_sec=gaps,
    )
