"""
Tests for the rule that assigns the stress label.

This rule, not the LLM, decides what the user is told. It therefore has to be
correct and it has to be stable — the same recording must always produce the same
label. Both properties are locked in here.
"""

import pytest

from hrv_rag.config.settings import settings
from hrv_rag.core.schemas import StressLevel
from hrv_rag.features.stress_level import classify

#: Read the thresholds rather than hard-coding them.
#:
#: These values are calibrated against data and will move again when a dataset with
#: a genuine middle condition arrives. Tests that memorised the numbers would break
#: on every recalibration while proving nothing about the behaviour — the point is
#: that a moderate move scores a point, not that the boundary sits at exactly -20%.
CFG = settings.stress_rule


def r(rmssd: float = float("nan"), hr: float = float("nan")) -> dict:
    """Shorthand for a reactivity dict."""
    return {"delta_pct_rmssd": rmssd, "delta_pct_mean_hr": hr}


def just_past(threshold: float) -> float:
    """A value one unit beyond a threshold, on whichever side it points."""
    return threshold - 1.0 if threshold < 0 else threshold + 1.0


# ----------------------------------------------------------------- levels
def test_no_change_is_low():
    """Both features flat means no stress response to report."""
    v = classify(r(rmssd=-2.0, hr=1.0))
    assert v.level is StressLevel.LOW
    assert v.points == 0


def test_both_features_strong_is_high():
    """RMSSD far down and heart rate far up: the textbook stress response."""
    v = classify(r(rmssd=-45.0, hr=25.0))
    assert v.level is StressLevel.HIGH
    assert v.points == 4


def test_both_features_mild_is_moderate():
    """Both features just past the moderate line: one point each, so moderate."""
    v = classify(r(rmssd=just_past(CFG.rmssd_moderate_pct),
                   hr=just_past(CFG.hr_moderate_pct)))
    assert v.level is StressLevel.MODERATE
    assert v.points == 2


def test_one_feature_strong_reaches_high():
    """
    Two points from one feature plus one from the other reaches the high threshold.
    Deliberate: a large move in RMSSD should not be discounted just because heart
    rate moved only moderately.
    """
    v = classify(r(rmssd=-40.0, hr=7.0))
    assert v.points == 3
    assert v.level is StressLevel.HIGH


def test_single_feature_alone_stays_moderate():
    """One feature moving while the other is flat is not enough to call it high."""
    v = classify(r(rmssd=-40.0, hr=0.0))
    assert v.points == 2
    assert v.level is StressLevel.MODERATE


# ------------------------------------------------- the inverted pattern
def test_inverted_pattern_still_registers():
    """
    THE CASE THAT MATTERS. Subjects S6 and S10 showed RMSSD RISING under TSST while
    heart rate also rose.

    Reading RMSSD alone would call this "no stress" and reassure the user falsely.
    Because heart rate is scored too, the verdict lands on moderate instead.
    """
    v = classify(r(rmssd=59.0, hr=11.0))
    assert v.level is StressLevel.MODERATE
    assert any("disagree" in e for e in v.evidence)


def test_disagreement_is_reported_in_evidence():
    """The conflict must be stated, not smoothed over — the narrative relies on it."""
    v = classify(r(rmssd=30.0, hr=12.0))
    assert any("speaking can cause" in e for e in v.evidence)


def test_genuine_calm_is_not_flagged_as_disagreement():
    """RMSSD up with heart rate DOWN is simply a calm state, not a conflict."""
    v = classify(r(rmssd=25.0, hr=-5.0))
    assert v.level is StressLevel.LOW
    assert not any("disagree" in e for e in v.evidence)


# ------------------------------------------------------------ robustness
def test_missing_feature_scores_nothing():
    """A feature that was never measured contributes no points, and does not crash."""
    v = classify(r(hr=20.0))
    assert v.points == 2
    assert v.level is StressLevel.MODERATE


def test_no_measurement_at_all_is_low_with_a_note():
    v = classify({})
    assert v.level is StressLevel.LOW
    assert "no usable measurement" in v.evidence[0]


def test_same_input_always_gives_same_label():
    """
    Determinism, stated as a test.

    This is the property the rule exists for. A label that wandered between runs
    could not honestly be shown to a user, and it is what disqualified the LLM from
    this job.
    """
    reactivity = r(rmssd=-33.0, hr=12.0)
    verdicts = [classify(reactivity) for _ in range(20)]
    assert len({v.level for v in verdicts}) == 1
    assert len({v.points for v in verdicts}) == 1


def test_evidence_is_human_readable():
    """The evidence carries the explanation into the prompt, so it must read well."""
    v = classify(r(rmssd=-35.0, hr=18.0))
    text = v.describe()
    assert "RMSSD" in text and "heart rate" in text
    assert "high" in text


def test_boundaries_are_inclusive():
    """
    A value sitting exactly on a threshold counts as having reached it.

    Read from the configuration so the rule survives recalibration: what is being
    locked in is the inclusive comparison, not any particular number.
    """
    on_high = classify(r(rmssd=CFG.rmssd_high_pct, hr=CFG.hr_high_pct))
    assert on_high.level is StressLevel.HIGH
    assert on_high.points == 4

    on_moderate = classify(r(rmssd=CFG.rmssd_moderate_pct,
                             hr=CFG.hr_moderate_pct))
    assert on_moderate.points == 2
    assert on_moderate.level is StressLevel.MODERATE


def test_just_inside_the_flat_zone_is_low():
    """A hair short of the moderate threshold scores nothing."""
    v = classify(r(rmssd=CFG.rmssd_moderate_pct + 0.1,
                   hr=CFG.hr_moderate_pct - 0.1))
    assert v.points == 0
    assert v.level is StressLevel.LOW
