"""
train.py — Leave-One-Subject-Out training, with overfitting treated as the enemy.

With 854 segments from 15 people and an 80k-parameter network, overfitting is the
default outcome, not a risk. Five defences are built in, and the last one is the
only one that can actually PROVE the others worked.

1. THE TEST SUBJECT IS NEVER SEEN, BY ANYTHING.

   Splitting by subject is necessary but not sufficient. The subtler mistake is
   early stopping: choosing the epoch by watching the held-out subject's score
   turns that subject into part of the training procedure, and the reported figure
   becomes the best of N attempts rather than a prediction. So each fold carves a
   separate VALIDATION subject out of the remaining fourteen. Three disjoint
   groups: train, validate, test.

2. NO SEGMENT CROSSES A BOUNDARY.

   Segments overlap by 30 seconds, so two rows can share half their beats. Because
   every split here is by subject, overlapping rows always land on the same side.
   `assert_no_leakage` re-checks this rather than trusting it.

3. THE MAJORITY CLASS IS NOT ALLOWED TO WIN BY DEFAULT.

   WESAD resting phases outnumber TSST roughly 1.76 to 1, so a model answering
   "low" every time already scores about 64% accuracy. Class weights remove that
   free lunch, and macro-F1 — the same metric the rule baseline is reported in —
   refuses to be impressed by it.

4. CAPACITY IS RESTRAINED WHILE IT TRAINS.

   Dropout 0.3 from the proposal, plus weight decay, plus early stopping on
   validation macro-F1. The train-validation gap is recorded per fold and printed,
   so overfitting is something you can SEE in the output rather than something the
   code claims to have prevented.

5. THE PERMUTATION TEST.

   Defences 1-4 are arguments. This is a measurement. Shuffle the labels and run
   the identical procedure: with the association destroyed, an honest pipeline can
   do no better than chance. If it still scores well, something leaks — and no
   amount of careful reasoning about the splits would have revealed it. Run it
   before believing any real result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn

from hrv_rag.evaluation.labels import DATASET_LABELS, EvaluationRecord, TrueLabel
from hrv_rag.evaluation.metrics import ClassificationReport, evaluate_classification

from .dataset import SequenceDataset, assert_no_leakage
from .models import make_model

#: Integer prediction back to the label the RAG side is scored in, so both
#: branches are measured by literally the same function.
INT_TO_LABEL = {0: TrueLabel.LOW, 1: TrueLabel.HIGH}


@dataclass(frozen=True)
class TrainConfig:
    """Every knob, fixed here so a run can be reproduced from the file alone."""

    epochs: int = 120
    batch_size: int = 32          # Tabel 3.3
    learning_rate: float = 1e-3   # Tabel 3.3, Adam
    dropout: float = 0.3          # Tabel 3.3

    # Not in the proposal, added deliberately. With 80k parameters over ~800
    # training rows, weight decay is cheap insurance and costs nothing to justify.
    weight_decay: float = 1e-4

    # Epochs without validation improvement before stopping. Generous, because the
    # validation set is a single subject and its score is therefore noisy; a tight
    # patience would stop on that noise rather than on genuine convergence.
    patience: int = 20

    # Floor below which early stopping cannot fire.
    #
    # Added after the first full run exposed the failure it prevents. Macro-F1 on
    # two validation subjects is a COARSE signal — it can reach 1.000 within a few
    # epochs purely because those two people are easy. Once it does, no later epoch
    # can ever beat it, patience drains, and the fold keeps a barely-trained model.
    # It happened in three of fifteen folds, and those three were exactly the three
    # worst test scores (S15 stopped at epoch 1 and scored 0.392). The symptom looks
    # like overfitting and is the opposite of it.
    min_epochs: int = 25

    #: Subjects held out of training WITHIN each fold, for early stopping only.
    #: Two rather than one so the stopping signal averages over two people.
    n_val_subjects: int = 2

    seed: int = 20260811


@dataclass
class FoldResult:
    """One LOSO fold: who was held out, what was predicted, and how it trained."""

    test_subject: str
    val_subjects: list[str]
    y_true: np.ndarray
    y_pred: np.ndarray
    phases: np.ndarray
    best_epoch: int
    train_macro_f1: float
    val_macro_f1: float
    test_macro_f1: float
    epochs_run: int

    @property
    def overfit_gap(self) -> float:
        """
        How much better the model does on data it trained on.

        Reported rather than merely guarded against. A gap near zero on this much
        data usually means the model learned little; a very large gap means it
        memorised. Both are findings, and neither is visible from the test score.
        """
        return self.train_macro_f1 - self.val_macro_f1


@dataclass
class LosoResult:
    """Every fold, plus the pooled report computed by the RAG side's own metrics."""

    folds: list[FoldResult]
    report: ClassificationReport
    config: TrainConfig
    label_permuted: bool = False
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def mean_overfit_gap(self) -> float:
        return float(np.mean([f.overfit_gap for f in self.folds])) if self.folds else float("nan")

    def summary(self) -> str:
        head = "PERMUTED LABELS — expect chance" if self.label_permuted else "LOSO"
        return (
            f"{head}: {len(self.folds)} folds, {self.report.n_evaluated} segments\n"
            f"  accuracy {self.report.accuracy:.3f}  "
            f"macro-F1 {self.report.macro_f1:.3f}  kappa {self.report.kappa:.3f}\n"
            f"  mean train-val gap {self.mean_overfit_gap:+.3f}  "
            f"({self.seconds:.0f}s)"
        )


# --------------------------------------------------------------------- helpers
def _subset(data: SequenceDataset, keep: np.ndarray) -> dict:
    return {
        "x": torch.from_numpy(data.x[keep]),
        "mask": torch.from_numpy(data.mask[keep]),
        "y": torch.from_numpy(data.y[keep]),
        "phases": data.phases[keep],
    }


def _class_weights(y: torch.Tensor, n_classes: int = 2) -> torch.Tensor:
    """
    Inverse-frequency weights, normalised to mean 1.

    Normalising keeps the effective learning rate comparable across folds. Without
    it, a fold whose training pool happens to be more unbalanced would also train
    with a larger total loss, and the two effects would be impossible to separate
    afterwards.
    """
    counts = torch.bincount(y, minlength=n_classes).float()
    weights = counts.sum() / counts.clamp(min=1.0)
    return weights / weights.mean()


def _macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(f1_score(y_true, y_pred, average="macro", labels=[0, 1],
                          zero_division=0))


@torch.no_grad()
def _predict(model: nn.Module, part: dict) -> np.ndarray:
    model.eval()
    logits = model(part["x"], part["mask"])
    return logits.argmax(dim=1).numpy()


@torch.no_grad()
def _loss_on(model: nn.Module, part: dict, loss_fn: nn.Module) -> float:
    """Validation loss, the finer-grained twin of validation macro-F1."""
    model.eval()
    return float(loss_fn(model(part["x"], part["mask"]), part["y"]).item())


def permute_labels(data: SequenceDataset, seed: int) -> SequenceDataset:
    """
    The same data with labels shuffled — the control condition for defence 5.

    Shuffled ACROSS the whole set rather than within each subject. Permuting
    within a subject would leave the calibration-versus-question structure partly
    intact, and the test would then be checking something weaker than intended.
    """
    rng = np.random.default_rng(seed)
    shuffled = data.y.copy()
    rng.shuffle(shuffled)
    return SequenceDataset(
        x=data.x, mask=data.mask, y=shuffled, subjects=data.subjects,
        phases=data.phases, n_beats=data.n_beats, normalised=data.normalised,
    )


# ------------------------------------------------------------------ one fold
def train_one_fold(data: SequenceDataset, test_subject: str,
                   val_subjects: list[str], cfg: TrainConfig) -> FoldResult:
    """
    Train on the remaining subjects, stop on the validation subjects, predict once.

    The test subject enters exactly once, at the end, after the weights are final.
    Nothing about the run — not the epoch, not the threshold, not the seed — is
    chosen by looking at it.
    """
    is_test = data.subjects == test_subject
    is_val = np.isin(data.subjects, val_subjects)
    is_train = ~is_test & ~is_val

    train, val, test = _subset(data, is_train), _subset(data, is_val), _subset(data, is_test)

    torch.manual_seed(cfg.seed)
    model = make_model(dropout=cfg.dropout, seed=cfg.seed)
    optimiser = torch.optim.Adam(model.parameters(), lr=cfg.learning_rate,
                                 weight_decay=cfg.weight_decay)
    loss_fn = nn.CrossEntropyLoss(weight=_class_weights(train["y"]))

    generator = torch.Generator().manual_seed(cfg.seed)
    n_train = train["y"].shape[0]

    best = {"val": -1.0, "loss": float("inf"), "train": 0.0, "epoch": 0, "state": None}
    since_improved = 0
    epochs_run = 0

    for epoch in range(1, cfg.epochs + 1):
        epochs_run = epoch
        model.train()
        order = torch.randperm(n_train, generator=generator)
        for start in range(0, n_train, cfg.batch_size):
            idx = order[start:start + cfg.batch_size]
            optimiser.zero_grad()
            logits = model(train["x"][idx], train["mask"][idx])
            loss_fn(logits, train["y"][idx]).backward()
            optimiser.step()

        val_f1 = _macro_f1(val["y"].numpy(), _predict(model, val))
        val_loss = _loss_on(model, val, loss_fn)

        # Loss breaks the tie when macro-F1 plateaus.
        #
        # Macro-F1 over two subjects is coarse and saturates: once it touches
        # 1.000, a strictly-greater test can never fire again and the fold freezes
        # on whatever weights happened to reach it first. Loss keeps moving after
        # the labels stop flipping, so it can still tell a confident model from a
        # barely-decided one that scores the same.
        improved = val_f1 > best["val"] or (
            val_f1 >= best["val"] and val_loss < best["loss"]
        )
        if improved:
            best = {
                "val": val_f1,
                "loss": val_loss,
                "train": _macro_f1(train["y"].numpy(), _predict(model, train)),
                "epoch": epoch,
                "state": {k: v.clone() for k, v in model.state_dict().items()},
            }
            since_improved = 0
        else:
            since_improved += 1
            if since_improved >= cfg.patience and epoch >= cfg.min_epochs:
                break

    # Restore the epoch the VALIDATION subjects chose, never the last one and
    # never the best-on-test one.
    if best["state"] is not None:
        model.load_state_dict(best["state"])

    y_pred = _predict(model, test)
    return FoldResult(
        test_subject=test_subject,
        val_subjects=list(val_subjects),
        y_true=test["y"].numpy(),
        y_pred=y_pred,
        phases=test["phases"],
        best_epoch=int(best["epoch"]),
        train_macro_f1=float(best["train"]),
        val_macro_f1=float(best["val"]),
        test_macro_f1=_macro_f1(test["y"].numpy(), y_pred),
        epochs_run=epochs_run,
    )


# ----------------------------------------------------------------- the sweep
def run_loso(data: SequenceDataset, cfg: TrainConfig | None = None,
             label_permuted: bool = False, verbose: bool = True) -> LosoResult:
    """
    One fold per subject, then pooled metrics via the RAG side's own function.

    Pooling the per-fold PREDICTIONS and scoring them once, rather than averaging
    fifteen per-fold macro-F1 scores, is deliberate: subjects contribute different
    numbers of segments, and averaging per-fold scores would silently weight a
    subject with 40 segments the same as one with 70.
    """
    cfg = cfg or TrainConfig()
    subjects = sorted(set(data.subjects.tolist()))
    rng = np.random.default_rng(cfg.seed)
    started = time.monotonic()

    folds: list[FoldResult] = []
    for i, test_subject in enumerate(subjects):
        others = [s for s in subjects if s != test_subject]
        # Rotated rather than random, so every subject takes a turn validating and
        # no single person's idiosyncrasies steer every fold's stopping point.
        val_subjects = [others[(i + k) % len(others)] for k in range(cfg.n_val_subjects)]

        fold = train_one_fold(data, test_subject, val_subjects, cfg)
        folds.append(fold)
        if verbose:
            print(f"  {test_subject:<5} val={','.join(val_subjects):<9} "
                  f"epoch {fold.best_epoch:>3}/{fold.epochs_run:<3} "
                  f"train {fold.train_macro_f1:.3f}  val {fold.val_macro_f1:.3f}  "
                  f"test {fold.test_macro_f1:.3f}  gap {fold.overfit_gap:+.3f}")

    records = []
    for fold in folds:
        for j, (truth, pred) in enumerate(zip(fold.y_true, fold.y_pred)):
            records.append(EvaluationRecord(
                subject=fold.test_subject, phase=str(fold.phases[j]), segment=j,
                modality="ECG", truth=INT_TO_LABEL[int(truth)],
                predicted=INT_TO_LABEL[int(pred)], raw_level=INT_TO_LABEL[int(pred)].value,
                confidence=1.0, references=[], retrieved_ids=[], reasoning="",
                is_trustworthy=True,
            ))

    report = evaluate_classification(records)
    result = LosoResult(folds=folds, report=report, config=cfg,
                        label_permuted=label_permuted,
                        seconds=time.monotonic() - started)

    if label_permuted:
        result.notes.append(
            "Labels were shuffled before training. Anything meaningfully above "
            "chance here is leakage, not learning."
        )
    _ = rng, DATASET_LABELS
    return result


def check_no_leakage(data: SequenceDataset, cfg: TrainConfig | None = None) -> None:
    """Re-run the subject-disjointness check for every fold this sweep will build."""
    cfg = cfg or TrainConfig()
    subjects = sorted(set(data.subjects.tolist()))
    for i, test_subject in enumerate(subjects):
        others = [s for s in subjects if s != test_subject]
        val_subjects = [others[(i + k) % len(others)] for k in range(cfg.n_val_subjects)]
        is_test = data.subjects == test_subject
        is_val = np.isin(data.subjects, val_subjects)
        train_part = _slice_dataset(data, ~is_test & ~is_val)
        assert_no_leakage(train_part, _slice_dataset(data, is_test))
        assert_no_leakage(train_part, _slice_dataset(data, is_val))


def _slice_dataset(data: SequenceDataset, keep: np.ndarray) -> SequenceDataset:
    return SequenceDataset(
        x=data.x[keep], mask=data.mask[keep], y=data.y[keep],
        subjects=data.subjects[keep], phases=data.phases[keep],
        n_beats=data.n_beats[keep], normalised=data.normalised,
    )
