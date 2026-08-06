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
from hrv_rag.evaluation.metrics import evaluate_classification
from hrv_rag.evaluation.rag_metrics import FaithfulnessReport
from hrv_rag.evaluation.rule_baseline import rule_rmssd_and_hr, rule_rmssd_only


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
