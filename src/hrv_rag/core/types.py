"""
types.py — Domain objects shared across modules.

Why dataclasses instead of plain dicts? A dict enforces nothing: a mistyped key
only surfaces at runtime, often as a silently wrong number. Dataclasses document
the shape of the data explicitly, which matters for code that has to be defended
line by line at the thesis defence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class Modality(str, Enum):
    """
    Source modality of the signal.

    Carried all the way through to the LLM prompt (Mandatory Rule #5): ECG is the
    reference, whereas PPG is validated against it and is more vulnerable to motion
    artefacts, so the confidence score must be adjusted accordingly.
    """

    ECG = "ECG"
    PPG = "PPG"


class Phase(str, Enum):
    """
    Phase within a single session.

    During validation the phase is filled from dataset labels (WESAD label 1 ->
    CALIBRATION, label 2 -> QUESTION). In production it comes from the real session
    timeline. The schema is deliberately identical so that the RAG and evaluation
    code never has to branch on which one it is looking at.
    """

    ADAPTATION = "adaptation"
    CALIBRATION = "calibration"   # -> personal baseline
    BRIEFING = "briefing"         # -> session-level anticipation
    QUESTION = "question"         # -> reactivity
    RECOVERY = "recovery"         # -> recovery


@dataclass(frozen=True)
class QualityReport:
    """Result of checking raw signal quality, before any filtering."""

    clipping_ratio: float          # fraction of samples pinned at extreme values
    flatline_ratio: float          # fraction of duration with a flat signal
    is_acceptable: bool            # passed every threshold?
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary for printing or for inclusion in the prompt."""
        status = "good" if self.is_acceptable else "questionable"
        return (f"quality {status} "
                f"(clipping {self.clipping_ratio:.1%}, "
                f"flat-line {self.flatline_ratio:.1%})")


@dataclass
class RRSeries:
    """
    Inter-beat interval series — the standard output of EVERY preprocessing branch.

    This is where the two modalities meet: ECG derives it from R peaks, PPG from
    systolic peaks. After this point the downstream code (features, RAG, evaluation)
    no longer needs to know where the signal came from — except through the
    `modality` attribute, which is deliberately carried forward.
    """

    rr_ms: np.ndarray              # intervals, milliseconds
    t_sec: np.ndarray              # time of each interval, seconds
    modality: Modality
    subject: str
    phase: Phase
    quality: QualityReport
    is_outlier: np.ndarray         # per-beat flags from ectopic correction

    def __post_init__(self) -> None:
        # All three arrays must be the same length. If they are not, something
        # upstream is broken, and it is far better to find out here than to see it
        # later disguised as a strange feature value.
        n = len(self.rr_ms)
        if not (len(self.t_sec) == len(self.is_outlier) == n):
            raise ValueError(
                f"Inconsistent array lengths: rr_ms={n}, "
                f"t_sec={len(self.t_sec)}, is_outlier={len(self.is_outlier)}"
            )

    @property
    def n_beats(self) -> int:
        return len(self.rr_ms)

    @property
    def duration_sec(self) -> float:
        return float(self.t_sec[-1] - self.t_sec[0]) if self.n_beats else 0.0

    @property
    def outlier_ratio(self) -> float:
        """Fraction of beats flagged as artefacts — a measure of series quality."""
        return float(self.is_outlier.mean()) if self.n_beats else 1.0

    def describe(self) -> str:
        return (f"{self.subject}/{self.phase.value} [{self.modality.value}]: "
                f"{self.n_beats} beats, {self.duration_sec:.0f} s, "
                f"outliers {self.outlier_ratio:.1%}, {self.quality.summary()}")
