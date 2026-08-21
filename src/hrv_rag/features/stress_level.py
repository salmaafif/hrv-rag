from __future__ import annotations

from dataclasses import dataclass

from ..config.settings import StressRuleConfig, settings
from ..core.schemas import StressLevel

#: Identifies which frozen calibration of this rule produced a given label
#: (decision K16; §3.3 of docs/ARSITEKTUR_KARIRLINK_HRV.md). The date is the
#: freeze date recorded on `StressRuleConfig` in config/settings.py — the
#: rule is calibrated once against the development subjects and then never
#: retuned, so a version only needs to change if that config's thresholds do.
RULE_VERSION = "K16-2026-08-03"


@dataclass(frozen=True)
class StressVerdict:
    """The label, the score behind it, and the evidence in plain words."""

    level: StressLevel
    points: int
    max_points: int
    evidence: list[str]

    @property
    def is_confident(self) -> bool:
        return self.points == 0 or self.points >= 3

    def describe(self) -> str:
        return (f"{self.level.value} ({self.points}/{self.max_points} points): "
                + "; ".join(self.evidence))


def _score_feature(value: float, moderate: float, high: float,
                   rising: bool) -> int:
    """Award 0, 1 or 2 points for how far one feature moved."""
    if value != value:                        # NaN: nothing measured
        return 0
    if rising:
        return 2 if value >= high else (1 if value >= moderate else 0)
    return 2 if value <= high else (1 if value <= moderate else 0)


def classify(reactivity: dict[str, float],
             cfg: StressRuleConfig | None = None) -> StressVerdict:
    """
    Turn one question's reactivity into a stress label.

    Takes the percentage changes already computed against the person's own baseline.
    Nothing here is learned or estimated; the same input always gives the same label,
    and every step can be recomputed by hand.
    """
    cfg = cfg or settings.stress_rule

    rmssd = reactivity.get("delta_pct_rmssd", float("nan"))
    hr = reactivity.get("delta_pct_mean_hr", float("nan"))

    rmssd_points = _score_feature(rmssd, cfg.rmssd_moderate_pct,
                                  cfg.rmssd_high_pct, rising=False)
    hr_points = _score_feature(hr, cfg.hr_moderate_pct,
                               cfg.hr_high_pct, rising=True)
    points = rmssd_points + hr_points

    evidence: list[str] = []
    if rmssd == rmssd:
        direction = "below" if rmssd < 0 else "above"
        evidence.append(f"RMSSD {abs(rmssd):.0f}% {direction} baseline "
                        f"({rmssd_points} pt)")
    if hr == hr:
        direction = "above" if hr > 0 else "below"
        evidence.append(f"heart rate {abs(hr):.0f}% {direction} baseline "
                        f"({hr_points} pt)")
    if not evidence:
        evidence.append("no usable measurement")

    if points >= cfg.high_points:
        level = StressLevel.HIGH
    elif points >= cfg.moderate_points:
        level = StressLevel.MODERATE
    else:
        level = StressLevel.LOW
    if rmssd == rmssd and hr == hr and rmssd > 10.0 and hr > cfg.hr_moderate_pct:
        evidence.append("features disagree: RMSSD rose while heart rate also rose, "
                        "which speaking can cause")

    return StressVerdict(level=level, points=points, max_points=4,
                         evidence=evidence)
