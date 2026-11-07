"""
indices.py — the three 0-5 figures a result screen can show: Calm, Recovery, Resilience.

WHY HERE AND NOT IN THE WEB APP. KARIRLINK's session-result design asks for three
numbers on a 0-5 scale. This project computes no such scale: it produces a level
per question, a recovery percentage, and a resilience quadrant. Someone has to do
the conversion, and the first rule of this project decides who: code computes the
numbers, never the screen and never the model. A rescaling written in a React
component would be arithmetic nobody tested, nobody documented, and nobody could
defend when asked where 2.4 came from.

WHAT THEY ADD: nothing. Each figure is a rescaling of a quantity that already
exists and carries exactly the same uncertainty. They exist so a screen can rank
and compare at a glance, not because the measurement improved.

WHAT THEY REFUSE TO DO: fill a gap. A heart-rate-only device produces no recovery
and no quadrant, so both figures come back `None` — never a zero. Zero on a 0-5
scale reads as "did not recover at all", which is a claim about the person; the
truth is that the instrument could not see it.
"""

from __future__ import annotations

import math

from ..config.settings import DynamicsConfig, IndexConfig, settings


def attainable_points(delta_rmssd_pct: float | None) -> int:
    """
    The most stress points this session could possibly have scored.

    The rule awards up to two points for RMSSD falling and two for heart rate
    rising. On the heart-rate-only path RMSSD is never measured, so two of the four
    points are unreachable — and dividing by four there would make every watch
    session look calmer than it was, by construction rather than by measurement.
    """
    return 2 if delta_rmssd_pct is None else 4


def calm_index(points: int, attainable: int,
               cfg: IndexConfig | None = None) -> float | None:
    """
    How calm the answering phase was, 0-5, where 5 is "nothing moved".

    Inverts the stress rule's own score: the points it awards measure how far the
    body moved from this person's resting baseline, so the calm figure is the room
    left between that and the maximum this session could have scored.
    """
    cfg = cfg or settings.indices
    if attainable <= 0:
        return None
    share = min(1.0, max(0.0, points / attainable))
    return round(cfg.scale_max * (1.0 - share), 1)


def recovery_index(median_recovery_pct: float | None,
                   cfg: IndexConfig | None = None) -> float | None:
    """
    How much of the reaction came back during the quiet gaps, 0-5.

    100% recovery — back at baseline — is the top of the scale. Overshooting past
    baseline is not extra credit: it is clamped, because "calmer afterwards than
    before" is a different observation, not a better one.

    `None` in, `None` out: recovery is read from beat-to-beat variability, and a
    device that never delivered it leaves this figure missing.
    """
    cfg = cfg or settings.indices
    if median_recovery_pct is None or math.isnan(median_recovery_pct):
        return None
    share = min(1.0, max(0.0, median_recovery_pct / 100.0))
    return round(cfg.scale_max * share, 1)


def resilience_index(median_reactivity_pct: float,
                     median_recovery_pct: float | None,
                     cfg: IndexConfig | None = None,
                     dynamics: DynamicsConfig | None = None) -> float | None:
    """
    The resilience quadrant as a number, 0-5.

    THE QUADRANT IS THE SOURCE, and it judges two things: how large the reaction
    was, and how much of it came back. This figure keeps both halves, equally
    weighted, instead of mapping four named quadrants onto a number — a mapping
    that would invent an ordering the categories never had ("held in" is not
    half as good as "flexible" by any measurement in this project).

    Each half is scaled against the quadrant's own calibrated cut-offs, so there
    is one set of thresholds to defend rather than two:

      reaction half  1.0 at no reaction, 0.5 at the "large reaction" cut-off,
                     0.0 at twice that cut-off or beyond
      recovery half  the recovery share, clamped at full recovery

    `None` under exactly the conditions the quadrant returns `None`: without both
    axes the conclusion would look more certain than the data supports.
    """
    cfg = cfg or settings.indices
    dyn = dynamics or settings.dynamics
    if median_recovery_pct is None or math.isnan(median_reactivity_pct):
        return None

    zero_at = dyn.reactivity_threshold_pct * cfg.resilience_reactivity_zero_at
    if zero_at <= 0:
        return None
    reaction_half = min(1.0, max(0.0, 1.0 - abs(median_reactivity_pct) / zero_at))
    recovery_half = min(1.0, max(0.0, median_recovery_pct / 100.0))

    weighted = (cfg.resilience_reactivity_weight * reaction_half
                + cfg.resilience_recovery_weight * recovery_half)
    total_weight = (cfg.resilience_reactivity_weight
                    + cfg.resilience_recovery_weight)
    if total_weight <= 0:
        return None
    return round(cfg.scale_max * weighted / total_weight, 1)
