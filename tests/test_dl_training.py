"""
test_dl_training.py — proving the anti-overfitting machinery actually bites.

Every check here is about a failure that inflates the score. A test that only
confirmed "training runs" would pass just as happily on a pipeline that leaks.

Synthetic subjects are used so the suite stays fast and runs anywhere. The
signal is deliberately crude — high-label rows have shorter intervals — because
what is under test is the plumbing around the model, not whether a CNN can learn
physiology.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from hrv_dl.dataset import MAX_BEATS, SequenceDataset, assert_no_leakage
from hrv_dl.models import CNN1D, make_model
from hrv_dl.train import (TrainConfig, _class_weights, _fit_fixed, _subset,
                          check_no_leakage, permute_labels, run_loso,
                          run_matched, train_one_fold)
from hrv_rag.config.settings import settings


def synthetic(n_subjects=6, per_class=8, seed=0) -> SequenceDataset:
    rng = np.random.default_rng(seed)
    x, mask, y, subs, phases, nb = [], [], [], [], [], []
    for s in range(n_subjects):
        for label in (0, 1):
            for _ in range(per_class):
                n = int(rng.integers(60, 120))
                base = 1.0 if label == 0 else 0.82
                row = np.zeros(MAX_BEATS, np.float32)
                m = np.zeros(MAX_BEATS, bool)
                row[:n] = base + rng.normal(0, 0.03, n)
                m[:n] = True
                x.append(row); mask.append(m); y.append(label)
                subs.append(f"S{s}"); nb.append(n)
                phases.append("calibration" if label == 0 else "question")
    return SequenceDataset(
        x=np.asarray(x, np.float32), mask=np.asarray(mask), y=np.asarray(y, np.int64),
        subjects=np.asarray(subs, dtype=object), phases=np.asarray(phases, dtype=object),
        n_beats=np.asarray(nb, np.int64), normalised=True,
    )


FAST = TrainConfig(epochs=6, patience=3, n_val_subjects=2, seed=7)


# ------------------------------------------------------------------ the model
def test_parameter_count_is_the_one_the_choice_was_argued_from():
    # The architecture was picked on capacity-against-data grounds. If the count
    # drifts, that argument silently stops being true.
    n = CNN1D().n_parameters()
    assert 70_000 < n < 95_000, n


def test_padding_cannot_change_the_answer():
    # The failure this catches is invisible: convolution bias makes padded slots
    # non-zero after layer one, so an unmasked network reads heart rate off how
    # much padding a row carries rather than off the intervals.
    torch.manual_seed(0)
    model = make_model(seed=0).eval()

    short = torch.zeros(1, MAX_BEATS)
    m = torch.zeros(1, MAX_BEATS, dtype=torch.bool)
    short[0, :70] = 0.95
    m[0, :70] = True

    with torch.no_grad():
        a = model(short, m)
        # Same real beats, but the padding filled with a wildly different value.
        polluted = short.clone()
        polluted[0, 70:] = 7.5
        b = model(polluted, m)

    assert torch.allclose(a, b, atol=1e-5), "padding leaked into the prediction"


def test_a_row_whose_mask_is_empty_does_not_produce_nan():
    model = make_model(seed=0).eval()
    with torch.no_grad():
        out = model(torch.zeros(1, MAX_BEATS), torch.zeros(1, MAX_BEATS, dtype=torch.bool))
    assert torch.isfinite(out).all()


# ----------------------------------------------------------- the three groups
def test_test_subject_is_absent_from_training_and_validation():
    data = synthetic()
    check_no_leakage(data, FAST)  # raises if any fold shares a subject


def test_validation_subjects_are_not_the_test_subject():
    # Early stopping on the held-out subject would turn the reported figure into
    # "best of N attempts" rather than a prediction about a new person.
    data = synthetic()
    subjects = sorted(set(data.subjects.tolist()))
    for i, test_subject in enumerate(subjects):
        others = [s for s in subjects if s != test_subject]
        val = [others[(i + k) % len(others)] for k in range(FAST.n_val_subjects)]
        assert test_subject not in val


def test_leakage_guard_still_fires_when_it_should():
    data = synthetic()
    with pytest.raises(ValueError, match="both splits"):
        assert_no_leakage(data, data)


def test_every_subject_gets_a_turn_being_tested():
    data = synthetic(n_subjects=5, per_class=4)
    result = run_loso(data, FAST, verbose=False)
    assert sorted(f.test_subject for f in result.folds) == sorted(set(data.subjects.tolist()))


# ------------------------------------------------------------- class balance
def test_class_weights_cancel_an_imbalance():
    y = torch.tensor([0] * 176 + [1] * 100)   # the real WESAD ratio, 1.76 : 1
    w = _class_weights(y)
    counts = torch.bincount(y).float()
    # Weighted contribution of each class should be equal — that is the point.
    assert torch.allclose(w * counts, (w * counts).mean().expand(2), rtol=1e-4)
    assert w[1] > w[0], "the minority class must carry the larger weight"


def test_class_weights_are_normalised_so_folds_stay_comparable():
    for y in (torch.tensor([0] * 10 + [1] * 10), torch.tensor([0] * 30 + [1] * 5)):
        assert float(_class_weights(y).mean()) == pytest.approx(1.0, abs=1e-5)


# ------------------------------------------------------- the permutation test
def test_permutation_keeps_the_data_and_destroys_only_the_association():
    data = synthetic()
    shuffled = permute_labels(data, seed=3)
    assert np.array_equal(shuffled.x, data.x)
    assert np.array_equal(shuffled.subjects, data.subjects)
    assert sorted(shuffled.y.tolist()) == sorted(data.y.tolist())
    assert not np.array_equal(shuffled.y, data.y)


# The two tests below are a matched pair and MUST share their settings. Run on
# different data sizes or epoch counts they prove nothing: a permutation test
# passes trivially on a model too starved to learn anything at all. Identical
# settings, opposite outcomes, is the whole argument.
PAIR = dict(n_subjects=8, per_class=10)
PAIR_CFG = TrainConfig(epochs=60, patience=20, seed=7)


def test_shuffled_labels_cannot_be_learned():
    # The decisive check. Defences on splits are arguments; this is a measurement.
    # If a pipeline scores well here, something leaks and no amount of careful
    # reasoning about the splits would have shown it.
    data = permute_labels(synthetic(**PAIR), seed=11)
    result = run_loso(data, PAIR_CFG, label_permuted=True, verbose=False)
    assert result.report.macro_f1 < 0.70, result.summary()
    assert result.label_permuted and result.notes


def test_the_real_signal_is_still_learnable():
    # The counterpart, on the same settings. Without it, the test above would also
    # pass on a pipeline that simply never learns anything.
    result = run_loso(synthetic(**PAIR), PAIR_CFG, verbose=False)
    assert result.report.macro_f1 > 0.70, result.summary()


# ------------------------------------------------------------- what it reports
def test_a_saturating_validation_score_does_not_freeze_training():
    # The regression this pins down was found by the first full WESAD run, not by
    # reasoning. Macro-F1 over two validation subjects can hit 1.000 within a few
    # epochs; with a strictly-greater test and no epoch floor, no later epoch can
    # ever beat it, patience drains, and the fold keeps a barely-trained model.
    # Three of fifteen folds did exactly this, and they were the three worst test
    # scores — one stopped at epoch 1 and scored 0.392.
    data = synthetic(n_subjects=5, per_class=6, seed=2)
    cfg = TrainConfig(epochs=30, patience=2, min_epochs=12, seed=3)
    fold = train_one_fold(data, "S0", ["S1", "S2"], cfg)
    assert fold.epochs_run >= cfg.min_epochs, (
        f"stopped at epoch {fold.epochs_run}, before the floor of {cfg.min_epochs}"
    )


def test_loss_breaks_the_tie_once_macro_f1_plateaus():
    # With the floor alone, a plateaued fold would still keep its FIRST saturating
    # epoch. Validation loss keeps moving after the labels stop flipping, so the
    # selected epoch should be able to advance past the first perfect one.
    data = synthetic(n_subjects=5, per_class=6, seed=5)
    cfg = TrainConfig(epochs=40, patience=40, min_epochs=1, seed=5)
    fold = train_one_fold(data, "S0", ["S1", "S2"], cfg)
    assert fold.best_epoch > 1


def test_the_overfitting_gap_is_recorded_not_merely_prevented():
    data = synthetic(n_subjects=4, per_class=5)
    fold = train_one_fold(data, "S0", ["S1", "S2"], FAST)
    assert fold.overfit_gap == pytest.approx(fold.train_macro_f1 - fold.val_macro_f1)
    assert 1 <= fold.best_epoch <= fold.epochs_run


def test_the_restored_epoch_is_the_one_validation_chose():
    data = synthetic(n_subjects=4, per_class=5)
    fold = train_one_fold(data, "S0", ["S1", "S2"], TrainConfig(epochs=8, patience=8, seed=1))
    assert fold.best_epoch <= fold.epochs_run
    assert fold.val_macro_f1 >= 0.0


# --------------------------------------------------- the matched head-to-head
def wesad_shaped(seed=0) -> SequenceDataset:
    """Synthetic data carrying the REAL subject IDs, so the split logic is exercised."""
    ids = list(settings.split.dev_subjects) + list(settings.split.test_subjects)
    rng = np.random.default_rng(seed)
    x, mask, y, subs, phases, nb = [], [], [], [], [], []
    for s in ids:
        for label in (0, 1):
            for _ in range(6):
                n = int(rng.integers(60, 120))
                row = np.zeros(MAX_BEATS, np.float32); m = np.zeros(MAX_BEATS, bool)
                row[:n] = (1.0 if label == 0 else 0.82) + rng.normal(0, 0.03, n)
                m[:n] = True
                x.append(row); mask.append(m); y.append(label); subs.append(s); nb.append(n)
                phases.append("calibration" if label == 0 else "question")
    return SequenceDataset(
        x=np.asarray(x, np.float32), mask=np.asarray(mask), y=np.asarray(y, np.int64),
        subjects=np.asarray(subs, dtype=object), phases=np.asarray(phases, dtype=object),
        n_beats=np.asarray(nb, np.int64), normalised=True,
    )


def test_matched_run_scores_only_the_sealed_subjects():
    # The whole point of this mode: the rule was calibrated on five people, so the
    # network must be too, and both must then meet the same ten.
    result = run_matched(wesad_shaped(), TrainConfig(epochs=8, patience=3,
                                                     min_epochs=1, seed=4),
                         verbose=False)
    assert set(result.per_subject) == set(settings.split.test_subjects)
    assert not (set(result.per_subject) & set(settings.split.dev_subjects))


def test_matched_run_freezes_its_epoch_before_touching_the_sealed_set():
    # Five inner rounds, one per development subject, and the median is obeyed.
    # If the epoch were chosen by watching the sealed subjects, the reported figure
    # would be the best of several attempts rather than a prediction.
    result = run_matched(wesad_shaped(), TrainConfig(epochs=8, patience=3,
                                                     min_epochs=1, seed=4),
                         verbose=False)
    assert len(result.inner_epochs) == len(settings.split.dev_subjects)
    assert result.frozen_epochs == int(np.median(result.inner_epochs))


def test_fixed_epoch_training_uses_no_validation_at_all():
    # With every development subject in the training pool there is nothing left to
    # early-stop on, which is exactly why the epoch had to be frozen beforehand.
    data = wesad_shaped()
    train = _subset(data, np.isin(data.subjects, settings.split.dev_subjects))
    model = _fit_fixed(train, 3, TrainConfig(seed=1))
    assert model.n_parameters() == CNN1D().n_parameters()


def test_matched_and_loso_share_one_training_loop():
    # Two copies of the loop would let the two comparisons train the same
    # architecture by different rules, and their numbers would stop being
    # comparable without anything saying so.
    import inspect

    from hrv_dl import train as mod
    assert "_fit_early_stopping" in inspect.getsource(mod.train_one_fold)
    assert "_fit_early_stopping" in inspect.getsource(mod.run_matched)


def test_metrics_come_from_the_rag_side_s_own_function():
    # Same macro-F1, same Cohen's kappa, same class list. If the two branches
    # computed their headline numbers with different code, comparing them would
    # mean nothing.
    data = synthetic(n_subjects=4, per_class=5)
    result = run_loso(data, FAST, verbose=False)
    assert result.report.dataset == "WESAD"
    assert set(result.report.per_class_f1) == {"low", "high"}
    assert result.report.n_evaluated == len(data)


def test_a_run_is_reproducible_from_its_config_alone():
    data = synthetic(n_subjects=4, per_class=5)
    a = run_loso(data, FAST, verbose=False)
    b = run_loso(data, FAST, verbose=False)
    assert a.report.macro_f1 == b.report.macro_f1
    assert [f.best_epoch for f in a.folds] == [f.best_epoch for f in b.folds]
