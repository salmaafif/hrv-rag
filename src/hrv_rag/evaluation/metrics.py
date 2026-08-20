"""
metrics.py — Classification metrics, reported per dataset and per modality.

CLAUDE.md forbids pooling labels from different datasets into one figure, because
their label structures differ: WESAD is binary, SWELL-KW has three levels, and
UBFC-Phys is not a classification problem at all. There is deliberately no function
here that computes a single overall score for the whole system — the absence is the
design.

Two reporting rules are enforced throughout:

1. **Coverage is reported alongside accuracy.** Abstentions are excluded from the
   accuracy figures, so accuracy over a small covered fraction would flatter the
   system. The two numbers only mean something together.

2. **Segments are not independent** (BACKLOG L2). Sliding windows overlap by 30
   seconds, so neighbouring segments share half their data. The effective sample
   size is smaller than the row count, and confidence intervals computed as if rows
   were independent would be too narrow. `SEGMENT_INDEPENDENCE_NOTE` carries this
   caveat so it travels with the numbers instead of being forgotten.

   This is also why the intervals below resample SUBJECTS rather than rows — see
   `bootstrap_subject_ci`, and `paired_difference_ci` for comparing two systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import (accuracy_score, cohen_kappa_score,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)

from .labels import DATASET_LABELS, EvaluationRecord, TrueLabel

SEGMENT_INDEPENDENCE_NOTE = (
    "Segments overlap by 30 s, so they are not independent observations. The "
    "effective sample size is below the row count and any confidence interval "
    "assuming independence would be too narrow."
)

#: Datasets whose rows really are independent, so the caveat above must NOT be
#: attached to them.
#:
#: SWELL-KW is read one row per minute with no overlap at all, which makes it the
#: cleaner of the two on this point. Printing the WESAD caveat underneath its
#: numbers would be a false statement about the data — and one that understates
#: the result, since it tells the reader the sample is weaker than it is.
INDEPENDENT_ROW_DATASETS = {"SWELL"}


#: Resamples drawn by default. Two thousand puts the Monte-Carlo error on a 95%
#: percentile bound at roughly +/-0.01 macro-F1 — comfortably finer than the
#: interval itself, and fast enough that nobody is tempted to switch it off.
DEFAULT_RESAMPLES = 2000

#: Fixed so the same records always yield the same interval. An interval that
#: shifted between two runs of an unchanged evaluation would be indistinguishable
#: from a real change in the system.
DEFAULT_BOOTSTRAP_SEED = 20260813


@dataclass(frozen=True)
class ConfidenceInterval:
    """A percentile bootstrap interval, with what it was computed over."""

    low: float
    high: float
    level: float
    n_resamples: int
    n_clusters: int

    def __str__(self) -> str:
        return f"[{self.low:.3f}, {self.high:.3f}] ({self.level:.0%})"


@dataclass
class ClassificationReport:
    """Metrics for one dataset and one modality."""

    dataset: str
    modality: str
    n_total: int
    n_abstained: int
    n_evaluated: int

    accuracy: float
    macro_f1: float
    kappa: float
    per_class_f1: dict[str, float]
    confusion: list[list[int]]
    labels_order: list[str]

    notes: list[str] = field(default_factory=list)

    #: None when there were too few subjects to resample, or when the caller
    #: switched the bootstrap off.
    macro_f1_ci: ConfidenceInterval | None = None
    kappa_ci: ConfidenceInterval | None = None

    @property
    def coverage(self) -> float:
        """Fraction of segments the system was willing to judge."""
        return self.n_evaluated / self.n_total if self.n_total else 0.0

    def summary(self) -> str:
        def qualified(text: str, ci: ConfidenceInterval | None) -> str:
            return text if ci is None else f"{text}  {ci}  over {ci.n_clusters} subjects"

        lines = [
            f"{self.dataset} / {self.modality}",
            f"  segments      : {self.n_total} "
            f"({self.n_evaluated} judged, {self.n_abstained} abstained)",
            f"  coverage      : {self.coverage:.1%}",
            f"  accuracy      : {self.accuracy:.3f}",
            qualified(f"  macro-F1      : {self.macro_f1:.3f}", self.macro_f1_ci),
            qualified(f"  Cohen's kappa : {self.kappa:.3f}", self.kappa_ci),
        ]
        for label, score in self.per_class_f1.items():
            lines.append(f"  F1 ({label:<4})   : {score:.3f}")
        lines.append(f"  confusion     : {self.labels_order} -> {self.confusion}")
        for note in self.notes:
            lines.append(f"  NOTE: {note}")
        return "\n".join(lines)


@dataclass(frozen=True)
class BootstrapIntervals:
    """Both headline figures, resampled together over the same draws."""

    macro_f1: ConfidenceInterval | None
    kappa: ConfidenceInterval | None
    notes: list[str]

    @classmethod
    def none(cls, notes: list[str] | None = None) -> "BootstrapIntervals":
        return cls(macro_f1=None, kappa=None, notes=notes or [])


def bootstrap_subject_ci(
    records: list[EvaluationRecord],
    labels_order: list[str],
    level: float = 0.95,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> BootstrapIntervals:
    """
    How far the headline figures could move if the study had recruited differently.

    Macro-F1 and kappa are computed on the SAME draws rather than in two passes.
    Two independent bootstraps would each be valid on their own while describing
    slightly different imaginary studies, and the pair would then not be quotable
    in one sentence. It is also half the work.

    WHY SUBJECTS ARE RESAMPLED AND NOT ROWS. The usual bootstrap draws rows with
    replacement, and here that would be wrong twice over. Neighbouring segments
    overlap by 30 seconds and share half their beats, and every segment belonging to
    one person is measured against that person's own baseline. Rows are therefore
    clustered inside people, and a row-level bootstrap treats each of those rows as
    a fresh observation. It answers "how precise is this number over these ten
    people" when the question worth asking is "what if they had been ten OTHER
    people" — the second interval is far wider, and it is the one a reader assumes
    they are being shown. Ten subjects is the real sample size, not 561.

    Percentile method rather than bias-corrected: with ten clusters the correction
    is estimated from the same ten and adds a precision the data cannot support.

    Intervals come back None when a bootstrap cannot mean anything — fewer than two
    subjects, or resampling switched off — because a fabricated interval is worse
    than none at all.
    """
    if n_resamples <= 0:
        return BootstrapIntervals.none()

    by_subject: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        by_subject.setdefault(r.subject, []).append(i)

    subjects = sorted(by_subject)
    if len(subjects) < 2:
        return BootstrapIntervals.none([
            f"no confidence interval: {len(subjects)} subject in this slice, and "
            f"resampling one person tells you nothing about the next one."
        ])

    y_true = np.array([r.truth.value for r in records])
    y_pred = np.array([r.predicted.value for r in records])
    index_of = [np.asarray(by_subject[s]) for s in subjects]

    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(subjects), size=(n_resamples, len(subjects)))

    f1s: list[float] = []
    kappas: list[float] = []
    n_single_class = 0
    for draw in draws:
        rows = np.concatenate([index_of[k] for k in draw])
        truth, pred = y_true[rows], y_pred[rows]
        # A resample can miss a class entirely — every drawn subject contributed
        # calibration segments only, say. Macro-F1 is then averaging an F1 over a
        # class that is not there, which scores zero and drags the bound down by
        # half; kappa over one class is undefined outright. Those resamples are
        # dropped and counted rather than silently widening the interval downwards.
        if len(set(truth.tolist())) < 2:
            n_single_class += 1
            continue
        f1s.append(float(f1_score(truth, pred, labels=labels_order,
                                  average="macro", zero_division=0)))
        kappas.append(float(cohen_kappa_score(truth, pred, labels=labels_order)))

    if len(f1s) < n_resamples // 2:
        return BootstrapIntervals.none([
            f"no confidence interval: {n_single_class} of {n_resamples} resamples "
            f"contained a single class, so the bootstrap has nothing stable to "
            f"summarise."
        ])

    notes = []
    if n_single_class:
        notes.append(
            f"{n_single_class} of {n_resamples} resamples were dropped for holding "
            f"only one class; the interval is over the remaining {len(f1s)}."
        )
    return BootstrapIntervals(
        macro_f1=_percentile_interval(f1s, level, len(subjects)),
        # Kappa can still come back undefined on a resample whose predictions are
        # constant AND match the expected agreement exactly. Rare, but a single nan
        # poisons the percentile of the whole array.
        kappa=_percentile_interval([k for k in kappas if k == k], level,
                                   len(subjects)),
        notes=notes,
    )


def _percentile_interval(scores: list[float], level: float,
                         n_clusters: int) -> ConfidenceInterval | None:
    if not scores:
        return None
    tail = (1.0 - level) / 2.0 * 100.0
    return ConfidenceInterval(
        low=float(np.percentile(scores, tail)),
        high=float(np.percentile(scores, 100.0 - tail)),
        level=level,
        n_resamples=len(scores),
        n_clusters=n_clusters,
    )


def paired_difference_ci(
    baseline: dict[str, float],
    challenger: dict[str, float],
    level: float = 0.95,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> tuple[ConfidenceInterval | None, list[str]]:
    """
    How much better one system is than another, over the subjects they both saw.

    WHY THIS IS NOT THE SAME AS COMPARING TWO INTERVALS. Two overlapping intervals
    are routinely read as "no difference", and for a PAIRED comparison that
    inference is simply wrong. Each interval carries the variation between people —
    some subjects are hard for everything — and that variation is shared by both
    systems, so it cancels when the difference is taken subject by subject. On the
    sealed WESAD subjects the two intervals overlap across most of their length
    while the difference itself never touches zero.

    Subjects are the resampling unit here too, and only those measured by BOTH
    systems take part: a subject one side never saw contributes no difference, and
    quietly treating its absence as zero would drag the estimate toward no-effect.
    """
    shared = sorted(set(baseline) & set(challenger))
    notes = []
    dropped = sorted((set(baseline) ^ set(challenger)))
    if dropped:
        notes.append(
            f"{len(dropped)} subject(s) scored by only one side and left out of the "
            f"difference: {', '.join(dropped)}."
        )

    if n_resamples <= 0:
        return None, notes
    if len(shared) < 2:
        return None, notes + [
            f"no interval for the difference: {len(shared)} subject in common."
        ]

    deltas = np.array([challenger[s] - baseline[s] for s in shared])
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(shared), size=(n_resamples, len(shared)))
    means = deltas[draws].mean(axis=1)

    tail = (1.0 - level) / 2.0 * 100.0
    return ConfidenceInterval(
        low=float(np.percentile(means, tail)),
        high=float(np.percentile(means, 100.0 - tail)),
        level=level,
        n_resamples=n_resamples,
        n_clusters=len(shared),
    ), notes


def evaluate_classification(records: list[EvaluationRecord],
                            dataset: str = "WESAD",
                            modality: str = "ECG",
                            n_resamples: int = DEFAULT_RESAMPLES
                            ) -> ClassificationReport:
    """
    Compute classification metrics for one dataset/modality slice.

    Cohen's kappa is included alongside accuracy because accuracy alone is
    misleading when classes are unbalanced. In WESAD the baseline phase is roughly
    twice as long as TSST, so always answering "low" would already score around 65%.
    Kappa measures agreement above what chance would produce, which is the honest
    figure here.

    The class list comes from the DATASET, via `DATASET_LABELS`, not from the
    labels that happen to turn up in `records`. Two datasets genuinely differ here
    — WESAD is binary, SWELL-KW has three levels — and deriving the list from the
    sample would silently change the meaning of macro-F1 whenever a class was
    missing from a partial run. CLAUDE.md is explicit that metrics are reported per
    dataset and never pooled, and this is where that is enforced.
    """
    judged = [r for r in records if not r.abstained]
    n_abstained = len(records) - len(judged)

    if not judged:
        return ClassificationReport(
            dataset=dataset, modality=modality, n_total=len(records),
            n_abstained=n_abstained, n_evaluated=0,
            accuracy=float("nan"), macro_f1=float("nan"), kappa=float("nan"),
            per_class_f1={}, confusion=[], labels_order=[],
            notes=["the system abstained on every segment"],
        )

    y_true = [r.truth.value for r in judged]
    y_pred = [r.predicted.value for r in judged]
    order = [label.value for label in
             DATASET_LABELS.get(dataset, [TrueLabel.LOW, TrueLabel.HIGH])]

    per_class = f1_score(y_true, y_pred, labels=order, average=None,
                         zero_division=0)

    notes = ([] if dataset in INDEPENDENT_ROW_DATASETS
             else [SEGMENT_INDEPENDENCE_NOTE])
    if n_abstained:
        notes.append(
            f"{n_abstained} segments abstained and are excluded from accuracy; "
            f"read coverage together with the scores."
        )

    # A class that never appears scores F1 = 0 and drags macro-F1 down by half,
    # which reads as a broken system when it is really a lopsided sample. This is
    # not hypothetical: the free tier allows 20 calls a day and `--full` walks the
    # CSV in order, so the first day's run sees calibration segments only. It would
    # print macro-F1 0.50 and kappa nan after answering all 20 correctly.
    missing = [lab for lab in order if lab not in set(y_true)]
    if missing:
        notes.append(
            f"class {', '.join(missing)} is absent from this sample, so macro-F1 "
            f"and kappa are not meaningful — report accuracy and per-class F1 "
            f"instead until both classes are represented."
        )

    intervals = bootstrap_subject_ci(judged, order, n_resamples=n_resamples)
    notes.extend(intervals.notes)

    return ClassificationReport(
        dataset=dataset,
        modality=modality,
        n_total=len(records),
        n_abstained=n_abstained,
        n_evaluated=len(judged),
        accuracy=float(accuracy_score(y_true, y_pred)),
        macro_f1=float(f1_score(y_true, y_pred, labels=order,
                                average="macro", zero_division=0)),
        kappa=float(cohen_kappa_score(y_true, y_pred, labels=order)),
        per_class_f1={lab: float(s) for lab, s in zip(order, per_class)},
        confusion=confusion_matrix(y_true, y_pred, labels=order).tolist(),
        labels_order=order,
        notes=notes,
        macro_f1_ci=intervals.macro_f1,
        kappa_ci=intervals.kappa,
    )


def evaluate_per_subject(records: list[EvaluationRecord]) -> dict[str, float]:
    """
    Accuracy per subject.

    Worth reporting because a single subject can carry an aggregate figure. Among
    the development subjects, S6 and S10 show inverted physiological patterns, so a
    per-subject breakdown shows immediately whether errors concentrate there rather
    than being spread evenly.
    """
    by_subject: dict[str, list[EvaluationRecord]] = {}
    for r in records:
        if not r.abstained:
            by_subject.setdefault(r.subject, []).append(r)

    return {
        subject: float(accuracy_score([r.truth.value for r in rows],
                                      [r.predicted.value for r in rows]))
        for subject, rows in sorted(by_subject.items())
    }
