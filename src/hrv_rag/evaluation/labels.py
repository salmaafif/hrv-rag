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
    """Ground-truth stress level derived from the dataset."""

    LOW = "low"
    HIGH = "high"


#: WESAD phase -> ground truth. Only these two phases are used.
WESAD_PHASE_TO_LABEL: dict[Phase, TrueLabel] = {
    Phase.CALIBRATION: TrueLabel.LOW,
    Phase.QUESTION: TrueLabel.HIGH,
}


def true_label(phase: str, dataset: str = "WESAD") -> TrueLabel | None:
    """
    Ground-truth label for a phase, or None when the phase carries no label.

    Returning None rather than raising lets a caller feed in a whole table and have
    unlabelled rows filtered naturally, without special-casing at every call site.
    """
    if dataset != "WESAD":
        raise NotImplementedError(
            f"Label mapping for {dataset} is not defined yet "
            f"(SWELL-KW and UBFC-Phys are BACKLOG stages 7 and 8)."
        )
    try:
        return WESAD_PHASE_TO_LABEL.get(Phase(phase))
    except ValueError:
        return None


def predicted_label(stress_level: str) -> TrueLabel | None:
    """
    Map the model's four-way output onto the binary ground truth.

        low       -> LOW
        moderate  -> HIGH
        high      -> HIGH
        uncertain -> None (abstention)

    `moderate` is folded into HIGH because WESAD offers no middle condition: the
    subject is either at rest or undergoing TSST. Any elevation above baseline
    therefore belongs on the stressed side. This mapping will need revisiting for
    SWELL-KW, which genuinely has three levels.
    """
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
