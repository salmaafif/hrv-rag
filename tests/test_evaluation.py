"""
Tests for the layer that turns assessments into the numbers reported in the thesis.

`evaluation/` had no tests. That was demonstrated rather than assumed: mutating
macro-F1 into micro-F1, counting abstentions as answers, and flipping the WESAD
ground-truth mapping so TSST meant "low" all left the suite green. Any one of
those would have put a wrong headline figure into the report with nothing to catch
it.

These cover the claims the report actually makes, and none of them need an API key.
"""

import pytest

from hrv_rag.evaluation.cache import cache_key
from hrv_rag.evaluation.labels import (EvaluationRecord, TrueLabel,
                                       predicted_label, true_label)
from hrv_rag.evaluation.metrics import (evaluate_classification,
                                        paired_difference_ci)
from hrv_rag.evaluation.rag_metrics import FaithfulnessReport
from hrv_rag.evaluation.rule_baseline import (rule_hr_only, rule_rmssd_and_hr,
                                              rule_rmssd_only)


def record(truth: TrueLabel, predicted: TrueLabel | None,
           subject: str = "S2") -> EvaluationRecord:
    return EvaluationRecord(
        subject=subject, phase="question", segment=1, modality="ECG",
        truth=truth, predicted=predicted,
        raw_level="uncertain" if predicted is None else predicted.value,
        confidence=0.8, references=[], retrieved_ids=[], reasoning="",
        is_trustworthy=True,
    )


# ----------------------------------------------------------- ground truth
def test_wesad_phases_map_to_the_right_direction():
    """
    TSST is the stressor and the resting phase is the reference.

    Inverting these would invert every metric in the thesis while leaving the
    numbers looking perfectly reasonable.
    """
    assert true_label("question") is TrueLabel.HIGH
    assert true_label("calibration") is TrueLabel.LOW


def test_amusement_carries_no_label():
    """Positive arousal is deliberately excluded, not folded into either class."""
    assert true_label("amusement") is None


@pytest.mark.parametrize("level,expected", [
    ("low", TrueLabel.LOW),
    ("moderate", TrueLabel.HIGH),
    ("high", TrueLabel.HIGH),
])
def test_three_way_output_collapses_onto_binary_truth(level, expected):
    """WESAD is binary, so "moderate" has to land on the stressed side."""
    assert predicted_label(level) is expected


def test_uncertain_is_an_abstention_not_a_prediction():
    """
    Abstaining is a legitimate answer and must not be scored as a wrong one.

    Counted as a prediction it would be marked incorrect roughly half the time,
    penalising the model for the one honest thing it can do without data.
    """
    assert predicted_label("uncertain") is None


# --------------------------------------------------------------- metrics
def test_abstentions_are_excluded_from_accuracy_but_reported():
    records = [
        record(TrueLabel.HIGH, TrueLabel.HIGH),
        record(TrueLabel.LOW, TrueLabel.LOW),
        record(TrueLabel.HIGH, None),
    ]
    report = evaluate_classification(records)

    assert report.n_total == 3
    assert report.n_evaluated == 2
    assert report.n_abstained == 1
    assert report.accuracy == pytest.approx(1.0)


def test_macro_f1_weights_classes_equally():
    """
    Macro, not micro. With unbalanced classes the two diverge, and micro-F1 would
    let the majority class carry the score.

    Nine LOW all correct, three HIGH all wrong: micro-averaging reports 0.75,
    macro-averaging reports the honest 0.43.
    """
    records = ([record(TrueLabel.LOW, TrueLabel.LOW)] * 9
               + [record(TrueLabel.HIGH, TrueLabel.LOW)] * 3)
    report = evaluate_classification(records)

    assert report.accuracy == pytest.approx(0.75)
    assert report.macro_f1 == pytest.approx(0.4286, abs=0.001)
    assert report.per_class_f1["high"] == pytest.approx(0.0)


def test_a_sample_missing_one_class_says_so():
    """
    An absent class scores F1 = 0 and halves macro-F1, which reads as a broken
    system rather than a lopsided sample.

    This is not hypothetical: the free tier allows 20 calls a day and a full run
    walks the CSV in order, so the first day sees resting segments only. Without
    the note it would print macro-F1 0.50 after answering all 20 correctly.
    """
    records = [record(TrueLabel.LOW, TrueLabel.LOW)] * 5
    report = evaluate_classification(records)

    assert report.accuracy == pytest.approx(1.0)
    assert any("absent" in note for note in report.notes)


def test_abstaining_on_everything_does_not_crash():
    report = evaluate_classification([record(TrueLabel.HIGH, None)])
    assert report.n_evaluated == 0
    assert any("abstained" in note for note in report.notes)


# ------------------------------------------------- confidence interval
def subject_rows(subject: str, n: int, correct: bool) -> list[EvaluationRecord]:
    """`n` LOW and `n` HIGH segments for one person, all right or all wrong."""
    rows = []
    for truth in (TrueLabel.LOW, TrueLabel.HIGH):
        other = TrueLabel.HIGH if truth is TrueLabel.LOW else TrueLabel.LOW
        rows += [record(truth, truth if correct else other, subject=subject)] * n
    return rows


def test_interval_brackets_the_point_estimate():
    records = [r for i in range(6)
               for r in subject_rows(f"S{i}", 10, correct=i < 4)]
    report = evaluate_classification(records, n_resamples=400)

    assert report.macro_f1_ci is not None
    assert report.macro_f1_ci.n_clusters == 6
    assert report.macro_f1_ci.low <= report.macro_f1 <= report.macro_f1_ci.high


def test_the_interval_resamples_subjects_and_not_rows():
    """
    The whole point of the interval, and the one thing that can silently be wrong.

    Five people read perfectly and five read backwards. Drawing ROWS with
    replacement keeps that fifty-fifty mixture in every resample, so the score
    barely moves and the interval comes out narrow — measured at 0.09 wide. Drawing
    PEOPLE can hand you eight good ones or two, which is the question actually being
    asked: what if the study had recruited differently. That interval is 0.4 wide or
    more.

    A row-level bootstrap would still return a plausible-looking interval, printed
    to three decimals, and nothing else in the suite would notice. Hence the
    generous margin here: it passes only for a bootstrap clustered on subjects.
    """
    records = [r for i in range(10)
               for r in subject_rows(f"S{i}", 12, correct=i < 5)]
    report = evaluate_classification(records, n_resamples=1000)

    assert report.macro_f1_ci is not None
    width = report.macro_f1_ci.high - report.macro_f1_ci.low
    assert width > 0.35, f"interval only {width:.3f} wide — resampling rows?"


def graded_subject(subject: str, n: int, n_wrong: int) -> list[EvaluationRecord]:
    """One person with `n_wrong` of their `n` segments misread, in each class."""
    rows = []
    for truth in (TrueLabel.LOW, TrueLabel.HIGH):
        other = TrueLabel.HIGH if truth is TrueLabel.LOW else TrueLabel.LOW
        rows += ([record(truth, other, subject=subject)] * n_wrong
                 + [record(truth, truth, subject=subject)] * (n - n_wrong))
    return rows


def test_the_same_records_always_give_the_same_interval():
    """
    A seed is fixed on purpose. An interval that moved between two runs of an
    unchanged evaluation could not be told apart from a change in the system.

    Twelve people of DIFFERENT ability, not the all-good-or-all-bad split used
    above. That matters for what this test can detect: when every subject scores
    the same, resamples land on a handful of values and both percentiles sit on the
    same one whatever the seed — so an unseeded bootstrap would pass. Spreading the
    ability out gives the distribution enough distinct values that six seeds produce
    five different intervals, and only a fixed seed returns the same one twice.
    """
    records = [r for i in range(12) for r in graded_subject(f"S{i}", 10, i % 6)]
    first = evaluate_classification(records, n_resamples=200).macro_f1_ci
    second = evaluate_classification(records, n_resamples=200).macro_f1_ci

    assert first == second


def test_one_subject_gets_no_interval_rather_than_a_fake_one():
    """
    Resampling one person measures how repeatable that person is, not how the
    system would fare on somebody else — but it returns a narrow, confident-looking
    interval all the same. Refusing is the honest answer.
    """
    report = evaluate_classification(subject_rows("S2", 10, correct=True))

    assert report.macro_f1_ci is None
    assert any("1 subject" in note for note in report.notes)


def test_the_bootstrap_can_be_switched_off():
    records = [r for i in range(4) for r in subject_rows(f"S{i}", 5, correct=True)]
    assert evaluate_classification(records, n_resamples=0).macro_f1_ci is None


def test_resamples_holding_one_class_are_dropped_not_scored_as_zero():
    """
    A resample can miss a class outright — every subject it drew contributed
    resting segments only. Macro-F1 then averages an F1 over a class that is not
    there, scores 0.5, and drags the lower bound down by half.

    Here all three people are classified perfectly, so every honest resample scores
    1.000. Only the draws of three-times-the-LOW-only-person and
    three-times-the-HIGH-only-person can score anything else, and they are dropped.
    A lower bound of 0.5 means they were not.
    """
    low_only = [record(TrueLabel.LOW, TrueLabel.LOW, subject="S1")] * 10
    high_only = [record(TrueLabel.HIGH, TrueLabel.HIGH, subject="S2")] * 10
    both = subject_rows("S3", 5, correct=True)

    report = evaluate_classification(low_only + high_only + both,
                                     n_resamples=600)

    assert report.macro_f1 == pytest.approx(1.0)
    assert report.macro_f1_ci is not None
    assert report.macro_f1_ci.low == pytest.approx(1.0)
    assert report.macro_f1_ci.n_resamples < 600
    assert any("one class" in note for note in report.notes)


def test_the_interval_is_printed_beside_the_number_it_qualifies():
    """A CI computed but not shown would be a CI nobody reports."""
    records = [r for i in range(5)
               for r in subject_rows(f"S{i}", 8, correct=i < 3)]
    summary = evaluate_classification(records, n_resamples=300).summary()

    macro_line = next(l for l in summary.splitlines() if "macro-F1" in l)
    assert "95%" in macro_line and "subjects" in macro_line


def test_kappa_gets_its_own_interval_not_a_copy_of_the_f1_one():
    """
    Kappa and macro-F1 are different statistics on the same draws, so their
    intervals must differ. Handing kappa the F1 interval would look right in every
    printout and be wrong in every report.
    """
    records = [r for i in range(8) for r in graded_subject(f"S{i}", 10, i % 4)]
    report = evaluate_classification(records, n_resamples=400)

    assert report.kappa_ci is not None
    assert report.kappa_ci.low <= report.kappa <= report.kappa_ci.high
    assert (report.kappa_ci.low, report.kappa_ci.high) != (
        report.macro_f1_ci.low, report.macro_f1_ci.high)

    kappa_line = next(l for l in report.summary().splitlines() if "kappa" in l)
    assert "95%" in kappa_line


# --------------------------------------------- paired system comparison
def test_a_system_that_never_loses_gets_an_interval_clear_of_zero():
    """
    The comparison the thesis actually makes. Every subject improves, so no
    resample of those subjects can average to zero.
    """
    rule = {"S3": 0.90, "S4": 0.78, "S5": 0.96, "S7": 0.86, "S8": 0.82}
    cnn = {"S3": 0.96, "S4": 0.85, "S5": 0.96, "S7": 0.86, "S8": 0.92}

    interval, notes = paired_difference_ci(rule, cnn, n_resamples=500)

    assert interval is not None and notes == []
    assert interval.low > 0.0
    assert interval.low <= 0.038 <= interval.high      # mean of the five deltas


def test_two_identical_systems_produce_a_difference_of_exactly_zero():
    scores = {"S3": 0.90, "S4": 0.78, "S5": 0.96}
    interval, _ = paired_difference_ci(scores, dict(scores), n_resamples=200)

    assert interval is not None
    assert interval.low == pytest.approx(0.0) and interval.high == pytest.approx(0.0)


def test_the_paired_interval_resamples_subjects():
    """
    Mixed wins and losses of the same size average to zero, but a resample can draw
    mostly winners or mostly losers — so the interval must have real width. Width
    zero means the subjects were never redrawn.
    """
    rule = {f"S{i}": 0.80 for i in range(8)}
    cnn = {f"S{i}": 0.80 + (0.15 if i % 2 else -0.15) for i in range(8)}

    interval, _ = paired_difference_ci(rule, cnn, n_resamples=800)

    assert interval is not None
    assert interval.high - interval.low > 0.10
    assert interval.low < 0.0 < interval.high


def test_a_subject_only_one_side_scored_is_left_out_and_named():
    """
    Counting a missing subject as a zero difference would pull the estimate toward
    "no effect" using a measurement that was never taken.
    """
    rule = {"S3": 0.90, "S4": 0.70, "S9": 0.60}
    cnn = {"S3": 0.96, "S4": 0.76}

    interval, notes = paired_difference_ci(rule, cnn, n_resamples=200)

    assert interval is not None
    assert interval.n_clusters == 2
    assert interval.low > 0.0                       # S9 did not dilute it
    assert any("S9" in note for note in notes)


def test_one_shared_subject_is_not_enough_for_a_difference():
    interval, notes = paired_difference_ci({"S3": 0.9}, {"S3": 0.8}, n_resamples=200)

    assert interval is None
    assert any("1 subject in common" in note for note in notes)


def test_the_paired_interval_is_reproducible():
    rule = {f"S{i}": 0.60 + 0.03 * i for i in range(9)}
    cnn = {f"S{i}": 0.60 + 0.03 * i + 0.01 * (i % 4) for i in range(9)}

    first, _ = paired_difference_ci(rule, cnn, n_resamples=300)
    second, _ = paired_difference_ci(rule, cnn, n_resamples=300)

    assert first == second


# -------------------------------------------------------- rule comparator
def test_two_feature_rule_is_a_disjunction():
    """
    RMSSD OR heart rate, not AND.

    Two of the five development subjects show RMSSD RISING under stress while
    heart rate rises in all five. Requiring both would miss those subjects
    entirely — which is the whole reason the second feature is there.
    """
    only_hr = {"delta_pct_rmssd": +5.0, "delta_pct_mean_hr": +25.0}
    only_rmssd = {"delta_pct_rmssd": -35.0, "delta_pct_mean_hr": +1.0}

    assert rule_rmssd_and_hr(only_hr) is TrueLabel.HIGH
    assert rule_rmssd_and_hr(only_rmssd) is TrueLabel.HIGH


def test_single_feature_rule_ignores_heart_rate():
    """The comparator's whole point is being weaker; that has to stay true."""
    assert rule_rmssd_only({"delta_pct_rmssd": +5.0,
                            "delta_pct_mean_hr": +25.0}) is TrueLabel.LOW


def test_rule_reports_low_when_nothing_moved():
    assert rule_rmssd_and_hr({"delta_pct_rmssd": 0.0,
                              "delta_pct_mean_hr": 0.0}) is TrueLabel.LOW


def test_hr_only_rule_ignores_rmssd():
    """
    Ablation #9's whole point: this rule must not see the feature a PPG armband
    cannot deliver reliably. A steep RMSSD drop alone must not flip it to HIGH.
    """
    assert rule_hr_only({"delta_pct_rmssd": -35.0,
                         "delta_pct_mean_hr": +1.0}) is TrueLabel.LOW


def test_hr_only_rule_fires_on_heart_rate_alone():
    assert rule_hr_only({"delta_pct_rmssd": +5.0,
                         "delta_pct_mean_hr": +25.0}) is TrueLabel.HIGH


def test_hr_only_rule_abstains_low_when_hr_missing():
    assert rule_hr_only({"delta_pct_rmssd": -35.0}) is TrueLabel.LOW


# ---------------------------------------------------------- faithfulness
def test_clean_rate_counts_assessments_not_violations():
    """
    An output that both invents a number and fabricates a citation is still ONE
    bad output.

    Adding the two counters double-counted it, and clipping the resulting negative
    to zero hid the symptom: ten assessments of which six broke both rules were
    reported as 0% clean when four were spotless.
    """
    report = FaithfulnessReport(
        n_total=10, n_cited_nothing=0,
        n_unknown_reference=6, n_invented_number=6, n_violating=6,
    )
    assert report.clean_rate == pytest.approx(0.4)


def test_clean_rate_is_one_when_nothing_violated():
    report = FaithfulnessReport(n_total=4, n_cited_nothing=1,
                               n_unknown_reference=0, n_invented_number=0)
    assert report.clean_rate == pytest.approx(1.0)


# ----------------------------------------------------------------- cache
def test_cache_distinguishes_the_two_modalities():
    """
    WESAD is the reason this matters: the same subject, phase and 60 seconds exist
    twice, once as ECG and once as PPG.

    Without modality in the key they collide, so asking for the PPG assessment
    returns the stored ECG one — and the paired comparison in T6.4 would be ECG
    measured against itself, reporting agreement that was never computed.
    """
    common = dict(subject="S2", phase="calibration", segment=1,
                  kb_version="kb_v2.0", prompt_version="p",
                  model="gemini-2.5-flash", temperature=0.0, pinned=None)
    assert cache_key(modality="ECG", **common) != cache_key(modality="PPG", **common)


def test_cache_key_changes_with_every_setting_that_changes_the_answer():
    base = dict(subject="S2", phase="calibration", segment=1, modality="ECG",
                kb_version="kb_v2.0", prompt_version="p", model="m",
                temperature=0.0, pinned=None)
    for field, other in [("kb_version", "kb_v3.0"), ("prompt_version", "v2"),
                         ("model", "other"), ("temperature", 0.7),
                         ("pinned", "KB-INTERP-01")]:
        assert cache_key(**base) != cache_key(**{**base, field: other}), field
