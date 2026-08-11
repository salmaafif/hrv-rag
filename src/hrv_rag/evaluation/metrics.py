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
"""

from __future__ import annotations

from dataclasses import dataclass, field

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

    @property
    def coverage(self) -> float:
        """Fraction of segments the system was willing to judge."""
        return self.n_evaluated / self.n_total if self.n_total else 0.0

    def summary(self) -> str:
        lines = [
            f"{self.dataset} / {self.modality}",
            f"  segments      : {self.n_total} "
            f"({self.n_evaluated} judged, {self.n_abstained} abstained)",
            f"  coverage      : {self.coverage:.1%}",
            f"  accuracy      : {self.accuracy:.3f}",
            f"  macro-F1      : {self.macro_f1:.3f}",
            f"  Cohen's kappa : {self.kappa:.3f}",
        ]
        for label, score in self.per_class_f1.items():
            lines.append(f"  F1 ({label:<4})   : {score:.3f}")
        lines.append(f"  confusion     : {self.labels_order} -> {self.confusion}")
        for note in self.notes:
            lines.append(f"  NOTE: {note}")
        return "\n".join(lines)


def evaluate_classification(records: list[EvaluationRecord],
                            dataset: str = "WESAD",
                            modality: str = "ECG") -> ClassificationReport:
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
