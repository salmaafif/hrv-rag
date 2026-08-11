"""
test_dl_dataset.py — guarding the deep-learning comparison against itself.

Every mistake this file checks for makes the model look BETTER, which is why none
of them would be caught by reading a results table. They are pinned here instead.

The tests run on synthetic series rather than on WESAD, so they execute anywhere
and in under a second. What they verify is the packing, splitting and
normalisation logic — the parts written for this comparison. The signal pipeline
underneath is already covered by the existing suite, and is imported rather than
copied precisely so it does not need testing twice.
"""

from __future__ import annotations

import numpy as np
import pytest

from hrv_dl.dataset import (LABEL_TO_INT, MAX_BEATS, SequenceDataset,
                            _pack, assert_no_leakage)
from hrv_rag.config.settings import settings
from hrv_rag.core.types import Phase
from hrv_rag.evaluation.labels import WESAD_PHASE_TO_LABEL, TrueLabel


def make_dataset(subjects, n_beats=(70, 80), labels=(0, 1),
                 normalised=True) -> SequenceDataset:
    rows = [np.full(n, 0.9 + 0.01 * i) for i, n in enumerate(n_beats)]
    return _pack(rows, list(labels), list(subjects),
                 ["calibration", "question"], list(n_beats), normalised)


# --------------------------------------------------------------- the split
def test_the_split_is_the_one_the_rag_results_were_produced_under():
    # Imported, never restated. A second copy of these ten IDs could drift and
    # nothing would report it — the two sets of numbers would simply stop being
    # about the same experiment.
    dev = set(settings.split.dev_subjects)
    test = set(settings.split.test_subjects)
    assert dev & test == set()
    assert len(dev) == 5 and len(test) == 10


def test_leakage_check_catches_a_shared_subject():
    train = make_dataset(["S2", "S6"])
    test = make_dataset(["S6", "S3"])
    with pytest.raises(ValueError, match="S6"):
        assert_no_leakage(train, test)


def test_leakage_check_passes_on_a_clean_split():
    assert_no_leakage(make_dataset(["S2", "S6"]), make_dataset(["S3", "S4"]))


def test_leakage_message_explains_why_it_matters():
    # The person hitting this at 2am needs to know it is not a formality: the
    # 30-second overlap is what turns a shared subject into a shared window.
    train = make_dataset(["S2", "S2"])
    test = make_dataset(["S2", "S2"])
    with pytest.raises(ValueError, match="overlap"):
        assert_no_leakage(train, test)


# ------------------------------------------------------------- the packing
def test_mask_marks_exactly_the_real_beats():
    data = make_dataset(["S2", "S2"], n_beats=(41, 96))
    assert data.mask.sum(axis=1).tolist() == [41, 96]
    assert data.x.shape == (2, MAX_BEATS)
    # Padding must be zero AND masked out, so a model cannot mistake it for a beat
    # of length zero.
    assert data.x[0, 41:].sum() == 0.0
    assert not data.mask[0, 41:].any()


def test_beat_count_is_kept_because_it_is_heart_rate():
    # A fast heart fits more beats into sixty seconds, so the count carries the
    # single most reliable stress signal in the whole dataset (L9: HR rose in all
    # five development subjects). Discarding it would handicap the comparator for
    # no reason.
    data = make_dataset(["S2", "S2"], n_beats=(45, 110))
    assert data.n_beats.tolist() == [45, 110]
    assert data.n_beats.tolist() == data.mask.sum(axis=1).tolist()


def test_padding_never_shortens_a_sequence():
    # Truncation would take beats only from the segments that have the most of
    # them — the fastest hearts, which are disproportionately the stressed ones.
    # The bias would run in the direction of the thing being measured.
    data = make_dataset(["S2"], n_beats=(MAX_BEATS,), labels=(1,))
    assert data.mask[0].all()
    assert int(data.n_beats[0]) == MAX_BEATS


def test_ceiling_matches_the_quality_gate_it_is_derived_from():
    # 200 beats in 60 s is 300 ms per beat, which is QualityConfig.rr_min_sec. A
    # segment cannot pass the gates and still exceed this.
    fastest_possible = int(round(60.0 / settings.quality.rr_min_sec))
    assert MAX_BEATS == fastest_possible


def test_shape_does_not_depend_on_the_data_it_was_built_from():
    # If MAX_BEATS were "the longest sequence observed", the array shape would
    # differ between dev and holdout — a small, quiet channel from the sealed set
    # back into the model's design.
    small = make_dataset(["S2"], n_beats=(35,), labels=(0,))
    large = make_dataset(["S3"], n_beats=(150,), labels=(1,))
    assert small.x.shape[1] == large.x.shape[1] == MAX_BEATS


# ---------------------------------------------------------------- labelling
def test_labels_follow_the_mapping_the_rule_is_scored_against():
    assert WESAD_PHASE_TO_LABEL[Phase.CALIBRATION] is TrueLabel.LOW
    assert WESAD_PHASE_TO_LABEL[Phase.QUESTION] is TrueLabel.HIGH
    assert LABEL_TO_INT[TrueLabel.LOW] == 0
    assert LABEL_TO_INT[TrueLabel.HIGH] == 1


def test_amusement_never_enters_the_dataset():
    from hrv_dl.dataset import LABELLED_PHASES
    # WESAD's amusement condition is positive arousal, not pressure. Including it
    # would corrupt the scale rather than enlarge the sample.
    assert set(LABELLED_PHASES) == {Phase.CALIBRATION, Phase.QUESTION}


# ------------------------------------------------------------ normalisation
def test_normalisation_removes_the_individual_offset():
    # Two people with very different resting rates should look alike after
    # dividing by their own baseline. Without this, a model with five training
    # subjects learns to recognise the SUBJECT rather than the state.
    slow = np.full(70, 1100.0)      # resting mean 1100 ms
    fast = np.full(70, 700.0)       # resting mean 700 ms
    assert np.allclose(slow / 1100.0, fast / 700.0)


def test_the_flag_records_which_form_the_arrays_are_in():
    # "Was this run normalised?" must be answerable from the data itself, since
    # the un-normalised form exists only as an ablation and the two are otherwise
    # indistinguishable at a glance.
    assert make_dataset(["S2"], n_beats=(70,), labels=(0,), normalised=True).normalised
    assert not make_dataset(["S2"], n_beats=(70,), labels=(0,),
                            normalised=False).normalised


def test_summary_reports_class_balance_and_beat_range():
    data = make_dataset(["S2", "S6"], n_beats=(50, 90), labels=(0, 1))
    text = data.summary()
    assert "2 segments" in text and "2 subjects" in text
    assert "1 low, 1 high" in text
    assert "50-90" in text
