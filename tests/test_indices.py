"""
Tests for the three 0-5 figures the result screen shows.

These numbers add no information — each is a rescaling of something already
measured — so what has to be guarded is the opposite: that they never invent
anything. A missing measurement must stay missing, a heart-rate-only session must
not be flattered by points it could never have scored, and the scale must not
reward overshooting past a person's own baseline.

Every expected value below is worked out by hand from the frozen thresholds.
"""

from __future__ import annotations

import math

from hrv_rag.config.settings import settings
from hrv_rag.features.indices import (attainable_points, calm_index,
                                      recovery_index, resilience_index)


# ------------------------------------------------------------ attainable
def test_the_heart_rate_path_can_only_ever_score_half_the_points():
    """
    RMSSD is never measured there, so two of the four points are unreachable.
    Dividing by four anyway would make every watch session look calm by
    construction rather than by measurement.
    """
    assert attainable_points(None) == 2
    assert attainable_points(-12.4) == 4
    assert attainable_points(0.0) == 4


# ------------------------------------------------------------------ calm
def test_calm_is_full_when_nothing_moved_and_empty_at_the_maximum():
    assert calm_index(0, 4) == 5.0
    assert calm_index(4, 4) == 0.0


def test_calm_uses_the_points_this_session_could_actually_score():
    # One point of two attainable is half the room: the same session judged
    # against four would read 3.8 and call a tense person calm.
    assert calm_index(1, 2) == 2.5
    assert calm_index(1, 4) == 3.8


def test_calm_never_leaves_the_scale_even_if_the_rule_changes():
    assert calm_index(9, 4) == 0.0
    assert calm_index(-1, 4) == 5.0
    assert calm_index(1, 0) is None


# -------------------------------------------------------------- recovery
def test_recovery_maps_full_return_to_the_top_of_the_scale():
    assert recovery_index(100.0) == 5.0
    assert recovery_index(40.0) == 2.0
    assert recovery_index(0.0) == 0.0


def test_overshooting_past_baseline_is_not_extra_credit():
    """Calmer afterwards than before is a different observation, not a better one."""
    assert recovery_index(130.0) == 5.0


def test_moving_further_away_is_the_floor_not_a_negative_figure():
    assert recovery_index(-25.0) == 0.0


def test_a_device_without_intervals_leaves_recovery_missing_not_zero():
    """Zero would say the person did not recover. The truth: nothing could see it."""
    assert recovery_index(None) is None
    assert recovery_index(float("nan")) is None


# ------------------------------------------------------------ resilience
def test_resilience_halves_are_anchored_on_the_quadrant_thresholds():
    # Reaction exactly at the "large reaction" cut-off scores half its axis;
    # recovery of 50% scores half of its own. Equal weights -> 2.5 of 5.
    cut = settings.dynamics.reactivity_threshold_pct
    assert resilience_index(-cut, 50.0) == 2.5


def test_no_reaction_and_full_recovery_is_the_top_of_the_scale():
    assert resilience_index(0.0, 100.0) == 5.0


def test_a_huge_reaction_scores_nothing_on_its_own_axis():
    # Twice the cut-off or beyond: the reaction half is zero, so only the
    # recovery half remains — three quarters of the scale.
    cut = settings.dynamics.reactivity_threshold_pct
    assert resilience_index(2 * cut, 100.0) == 3.8
    assert resilience_index(10 * cut, 100.0) == 3.8


def test_coming_back_outweighs_reacting_hard():
    """
    The correction of 18 September 2026. With equal weights, the two archived
    pilot sessions — RMSSD down 51% and 59%, recovery 65% and 99%, both called
    "responsive but flexible" by the quadrant — scored 1.6 and 2.5 of 5, which
    reads as poor resilience for a profile the module had just called healthy.

    Reacting hard may cost a session at most a quarter of the scale; the rest is
    decided by how much came back.
    """
    cut = settings.dynamics.reactivity_threshold_pct
    tenang = resilience_index(0.0, 60.0)
    keras = resilience_index(10 * cut, 60.0)

    # Same recovery, reaction from nothing to far past the cut-off: the whole
    # difference is the reaction quarter, 1.25 before the figures are rounded to
    # the one decimal they are displayed at.
    assert (tenang, keras) == (3.5, 2.2)
    # And the sessions that started this: no longer at the bottom of the scale.
    assert resilience_index(-51.3, 64.7) == 2.4
    assert resilience_index(-59.4, 99.2) == 3.7


def test_the_sign_of_the_reaction_does_not_change_the_figure():
    """RMSSD falls for most people and rises for some; the size is what is judged."""
    cut = settings.dynamics.reactivity_threshold_pct
    assert resilience_index(cut, 60.0) == resilience_index(-cut, 60.0)


def test_resilience_is_missing_exactly_when_the_quadrant_would_be():
    assert resilience_index(-30.0, None) is None
    assert resilience_index(float("nan"), 70.0) is None


def test_the_scale_never_produces_a_number_outside_itself():
    cut = settings.dynamics.reactivity_threshold_pct
    for reactivity in (-500.0, -cut, 0.0, cut, 500.0):
        for recovery in (-80.0, 0.0, 55.0, 100.0, 400.0):
            nilai = resilience_index(reactivity, recovery)
            assert nilai is not None and not math.isnan(nilai)
            assert 0.0 <= nilai <= settings.indices.scale_max
