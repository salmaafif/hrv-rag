"""
U1.6 — Personal baseline and reactivity.

The most important test in this file: a segment whose values match the baseline
exactly MUST yield 0% reactivity. If it does not, every reactivity figure in the
project is systematically shifted.
"""

import numpy as np
import pandas as pd
import pytest

from hrv_rag.features.baseline import (BaselineEvidence, BaselineProfile,
                                       check_baseline)


@pytest.fixture
def calibration() -> pd.DataFrame:
    """
    Synthetic calibration feature table with an easily computed median.

    RMSSD = [40, 45, 50, 55, 60] -> median 50 (the middle value)
    """
    return pd.DataFrame({
        "rmssd": [40.0, 45.0, 50.0, 55.0, 60.0],
        "sdnn": [50.0, 55.0, 60.0, 65.0, 70.0],
        "mean_hr": [70.0, 70.0, 70.0, 70.0, 70.0],
    })


def test_baseline_uses_median(calibration):
    profile = BaselineProfile.from_segments("TEST", calibration)
    assert profile.values["rmssd"] == pytest.approx(50.0)


def test_median_resists_outliers(calibration):
    """
    Why the median is used instead of the mean.

    One noisy segment with RMSSD 500 ms drags the mean from 50 to 125 — a 150%
    distortion. The median only moves from 50 to 52.5, about 5%. Since every
    reactivity figure is divided by this reference, its stability determines the
    stability of every result downstream.

    The value 52.5 arises because with six data points the median is the average of
    the two middle values: (50 + 55) / 2.
    """
    dirty = pd.concat([calibration, pd.DataFrame({"rmssd": [500.0]})],
                      ignore_index=True)
    profile = BaselineProfile.from_segments("TEST", dirty)
    assert profile.values["rmssd"] == pytest.approx(52.5)
    assert dirty["rmssd"].mean() == pytest.approx(125.0)   # the mean is ruined


def test_reactivity_zero_when_equal_to_baseline(calibration):
    """THE KEY SANITY CHECK — identical values must give 0%."""
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 50.0, "sdnn": 60.0, "mean_hr": 70.0})
    assert result["delta_pct_rmssd"] == pytest.approx(0.0)
    assert result["delta_pct_sdnn"] == pytest.approx(0.0)


def test_reactivity_negative_when_lower(calibration):
    """RMSSD of 25 against a reference of 50 is a 50% drop."""
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 25.0})
    assert result["delta_pct_rmssd"] == pytest.approx(-50.0)


def test_reactivity_positive_when_higher(calibration):
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 75.0})
    assert result["delta_pct_rmssd"] == pytest.approx(50.0)


def test_reactivity_does_not_fuse_features(calibration):
    """
    The code produces reactivity PER FEATURE only — there is no combined score
    column. Fusing them is the LLM's job, working from the knowledge base. If the
    code did the fusing, the LLM would merely be reading a threshold and the RAG
    approach would lose its reason to exist.
    """
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": 25.0, "sdnn": 30.0, "mean_hr": 90.0})
    assert all(k.startswith("delta_pct_") for k in result)


def test_empty_calibration_rejected():
    """
    Without calibration segments no baseline can be built, and every reactivity
    figure becomes meaningless. Failing loudly beats silently using an arbitrary
    number.
    """
    with pytest.raises(ValueError, match="no baseline can be built"):
        BaselineProfile.from_segments("TEST", pd.DataFrame())


def test_spread_flags_unsteady_baseline(calibration):
    """
    Relative IQR serves as a warning flag. On the real WESAD data, S10 produced 52%
    — far above the other subjects at 14-17% — and S10 was also the subject whose
    response pattern turned out inverted.
    """
    profile = BaselineProfile.from_segments("TEST", calibration)
    # RMSSD [40..60]: quartiles 45 and 55 -> IQR 10, reference 50 -> 20%
    assert profile.relative_spread("rmssd") == pytest.approx(0.20)


def test_nan_feature_does_not_crash(calibration):
    profile = BaselineProfile.from_segments("TEST", calibration)
    result = profile.reactivity({"rmssd": np.nan})
    assert np.isnan(result["delta_pct_rmssd"])


# ----------------------------------------------- resting-phase sampling
def test_baseline_samples_the_resting_period_more_densely(make_series):
    """
    `from_series` uses the finer resting hop; `extract_features` does not.

    That split is the whole point, and getting it wrong is silent. Applying the
    finer hop inside `extract_features` looks harmless — but on WESAD the resting
    rows are ALSO the low-stress class the system is scored against, so doubling
    them doubled one side of the classification set and moved macro-F1 from 0.851
    to 0.797 without a single measurement having changed.

    Two jobs, two sampling rates: the baseline wants the steadiest central value
    it can extract from a short recording, the classification set wants segments
    as independent as the design allows.
    """
    from hrv_rag.core.types import Phase
    from hrv_rag.features.extractor import extract_features

    resting = make_series(n_beats=241, phase=Phase.CALIBRATION)   # 240 s

    table, _ = extract_features(resting)
    profile = BaselineProfile.from_series("TEST", resting)

    # 240 s: hop 30 gives 7 windows, hop 15 gives 13.
    assert len(table) == 7
    assert profile.n_segments == 13


def test_task_phase_is_not_sampled_densely(make_series):
    from hrv_rag.core.types import Phase
    from hrv_rag.features.extractor import extract_features

    table, _ = extract_features(make_series(n_beats=241, phase=Phase.QUESTION))
    assert len(table) == 7


def test_one_minute_of_rest_yields_no_baseline_at_all(make_series):
    """
    The hard floor, and the reason the resting period cannot be shortened to a
    minute however much anyone would like it to be.

    Features are computed over 60-second windows, and 60 seconds of beats spans
    only about 59 seconds — measured first beat to last, not from when the timer
    started. Nothing fits. The result is not a weaker baseline but NO baseline,
    which leaves the whole session unscoreable, because every number this system
    reports is a change relative to the person's own quiet state.

    A finer hop does not rescue it: zero windows stay zero.
    """
    from hrv_rag.core.types import Phase

    one_minute = make_series(n_beats=60, rr_value=1000.0, phase=Phase.CALIBRATION)
    with pytest.raises(ValueError, match="no baseline can be built"):
        BaselineProfile.from_series("TEST", one_minute)


def test_two_minutes_of_rest_does_yield_a_baseline(make_series):
    """Two minutes is the floor that works, and only with the finer hop."""
    from hrv_rag.core.types import Phase

    two_minutes = make_series(n_beats=120, rr_value=1000.0, phase=Phase.CALIBRATION)
    profile = BaselineProfile.from_series("TEST", two_minutes)
    assert profile.n_segments >= 2


def test_configured_resting_duration_actually_produces_a_baseline(make_series):
    """
    Guards the setting itself, not just the code that reads it.

    `SessionConfig.calibration_sec` has been shortened three times for the sake of
    the person waiting, and each cut brought it nearer the floor. Below two
    minutes it stops producing any windows at all — silently, since a shorter wait
    looks like an improvement right up until the analysis has nothing to divide
    by. This runs the configured duration through the real segmentation and fails
    if it yields nothing.
    """
    from hrv_rag.config.settings import settings
    from hrv_rag.core.types import Phase

    seconds = settings.session.calibration_sec
    resting = make_series(n_beats=seconds, rr_value=1000.0,
                          phase=Phase.CALIBRATION)

    profile = BaselineProfile.from_series("TEST", resting)
    assert profile.n_segments >= 2, (
        f"calibration_sec={seconds} yields only {profile.n_segments} window(s); "
        f"the median needs at least two to reject a noisy one"
    )


# ------------------------------------------------- the baseline quality gate
def profile_with(rmssd: list[float], hr: float) -> BaselineProfile:
    """A baseline whose spread and resting heart rate are both dictated."""
    return BaselineProfile.from_segments("TEST", pd.DataFrame({
        "rmssd": rmssd,
        "mean_hr": [hr] * len(rmssd),
    }))


def test_a_steady_resting_period_passes():
    """Twelve windows, because four would now also draw a thin-evidence note."""
    verdict = check_baseline(profile_with([49.0, 50.0, 50.0, 51.0] * 3, hr=68.0))

    assert verdict.is_acceptable
    assert verdict.reasons == []
    assert verdict.note_for_user() == "" and verdict.note_for_model() == ""


def test_the_spread_threshold_sits_where_it_was_calibrated():
    """
    0.35 — swept across the prelude lengths production actually produces, not the
    0.40 guess that was here before and not the 0.20 that a two-minutes-only sweep
    suggested. Boundary checked from both sides, because a `>=` written where `>`
    belongs would turn every exactly-at-threshold baseline away and nothing else
    would notice.
    """
    # RMSSD [30, 40, 60, 70]: quartiles 37.5 and 62.5 -> IQR 25, median 50.
    over = check_baseline(profile_with([30.0, 40.0, 60.0, 70.0], hr=68.0))
    assert over.relative_spread == pytest.approx(0.50)
    assert not over.is_acceptable

    # Exactly 0.35 is still acceptable. [30, 45, 55, 70]: IQR 17.5, median 50.
    at_threshold = check_baseline(profile_with([30.0, 45.0, 55.0, 70.0], hr=68.0))
    assert at_threshold.relative_spread == pytest.approx(0.35)
    assert at_threshold.is_acceptable

    # And a spread that only a TWO-MINUTE sweep would have refused now passes,
    # deliberately: twelve windows disagree more than four do without being worse.
    assert check_baseline(profile_with([40.0, 45.0, 55.0, 60.0], hr=68.0)
                          ).is_acceptable


def test_a_perfectly_steady_but_racing_baseline_is_still_refused():
    """
    The check spread cannot make. Someone who never settled has a HIGH resting
    heart rate, and a steadily elevated heart rate is perfectly steady — zero
    spread, and completely unusable.

    This is WESAD S10: 99 bpm while sitting still, and its two-minute baselines
    landed 34% away from the subject's own true resting value, the worst of all
    fifteen. Spread alone would have waved it through.
    """
    verdict = check_baseline(profile_with([50.0] * 5, hr=99.0))

    assert verdict.relative_spread == pytest.approx(0.0)
    assert not verdict.is_acceptable
    assert any("resting heart rate" in r for r in verdict.reasons)


def test_both_faults_are_reported_not_just_the_first():
    """A person told only half of what is wrong fixes half of it."""
    verdict = check_baseline(profile_with([30.0, 40.0, 60.0, 70.0], hr=99.0))

    assert len(verdict.reasons) == 2


def test_a_single_window_cannot_look_unsteady_and_is_not_refused():
    """
    One window has nothing to disagree with, so its interquartile range is zero and
    the spread check can never fire — it passes for lack of evidence, not because
    the baseline was shown to be good.

    Worth pinning down, because it is where the gate is blindest. The heart-rate
    check still applies, and on a two-minute rest it is the only one that can.
    """
    verdict = check_baseline(profile_with([50.0], hr=68.0))

    assert verdict.relative_spread == pytest.approx(0.0)
    assert verdict.is_acceptable
    assert not check_baseline(profile_with([50.0], hr=99.0)).is_acceptable


def test_a_missing_feature_is_not_treated_as_a_fault():
    """
    No RMSSD at all — a PPG recording too noisy to yield one, say. The spread is
    then unmeasurable rather than bad, and refusing on it would send somebody to
    redo a resting period that was never the problem.
    """
    profile = BaselineProfile.from_segments("TEST", pd.DataFrame({
        "mean_hr": [68.0, 68.0, 68.0],
    }))
    verdict = check_baseline(profile)

    assert verdict.relative_spread != verdict.relative_spread     # NaN
    assert verdict.is_acceptable


def test_the_user_never_sees_the_technical_wording():
    """
    Decision K4: the note travels into an API response and onto a screen. The
    model's version names interquartile ranges and beats per minute; the user's
    version must name neither.
    """
    verdict = check_baseline(profile_with([30.0, 40.0, 60.0, 70.0], hr=99.0))

    for term in ("IQR", "bpm", "RMSSD", "heart rate", "%"):
        assert term not in verdict.note_for_user()
    assert "IQR" in verdict.note_for_model()


def test_every_caller_reads_the_same_threshold():
    """
    The comparison used to be written out in four files. The failure that arrangement
    invites is not a crash: three copies keep an old number, and the offline report
    and the API then hand the SAME recording two different verdicts.

    Moving the threshold must therefore move every caller at once.
    """
    from dataclasses import replace

    from hrv_rag.config.settings import settings

    borderline = profile_with([30.0, 40.0, 60.0, 70.0], hr=68.0)   # spread 0.50
    assert not check_baseline(borderline).is_acceptable

    loosened = replace(settings.baseline_gate, max_relative_spread=0.60)
    assert check_baseline(borderline, cfg=loosened).is_acceptable


# --------------------------------------------- how much evidence there was
def profile_of_size(n_windows: int) -> BaselineProfile:
    """A perfectly steady baseline built from `n_windows` resting windows."""
    return BaselineProfile.from_segments("TEST", pd.DataFrame({
        "rmssd": [50.0] * n_windows,
        "mean_hr": [68.0] * n_windows,
    }))


@pytest.mark.parametrize("n_windows,expected", [
    (4, BaselineEvidence.MINIMAL),      # pressed start the instant it paired
    (5, BaselineEvidence.MINIMAL),
    (6, BaselineEvidence.LIMITED),
    (9, BaselineEvidence.LIMITED),
    (10, BaselineEvidence.FULL),        # sensor connected a couple of minutes early
    (12, BaselineEvidence.FULL),
])
def test_evidence_follows_how_much_resting_recording_there_was(n_windows, expected):
    assert check_baseline(profile_of_size(n_windows)).evidence is expected


def test_a_thin_baseline_is_reported_but_never_refused():
    """
    The whole point of separating these two. A short resting period is not a faulty
    one, and refusing on it would send somebody to redo minutes that may have been
    perfectly good — while saying nothing would hand them a report resting on four
    windows as though it rested on twelve.

    Measured on WESAD: under six windows, 11.8% of sessions carry a baseline off by
    more than the rule's own threshold with nothing flagged, against 3.9% at ten or
    more.
    """
    thin = check_baseline(profile_of_size(4))

    assert thin.is_acceptable          # not refused
    assert thin.is_thin                # but not silent either
    assert thin.note_for_user() != ""
    assert "4 resting windows" in thin.note_for_model()


def test_a_full_baseline_says_nothing_at_all():
    """A caveat printed on every session is a caveat nobody reads."""
    verdict = check_baseline(profile_of_size(12))

    assert verdict.evidence is BaselineEvidence.FULL
    assert not verdict.is_thin
    assert verdict.note_for_user() == "" and verdict.note_for_model() == ""


def test_thin_evidence_and_an_unsteady_baseline_are_both_said():
    """
    Two independent faults. Reporting only the first would leave the person fixing
    half of what went wrong.
    """
    profile = BaselineProfile.from_segments("TEST", pd.DataFrame({
        "rmssd": [30.0, 40.0, 60.0, 70.0],      # spread 0.50
        "mean_hr": [99.0] * 4,                  # not at rest
    }))
    verdict = check_baseline(profile)

    assert not verdict.is_acceptable and verdict.is_thin
    note = verdict.note_for_model()
    assert "unsteady" in note and "4 resting windows" in note


def test_the_evidence_wording_shown_to_a_user_stays_plain():
    """Decision K4 again: this string reaches a screen."""
    note = check_baseline(profile_of_size(4)).note_for_user()

    for term in ("window", "jendela", "RMSSD", "IQR", "bpm", "%"):
        assert term not in note
