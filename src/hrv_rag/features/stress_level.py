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


def _percent(value: float) -> str:
    """
    A measured change, written so it never claims to be no change at all.

    Whole numbers everywhere is the right default: nobody reads "heart rate 4.7%
    above baseline" more accurately than "5%". But below half a percent that
    rounding prints `0%`, and this sentence is what the model is given as the
    evidence behind a label — so a real measurement of -0.4% arrived as "heart
    rate 0% below baseline", which is a statement that nothing moved. Seen on the
    first real watch session, 17 September 2026. Small values therefore keep one
    decimal, which is the smallest change that stops the sentence being false.
    """
    return f"{abs(value):.1f}" if abs(value) < 0.5 else f"{abs(value):.0f}"


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
        evidence.append(f"RMSSD {_percent(rmssd)}% {direction} baseline "
                        f"({rmssd_points} pt)")
    if hr == hr:
        direction = "above" if hr > 0 else "below"
        evidence.append(f"heart rate {_percent(hr)}% {direction} baseline "
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
