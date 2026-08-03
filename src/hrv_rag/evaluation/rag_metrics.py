"""
rag_metrics.py — Metrics with no counterpart in a deep-learning pipeline.

A trained model is deterministic at inference and cites nothing, so these questions
never arise. A RAG system is stochastic and does cite, which creates three
obligations that CLAUDE.md lists as mandatory:

  - **Consistency** (T5.4): does the same prompt give the same answer?
  - **Faithfulness** (T5.6): is every claim actually supported by what was retrieved?
  - **Confidence calibration** (T5.7): does high confidence really mean more correct?

Together these test whether the interpretation can be trusted, as opposed to merely
being accurate on average.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .labels import EvaluationRecord


# =========================================================== consistency
@dataclass
class ConsistencyReport:
    """Variation across repeated runs of one identical prompt."""

    n_runs: int
    levels: list[str]
    confidences: list[float]
    reference_sets: list[frozenset[str]]

    @property
    def label_agreement(self) -> float:
        """Fraction of runs that produced the most common label."""
        if not self.levels:
            return 0.0
        return Counter(self.levels).most_common(1)[0][1] / len(self.levels)

    @property
    def confidence_range(self) -> float:
        return max(self.confidences) - min(self.confidences) if self.confidences else 0.0

    @property
    def reference_agreement(self) -> float:
        """
        Fraction of runs citing the most common set of chunks.

        Tracked separately from the label because the two can diverge: a model may
        reach the same conclusion by citing different knowledge each time. That is
        worth knowing, since it weakens any claim that the reasoning is grounded.
        """
        if not self.reference_sets:
            return 0.0
        return (Counter(self.reference_sets).most_common(1)[0][1]
                / len(self.reference_sets))

    @property
    def is_stable(self) -> bool:
        return self.label_agreement == 1.0 and self.confidence_range < 0.1

    def summary(self) -> str:
        return (f"{self.n_runs} runs | label agreement {self.label_agreement:.0%} "
                f"| confidence spread {self.confidence_range:.2f} "
                f"| citation agreement {self.reference_agreement:.0%} "
                f"| {'stable' if self.is_stable else 'UNSTABLE'}")


def measure_consistency(assessments: list) -> ConsistencyReport:
    """Summarise a list of assessments produced from the same input."""
    return ConsistencyReport(
        n_runs=len(assessments),
        levels=[a.response.stress_level.value for a in assessments],
        confidences=[a.response.confidence for a in assessments],
        reference_sets=[frozenset(a.response.references) for a in assessments],
    )


# ========================================================== faithfulness
@dataclass
class FaithfulnessReport:
    """How well the output stayed anchored to the retrieved knowledge."""

    n_total: int
    n_cited_nothing: int
    n_unknown_reference: int
    n_invented_number: int
    n_cited_unretrieved_only: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def clean_rate(self) -> float:
        """Fraction of outputs with no citation or numeric violation."""
        if not self.n_total:
            return 0.0
        bad = self.n_unknown_reference + self.n_invented_number
        return max(0.0, (self.n_total - bad) / self.n_total)

    def summary(self) -> str:
        lines = [
            f"  assessments        : {self.n_total}",
            f"  clean rate         : {self.clean_rate:.1%}",
            f"  cited nothing      : {self.n_cited_nothing}",
            f"  unknown citation   : {self.n_unknown_reference}",
            f"  invented numbers   : {self.n_invented_number}",
        ]
        lines.extend(f"  example: {e}" for e in self.examples[:5])
        return "\n".join(lines)


def measure_faithfulness(assessments: list) -> FaithfulnessReport:
    """
    Audit citations and numbers across a batch of assessments.

    This consumes the per-assessment guard results rather than recomputing them, so
    the batch report and the individual records can never disagree.

    "Cited nothing" is tracked but not counted as a violation: an output that
    declares uncertainty without citing knowledge is behaving correctly, since there
    was no supporting knowledge to cite.
    """
    report = FaithfulnessReport(n_total=len(assessments), n_cited_nothing=0,
                                n_unknown_reference=0, n_invented_number=0)

    for a in assessments:
        if not a.response.references:
            report.n_cited_nothing += 1
        if a.unknown_references:
            report.n_unknown_reference += 1
            report.examples.append(
                f"{a.session_id} seg {a.segment_index}: cited "
                f"{a.unknown_references} which was never retrieved"
            )
        if a.invented_numbers:
            report.n_invented_number += 1
            report.examples.append(
                f"{a.session_id} seg {a.segment_index}: numbers "
                f"{a.invented_numbers} do not appear in the prompt"
            )
    return report


# ==================================================== confidence calibration
@dataclass
class CalibrationBin:
    """Accuracy within one confidence band."""

    lower: float
    upper: float
    n: int
    accuracy: float

    def summary(self) -> str:
        return (f"  confidence {self.lower:.1f}-{self.upper:.1f}: "
                f"n={self.n:<4} accuracy={self.accuracy:.3f}")


def measure_calibration(records: list[EvaluationRecord],
                        edges: tuple[float, ...] = (0.0, 0.5, 0.7, 0.9, 1.01)
                        ) -> list[CalibrationBin]:
    """
    Group judged segments by confidence and report accuracy in each band.

    A well-calibrated system is more often right when it claims to be confident. If
    accuracy is flat across the bands, the confidence score carries no information
    and should not be shown to users as though it did.

    Abstentions are excluded, since they have no correctness to measure.
    """
    judged = [r for r in records if not r.abstained]
    bins: list[CalibrationBin] = []

    for lo, hi in zip(edges[:-1], edges[1:]):
        rows = [r for r in judged if lo <= r.confidence < hi]
        accuracy = (sum(1 for r in rows if r.correct) / len(rows)) if rows else float("nan")
        bins.append(CalibrationBin(lo, min(hi, 1.0), len(rows), accuracy))
    return bins
