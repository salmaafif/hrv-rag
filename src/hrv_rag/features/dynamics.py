"""
dynamics.py — Recovery, resilience, and the ordering of triggers across a session.

Unlike the other feature modules, this one does not look at a single segment; it
looks at the RELATIONSHIP between segments over time.

The design document places recovery and the resilience index in the "Code
(formula)" column, so both are computed deterministically here — unlike the stress
label itself, which remains the LLM's judgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from ..config.settings import DynamicsConfig, settings


class ResilienceQuadrant(str, Enum):
    """
    The four possible combinations of reactivity and recovery.

    Deliberately NOT a 0-100 score. A number like "resilience 72" only means
    something against a reference, and that reference would have to come from
    comparing people to one another — exactly what Mandatory Rule #2 forbids.
    Quadrants carry the same information without feigning precision.
    """

    HIGH = "high resilience"        # small reactivity, fast recovery
    HELD_IN = "held-in tension"     # small reactivity, slow recovery
    FLEXIBLE = "responsive but flexible"   # large reactivity, fast recovery
    LOW = "low resilience"          # large reactivity, slow recovery


@dataclass(frozen=True)
class RecoveryResult:
    """Recovery computed for one question."""

    percent: float | None      # None = not computable
    reason: str = ""           # explanation when None

    @property
    def is_computable(self) -> bool:
        return self.percent is not None


def recovery_percent(baseline: float, stressed: float, recovered: float,
                     cfg: DynamicsConfig | None = None) -> RecoveryResult:
    """
    What percentage of the deviation has returned towards baseline during the gap.

        recovery = (stressed - during_gap) / (stressed - baseline) x 100

    Reading it:
        100%  = back at baseline
        >100% = overshot past baseline
        0%    = did not move at all
        <0%   = moved further away from baseline

    Worked example using real S2 numbers — baseline RMSSD 56.8 ms falls to 31.7 ms
    under stress (a deviation of 25.1 ms). If it rises to 45.0 ms during the gap,
    then 13.3 of those 25.1 have been recovered, which is 53%.

    THE GUARD. If a question barely provoked anything, the denominator
    (stressed - baseline) approaches zero and the division explodes into meaningless
    numbers. The calculation therefore only runs when the deviation is at least
    `min_deviation_ratio` of the baseline. Otherwise the result is declared NOT
    COMPUTABLE — never filled in as zero, because zero means "did not recover at
    all", which is an entirely different claim.
    """
    cfg = cfg or settings.dynamics

    if any(v is None or np.isnan(v) for v in (baseline, stressed, recovered)):
        return RecoveryResult(None, "one of the values is missing")
    if baseline == 0:
        return RecoveryResult(None, "baseline is zero")

    deviation = stressed - baseline
    if abs(deviation) / abs(baseline) < cfg.min_deviation_ratio:
        return RecoveryResult(
            None,
            f"reaction too small ({abs(deviation) / abs(baseline):.1%} "
            f"< {cfg.min_deviation_ratio:.0%})",
        )

    return RecoveryResult(float((stressed - recovered) / deviation * 100.0))


def resilience_quadrant(reactivity_pct: float, recovery_pct: float | None,
                        cfg: DynamicsConfig | None = None
                        ) -> ResilienceQuadrant | None:
    """
    Place one session into a resilience quadrant.

    Uses the ABSOLUTE value of reactivity, because what is being judged is the size
    of the disturbance — the direction is already determined by which feature it is
    (RMSSD falls under pressure, LF/HF rises).

    Returns None when recovery is not computable: without one of the two axes the
    quadrant cannot be determined, and guessing the missing axis would make the
    conclusion look more certain than the data supports.
    """
    cfg = cfg or settings.dynamics
    if recovery_pct is None or np.isnan(reactivity_pct):
        return None

    strong = abs(reactivity_pct) >= cfg.reactivity_threshold_pct
    fast = recovery_pct >= cfg.recovery_threshold_pct

    if strong and fast:
        return ResilienceQuadrant.FLEXIBLE
    if strong and not fast:
        return ResilienceQuadrant.LOW
    if not strong and fast:
        return ResilienceQuadrant.HIGH
    return ResilienceQuadrant.HELD_IN


def rank_by_reactivity(features: pd.DataFrame,
                       cfg: DynamicsConfig | None = None) -> pd.DataFrame:
    """
    Order segments from most to least provoking.

    This is the basis of the "per-question dynamics": which question shook this
    person the most, judged against that same person. The comparison stays inside
    one session, so no between-person comparison is involved.

    Entirely deterministic — computed by code, not by the LLM. That means this
    ordering does not change if the language model is swapped out.
    """
    cfg = cfg or settings.dynamics
    col = f"delta_pct_{cfg.primary_feature}"
    if col not in features.columns:
        raise KeyError(f"Column {col} is missing — reactivity not computed yet.")

    ranked = features.copy()
    # RMSSD FALLS under pressure, so the most provoking segment has the most
    # negative delta. Sorting ascending puts it first.
    ranked = ranked.sort_values(col, ascending=True)
    ranked["trigger_rank"] = range(1, len(ranked) + 1)
    return ranked
