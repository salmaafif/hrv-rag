"""
labels.py — Ground truth and how model output maps onto it.

Two mappings live here, and keeping them explicit matters because both encode
choices an examiner can reasonably challenge.

GROUND TRUTH. WESAD is effectively binary: the baseline phase is low stress, the
TSST phase is high stress. Amusement is excluded entirely (decision K7) because it
is positive arousal rather than pressure. SWELL-KW will later supply three levels,
and UBFC-Phys is not a classification task at all — which is exactly why metrics
are reported per dataset and never pooled.

PREDICTIONS. The system may answer `uncertain`, and that is a designed behaviour
rather than a failure. Treating it as a wrong answer would punish the system for
being honest when evidence conflicts, and treating it as correct would reward
evasion. It is therefore counted as an ABSTENTION: excluded from the accuracy
figures, and reported separately as coverage. Both numbers must be quoted together
— high accuracy over a small covered fraction is not a good result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..core.types import Phase


class TrueLabel(str, Enum):
    """
    Ground-truth stress level derived from the dataset.

    Ordinal, not nominal: LOW < MODERATE < HIGH. MODERATE exists only because
    SWELL-KW supplies a genuine middle condition. WESAD never uses it — a subject
    there is either resting or undergoing TSST — so which labels are in play is a
    property of the DATASET and is declared per mapping below, never assumed.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


#: WESAD phase -> ground truth. Only these two phases are used.
WESAD_PHASE_TO_LABEL: dict[Phase, TrueLabel] = {
    Phase.CALIBRATION: TrueLabel.LOW,
    Phase.QUESTION: TrueLabel.HIGH,
}

#: SWELL-KW condition -> ground truth, the three-level gradient WESAD cannot give.
#:
#: The ordering follows the experiment's own design rather than an interpretation
#: of it. Neutral is the ordinary working condition; time pressure removes a third
#: of the available time; interruption adds eight unexpected emails ON TOP of the
#: task. Each step adds a demand without removing the previous one.
#:
#: `calibration` is the rest block, and it anchors each subject's personal
#: baseline instead of being scored — the same role WESAD's baseline phase plays.
SWELL_PHASE_TO_LABEL: dict[str, TrueLabel] = {
    "no_stress": TrueLabel.LOW,
    "time_pressure": TrueLabel.MODERATE,
    "interruption": TrueLabel.HIGH,
}

#: Which labels each dataset can actually produce. Reported metrics must be built
#: from this rather than from whatever happens to appear in a sample, or a class
#: that is merely absent from one day's data looks like a class the system failed
#: on (see `evaluate_classification`).
DATASET_LABELS: dict[str, list[TrueLabel]] = {
    "WESAD": [TrueLabel.LOW, TrueLabel.HIGH],
    "SWELL": [TrueLabel.LOW, TrueLabel.MODERATE, TrueLabel.HIGH],
}


def true_label(phase: str, dataset: str = "WESAD") -> TrueLabel | None:
    """
    Ground-truth label for a phase, or None when the phase carries no label.

    Returning None rather than raising lets a caller feed in a whole table and have
    unlabelled rows filtered naturally, without special-casing at every call site.
    Rest and calibration blocks return None for exactly that reason: they define
    the baseline, so scoring the system against them would be marking it on the
    reference it was handed.
    """
    if dataset == "WESAD":
        try:
            return WESAD_PHASE_TO_LABEL.get(Phase(phase))
        except ValueError:
            return None
    if dataset == "SWELL":
        return SWELL_PHASE_TO_LABEL.get(phase)
    raise NotImplementedError(
        f"Label mapping for {dataset} is not defined yet "
        f"(UBFC-Phys is BACKLOG stage 8)."
    )


def predicted_label(stress_level: str,
                    dataset: str = "WESAD") -> TrueLabel | None:
    """
    Map the system's four-way output onto whatever labels the dataset supports.

    On WESAD, `moderate` is folded into HIGH, because there is no middle condition
    to map it to: the subject is either at rest or undergoing TSST, so any
    elevation above baseline belongs on the stressed side.

    On SWELL-KW the three levels are kept apart, and that is the point of using it.
    The upper threshold of the scoring rule could never be calibrated on WESAD —
    with only two conditions, "moderate" and "high" both landed in the same class
    and every candidate threshold scored identically (BACKLOG T2c.10). SWELL is the
    first dataset where that boundary is answerable at all.

    `uncertain` is an abstention under either mapping.
    """
    if dataset == "SWELL":
        return {
            "low": TrueLabel.LOW,
            "moderate": TrueLabel.MODERATE,
            "high": TrueLabel.HIGH,
            "uncertain": None,
        }.get(stress_level)

    return {
        "low": TrueLabel.LOW,
        "moderate": TrueLabel.HIGH,
        "high": TrueLabel.HIGH,
        "uncertain": None,
    }.get(stress_level)


@dataclass
class EvaluationRecord:
    """One assessed segment, reduced to what the metrics need."""

    subject: str
    phase: str
    segment: int
    modality: str
    truth: TrueLabel
    predicted: TrueLabel | None       # None = the system abstained
    raw_level: str                    # the original four-way answer
    confidence: float
    references: list[str]
    retrieved_ids: list[str]
    reasoning: str
    is_trustworthy: bool

    @property
    def abstained(self) -> bool:
        return self.predicted is None

    @property
    def correct(self) -> bool | None:
        """None when the system abstained — neither right nor wrong."""
        return None if self.abstained else self.predicted == self.truth
