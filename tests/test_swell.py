"""
Tests for the SWELL-KW layer (Stage 7).

The loader tests skip themselves when the dataset is not downloaded, because the
raw files are not committed. The label and metric tests do not need it at all —
they cover the three-class machinery, which WESAD could never exercise.
"""

import pytest

from hrv_rag.evaluation.labels import (DATASET_LABELS, EvaluationRecord,
                                       TrueLabel, predicted_label, true_label)
from hrv_rag.evaluation.metrics import evaluate_classification


def record(truth: TrueLabel, predicted: TrueLabel | None) -> EvaluationRecord:
    return EvaluationRecord(
        subject="p1", phase="time_pressure", segment=1, modality="ECG",
        truth=truth, predicted=predicted,
        raw_level="uncertain" if predicted is None else predicted.value,
        confidence=1.0, references=[], retrieved_ids=[], reasoning="",
        is_trustworthy=True,
    )


# ------------------------------------------------------------ ground truth
def test_swell_conditions_form_an_ordered_gradient():
    """
    Each step adds a demand without withdrawing the previous one: ordinary work,
    the same work with a third of the time removed, then that plus eight
    unexpected interruptions.
    """
    assert true_label("no_stress", dataset="SWELL") is TrueLabel.LOW
    assert true_label("time_pressure", dataset="SWELL") is TrueLabel.MODERATE
    assert true_label("interruption", dataset="SWELL") is TrueLabel.HIGH


def test_rest_block_is_not_scored():
    """
    The rest block defines the personal baseline, so scoring the system against it
    would be marking it on the reference it was handed.
    """
    assert true_label("calibration", dataset="SWELL") is None


def test_moderate_stays_separate_on_swell_but_folds_into_high_on_wesad():
    """
    This distinction is the entire reason SWELL is here.

    WESAD has no middle condition, so `moderate` has nowhere to land but the
    stressed side — which is why the rule's upper threshold could never be
    calibrated there (BACKLOG T2c.10).
    """
    assert predicted_label("moderate", dataset="SWELL") is TrueLabel.MODERATE
    assert predicted_label("moderate", dataset="WESAD") is TrueLabel.HIGH


def test_uncertain_abstains_under_either_mapping():
    assert predicted_label("uncertain", dataset="SWELL") is None
    assert predicted_label("uncertain", dataset="WESAD") is None


def test_unknown_dataset_is_refused_rather_than_guessed():
    with pytest.raises(NotImplementedError):
        true_label("rest", dataset="UBFC")


# ---------------------------------------------------------------- metrics
def test_class_list_comes_from_the_dataset_not_the_sample():
    """
    Three-class metrics must stay three-class even when a run happens to contain
    only two of them, or macro-F1 silently changes meaning between runs.
    """
    assert DATASET_LABELS["SWELL"] == [TrueLabel.LOW, TrueLabel.MODERATE,
                                       TrueLabel.HIGH]

    records = [record(TrueLabel.LOW, TrueLabel.LOW),
               record(TrueLabel.HIGH, TrueLabel.HIGH)]
    report = evaluate_classification(records, dataset="SWELL")

    assert report.labels_order == ["low", "moderate", "high"]
    assert set(report.per_class_f1) == {"low", "moderate", "high"}
    assert len(report.confusion) == 3


def test_wesad_stays_binary():
    report = evaluate_classification([record(TrueLabel.LOW, TrueLabel.LOW)],
                                     dataset="WESAD")
    assert report.labels_order == ["low", "high"]


def test_overlap_caveat_is_not_attached_to_swell():
    """
    SWELL rows are one minute each and do not overlap. Repeating WESAD's
    non-independence warning under them would be false, and it would understate
    the result by telling the reader the sample is weaker than it is.
    """
    records = [record(TrueLabel.LOW, TrueLabel.LOW)]
    swell = evaluate_classification(records, dataset="SWELL")
    wesad = evaluate_classification(records, dataset="WESAD")

    assert not any("overlap" in note for note in swell.notes)
    assert any("overlap" in note for note in wesad.notes)


# ----------------------------------------------------------------- loader
@pytest.fixture
def swell_table():
    swell = pytest.importorskip("hrv_rag.datasets.swell")
    try:
        return swell.load_swell_minutes()
    except FileNotFoundError:
        pytest.skip("SWELL-KW not downloaded on this machine")


def test_rmssd_is_converted_to_milliseconds(swell_table):
    """
    The workbook stores RMSSD in seconds. Left unconverted every value would be
    about 0.05, which is inside no plausible physiological range and would make
    every reactivity percentage meaningless while still looking like a number.
    """
    median = swell_table["rmssd"].median()
    assert 20.0 < median < 100.0, f"median RMSSD {median} is not in milliseconds"


def test_minutes_do_not_overlap(swell_table):
    subject = swell_table[swell_table["subject"] == swell_table["subject"].iloc[0]]
    spans = subject.sort_values("start_sec")
    assert (spans["start_sec"].diff().dropna() >= 60.0).all()


def test_every_row_has_a_mapped_phase(swell_table):
    assert swell_table["phase"].notna().all()
    assert set(swell_table["phase"]) <= {"calibration", "no_stress",
                                         "time_pressure", "interruption"}
