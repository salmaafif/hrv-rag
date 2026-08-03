"""
Tests for the recovery formula and the resilience quadrants.

This is the most valuable part of U1. Recovery and resilience CANNOT be tested with
WESAD, because WESAD has no gap phase — only baseline and TSST. So the only way to
establish that the formula is correct, before it is ever applied to real session
data, is to test it against numbers whose answers are already known.

Reference example using the real S2 values:
    baseline RMSSD  = 56.8 ms
    while stressed  = 31.7 ms   -> deviation 25.1 ms
    during the gap  = 45.0 ms   -> recovered 13.3 of 25.1 = 52.99%
"""

import numpy as np
import pytest

from hrv_rag.features.dynamics import (ResilienceQuadrant, recovery_percent,
                                       resilience_quadrant)


# -------------------------------------------------------------- recovery
def test_recovery_s2_reference_example():
    """The example used in the documentation must genuinely come out at 53%."""
    result = recovery_percent(baseline=56.8, stressed=31.7, recovered=45.0)
    assert result.is_computable
    assert result.percent == pytest.approx(52.99, abs=0.01)


def test_full_recovery_is_hundred_percent():
    """Returning exactly to baseline = 100% recovered."""
    result = recovery_percent(baseline=50.0, stressed=30.0, recovered=50.0)
    assert result.percent == pytest.approx(100.0)


def test_no_recovery_is_zero_percent():
    """No movement at all from the stressed state = 0%."""
    result = recovery_percent(baseline=50.0, stressed=30.0, recovered=30.0)
    assert result.percent == pytest.approx(0.0)


def test_overshoot_exceeds_hundred():
    """Going past baseline (overcompensation) may exceed 100%."""
    result = recovery_percent(baseline=50.0, stressed=30.0, recovered=60.0)
    assert result.percent > 100.0


def test_worsening_is_negative():
    """Moving further from baseline during the gap = negative recovery."""
    result = recovery_percent(baseline=50.0, stressed=30.0, recovered=20.0)
    assert result.percent < 0.0


def test_upward_direction_also_works():
    """
    The formula must work for features that RISE under pressure, such as LF/HF and
    heart rate — not only for those that fall, such as RMSSD.
    """
    result = recovery_percent(baseline=2.0, stressed=4.0, recovered=3.0)
    assert result.percent == pytest.approx(50.0)


# ----------------------------------------------------------------- guard
def test_reaction_too_small_not_computed():
    """
    THE PRIMARY GUARD. The deviation here is only 4% (50 -> 48), below the 10%
    threshold.

    Without this guard, dividing by a tiny denominator produces wild numbers. The
    correct answer is to declare the result NOT COMPUTABLE.
    """
    result = recovery_percent(baseline=50.0, stressed=48.0, recovered=49.0)
    assert not result.is_computable
    assert "too small" in result.reason


def test_not_computable_is_not_zero():
    """
    The distinction that matters: None means "unknown", whereas 0 means "did not
    recover at all". Those are very different claims, and conflating them would
    falsify the conclusion drawn about the user.
    """
    result = recovery_percent(baseline=50.0, stressed=48.0, recovered=49.0)
    assert result.percent is None
    assert result.percent != 0


def test_missing_value_handled():
    result = recovery_percent(baseline=np.nan, stressed=30.0, recovered=40.0)
    assert not result.is_computable


def test_zero_baseline_handled():
    result = recovery_percent(baseline=0.0, stressed=30.0, recovered=40.0)
    assert not result.is_computable


# ------------------------------------------------------------- resilience
@pytest.mark.parametrize("reactivity, recovery, expected", [
    (-10.0, 80.0, ResilienceQuadrant.HIGH),       # small + fast
    (-10.0, 20.0, ResilienceQuadrant.HELD_IN),    # small + slow
    (-40.0, 80.0, ResilienceQuadrant.FLEXIBLE),   # large + fast
    (-40.0, 20.0, ResilienceQuadrant.LOW),        # large + slow
])
def test_four_quadrants(reactivity, recovery, expected):
    assert resilience_quadrant(reactivity, recovery) is expected


def test_reactivity_judged_by_absolute_value():
    """
    What is judged is the size of the disturbance, not its direction. RMSSD falling
    40% and LF/HF rising 40% both count as large reactivity.
    """
    falling = resilience_quadrant(-40.0, 80.0)
    rising = resilience_quadrant(+40.0, 80.0)
    assert falling is rising is ResilienceQuadrant.FLEXIBLE


def test_missing_recovery_leaves_quadrant_undetermined():
    """
    When one axis is missing, the quadrant must NOT be guessed. Guessing would make
    the conclusion look more certain than the data warrants.
    """
    assert resilience_quadrant(-40.0, None) is None
