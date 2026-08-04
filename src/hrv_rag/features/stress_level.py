"""
stress_level.py — Assigns the stress label. Deterministic, no LLM.

This module holds the product's classifier. It is a scoring rule of a few lines,
and that is deliberate rather than a placeholder.

WHY A RULE AND NOT THE LLM

Measured on the development subjects:

    rule (RMSSD or heart rate)   macro-F1 0.828   kappa 0.656
    always answer "low"          macro-F1 0.390   kappa 0.000

and in the same period, an LLM handed the identical numbers answered "uncertain"
on 6 of 13 resting segments that the rule labelled correctly.

Beyond accuracy, a rule is instant, free, works offline, and returns the same answer
every single time. A label that changes between runs is not something a user can be
shown with a straight face.

The LLM keeps the part it is genuinely better at — turning the result into an
explanation and a suggestion someone can act on. Splitting the work this way means
the number is defensible and the words are useful, instead of both being neither.

HOW THE SCORE WORKS

Two features are scored, from zero to two points each:

    RMSSD below baseline    -15% -> 1 point    -30% -> 2 points
    heart rate above it      +5% -> 1 point    +15% -> 2 points

    0 points        -> low
    1 to 2 points   -> moderate
    3 to 4 points   -> high

Neither feature carries the decision alone, because neither can. RMSSD moved the
expected way in only three of five development subjects, while heart rate rose in
all five — so heart rate covers the cases RMSSD misses. But heart rate on its own is
too coarse to grade severity, which is what RMSSD supplies.

That combination also handles the awkward case honestly: when RMSSD RISES while
heart rate also rises — the pattern seen in subjects S6 and S10 — RMSSD scores
nothing and heart rate still scores, so the result lands on "moderate" rather than
falsely reassuring the user that nothing happened.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config.settings import StressRuleConfig, settings
from ..core.schemas import StressLevel


@dataclass(frozen=True)
class StressVerdict:
    """The label, the score behind it, and the evidence in plain words."""

    level: StressLevel
    points: int
    max_points: int
    evidence: list[str]

    @property
    def is_confident(self) -> bool:
        """
        Whether both features agreed on the direction.

        A verdict resting on one feature while the other stays flat is weaker than
        one where both moved together, and the narrative should say so rather than
        presenting every label with equal certainty.
        """
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

    # A disagreement worth naming: the vagal marker says calm while the heart says
    # otherwise. The narrative must mention this rather than smoothing it over.
    if rmssd == rmssd and hr == hr and rmssd > 10.0 and hr > cfg.hr_moderate_pct:
        evidence.append("features disagree: RMSSD rose while heart rate also rose, "
                        "which speaking can cause")

    return StressVerdict(level=level, points=points, max_points=4,
                         evidence=evidence)
