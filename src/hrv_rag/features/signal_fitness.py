"""
signal_fitness.py — is THIS recording good enough for RMSSD, judged per signal.

WHY PER SIGNAL AND NOT PER DEVICE CLASS. The evidence against "PPG" as a class
turned out to be evidence against one device: WESAD's wrist-worn Empatica E4
collapsed under stress (16-37% outliers during TSST, RMSSD ICC +0.109), while
the project's actual armband, a Coospo HW9, stayed clean in the field on the
same checks — 2-7% outliers WHILE the wearer was speaking, <1% missed beats.
Sentencing every optical sensor for the E4's failure would have thrown away a
working device. So the verdict is computed from the recording itself, with the
criteria that separated those two devices in measured data.

WHAT THIS CAN AND CANNOT CATCH — the honest boundary. Everything here is
computable from the RR series alone, which means it catches NOISE: beats the
detector mangled, beats it missed, a clock too coarse for the quantity. It
cannot catch systematic BIAS — a cleanly-detected series that is consistently
wrong looks identical to one that is right. Ruling bias out needs a reference
recording (chest-strap ECG worn simultaneously), which is a per-device
certification run once, not a per-signal check run always. Until that run
exists for a device, passing these checks means "no measurable reason to
distrust", never "certified accurate".

WHAT HAPPENS DOWNSTREAM. When RMSSD is not trusted, its reactivity is fed to
the scoring rule as NaN — the rule already treats NaN as "nothing measured"
and scores from heart rate alone. Thresholds stay frozen; what changes is
which features get a voice, per recording, for stated reasons. Heart rate is
never gated here: rate is a count, robust to everything these checks measure
(the E4's rate agreed with ECG at ICC +0.986 even while its RMSSD was noise).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config.settings import SignalFitnessConfig, settings


@dataclass(frozen=True)
class SignalFitness:
    """The verdict, with the numbers it was reached from."""

    rmssd_trusted: bool
    reasons: list[str] = field(default_factory=list)

    quantization_step_ms: float = 0.0
    noise_floor_ms: float = 0.0
    rest_rmssd_ms: float = 0.0
    missed_beat_ratio: float = 0.0
    task_outlier_ratio: float = 0.0

    def block(self) -> dict:
        """The API representation. Instrument facts, not person facts."""
        return {
            "rmssd_trusted": self.rmssd_trusted,
            "reasons": list(self.reasons),
            "quantization_step_ms": round(self.quantization_step_ms, 2),
            "missed_beat_ratio": round(self.missed_beat_ratio, 4),
            "task_outlier_ratio": round(self.task_outlier_ratio, 4),
        }


def _quantization_step(rr_ms: np.ndarray) -> float:
    """
    The device clock's effective tick, from the data itself.

    The smallest nonzero gap between successive intervals. A sensor reporting
    on a 1/1024 s BLE grid shows ~1 ms; the HW9 in the field showed ~6.8 ms;
    a device rounding to whole seconds would show 1000 ms. Zero when the series
    never moves — no step is observable, and none is claimed.
    """
    diffs = np.abs(np.diff(rr_ms.astype(float)))
    diffs = diffs[diffs > 0]
    return float(diffs.min()) if diffs.size else 0.0


def _rmssd(rr_ms: np.ndarray) -> float:
    diffs = np.diff(rr_ms.astype(float))
    return float(np.sqrt(np.mean(diffs ** 2))) if diffs.size else 0.0


def _missed_beat_ratio(rr_ms: np.ndarray) -> float:
    """
    Intervals close to twice the median are one heartbeat the detector missed.

    A missed beat forges a successive difference of a whole beat's length —
    exactly the quantity RMSSD squares. The ectopic gate catches most, but a
    recording where they keep appearing has a detection problem, not a rhythm.
    """
    if rr_ms.size == 0:
        return 0.0
    median = float(np.median(rr_ms))
    doubled = (rr_ms > 1.7 * median) & (rr_ms < 2.3 * median)
    return float(np.mean(doubled))


def assess_signal(rest_rr_ms: np.ndarray, task_rr_ms: np.ndarray,
                  task_outlier_ratio: float,
                  cfg: SignalFitnessConfig | None = None) -> SignalFitness:
    """
    Judge whether RMSSD from this recording deserves a voice in the label.

    Three checks, any one enough to withhold trust. Each threshold's rationale
    lives on the config, next to its number.
    """
    cfg = cfg or settings.signal_fitness

    both = np.concatenate([np.asarray(rest_rr_ms, dtype=float),
                           np.asarray(task_rr_ms, dtype=float)])
    step = _quantization_step(both)
    floor = step / np.sqrt(6.0)
    rest_rmssd = _rmssd(np.asarray(rest_rr_ms, dtype=float))
    missed = _missed_beat_ratio(both)

    reasons: list[str] = []
    if task_outlier_ratio > cfg.max_task_outlier_ratio:
        reasons.append(
            f"beat detection unreliable while answering: "
            f"{task_outlier_ratio:.0%} of beats flagged "
            f"(limit {cfg.max_task_outlier_ratio:.0%})"
        )
    if missed > cfg.max_missed_beat_ratio:
        reasons.append(
            f"{missed:.1%} of intervals look like a missed beat "
            f"(limit {cfg.max_missed_beat_ratio:.1%})"
        )
    if rest_rmssd > 0 and floor > cfg.max_quantization_ratio * rest_rmssd:
        reasons.append(
            f"device clock too coarse for this person's variability: "
            f"quantization noise floor {floor:.1f} ms against a resting "
            f"RMSSD of {rest_rmssd:.1f} ms"
        )

    return SignalFitness(
        rmssd_trusted=not reasons,
        reasons=reasons,
        quantization_step_ms=step,
        noise_floor_ms=floor,
        rest_rmssd_ms=rest_rmssd,
        missed_beat_ratio=missed,
        task_outlier_ratio=float(task_outlier_ratio),
    )
