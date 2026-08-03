"""
schemas.py — Input and output contracts for the assessment step.

Two design points matter here.

FIRST, the input schema is deliberately IDENTICAL for validation and production.
During validation the phase and question metadata come from dataset labels; in
production they come from the real session timeline. Because the shape is the same,
neither the RAG code nor the evaluation code ever has to branch on which one it is
looking at — which is what lets the thesis claim "the system that was validated is
the system that runs".

SECOND, the output has TWO LAYERS (decision K4):
  - the technical layer keeps every number and the chain of reasoning, in English,
    and is what gets written to CSV and audited at the defence;
  - the user layer is plain Indonesian, because KARIRLINK's users are Indonesian
    and must never be shown RMSSD or LF/HF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field

from .types import Modality, Phase


class StressLevel(str, Enum):
    """
    Stress level assigned by the LLM.

    UNCERTAIN is a first-class answer, not a failure. When the retrieved context
    does not support a conclusion — or when the evidence genuinely conflicts, as
    with the inverted patterns seen in subjects S6 and S10 — saying so is the
    correct response. Forcing a label in those cases would be exactly the
    hallucination Mandatory Rule #3 forbids.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNCERTAIN = "uncertain"


#: Indonesian labels for display. The data layer stays English; only the user
#: layer is translated, at the moment of presentation.
STRESS_LEVEL_ID: dict[str, str] = {
    "low": "tekanan rendah",
    "moderate": "tekanan sedang",
    "high": "tekanan tinggi",
    "uncertain": "belum dapat dipastikan",
}


@dataclass
class SignalQuality:
    """Signal quality carried into the prompt so the LLM can weigh its confidence."""

    outlier_pct: float
    is_acceptable: bool
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        status = "good" if self.is_acceptable else "questionable"
        text = f"{status}, {self.outlier_pct:.1f}% of beats interpolated"
        return f"{text} ({'; '.join(self.notes)})" if self.notes else text


@dataclass
class AssessmentInput:
    """
    Everything needed to assess one 60-second segment.

    Every numeric field here is computed by Python before this object is built.
    The LLM receives finished numbers and is never asked to derive any of them.
    """

    session_id: str                       # anonymised; never a name or student ID
    modality: Modality
    device: str                           # e.g. "RespiBAN chest strap, 700 Hz"
    phase: Phase
    segment_index: int

    features: dict[str, float]            # absolute values, e.g. rmssd -> 31.7
    reactivity: dict[str, float]          # percent change vs the personal baseline
    signal_quality: SignalQuality

    question_no: int | None = None
    question_type: str | None = None      # "behavioural", "technical", ...
    recovery_pct: float | None = None     # None = not computable
    recovery_note: str = ""
    confounders: list[str] = field(default_factory=list)
    baseline_note: str = ""               # e.g. an unsteady baseline warning


class LLMResponse(BaseModel):
    """
    The structured JSON contract the model must return.

    Passed straight to the Gemini API as a response schema, so the model is
    constrained to this shape rather than being asked politely for JSON.
    """

    stress_level: StressLevel = Field(
        description="One of: low, moderate, high, uncertain."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence between 0 and 1. Lower it for PPG data, poor "
                    "signal quality, or conflicting evidence.",
    )
    reasoning: str = Field(
        description="English, 3-5 sentences maximum. Why this level was chosen, "
                    "referring only to the supplied measurements and the "
                    "retrieved context. Be concise: long reasoning risks the "
                    "response being truncated."
    )
    references: list[str] = Field(
        description="IDs of the context chunks that support the reasoning, "
                    "e.g. KB-RMSSD-01. Only IDs present in the CONTEXT."
    )
    uncertainty_notes: str = Field(
        default="",
        description="English. Anything that weakens the conclusion: modality, "
                    "signal quality, confounders, conflicting features."
    )
    user_summary: str = Field(
        description="INDONESIAN, plain language for the end user. No feature "
                    "names, no numbers such as RMSSD or LF/HF. Two sentences."
    )
    user_recommendation: str = Field(
        description="INDONESIAN. One concrete, trainable suggestion. Describe "
                    "behaviour, never a personal trait."
    )


@dataclass
class Assessment:
    """One completed assessment, in both layers, with full provenance."""

    # --- provenance, needed for reproducibility (BACKLOG D2.5) ---
    session_id: str
    segment_index: int
    modality: str
    phase: str
    kb_version: str
    prompt_version: str
    model: str
    temperature: float
    retrieved_ids: list[str]
    retrieval_scores: list[float]

    # --- what the LLM produced ---
    response: LLMResponse

    # --- guard results (Mandatory Rule #1) ---
    invented_numbers: list[str] = field(default_factory=list)
    unknown_references: list[str] = field(default_factory=list)

    @property
    def is_trustworthy(self) -> bool:
        """False when a guard caught the model inventing numbers or citations."""
        return not self.invented_numbers and not self.unknown_references

    def user_view(self) -> dict[str, str]:
        """The user layer — Indonesian, no technical terms (decision K4)."""
        return {
            "tingkat_tekanan": STRESS_LEVEL_ID[self.response.stress_level.value],
            "ringkasan": self.response.user_summary,
            "rekomendasi": self.response.user_recommendation,
        }

    def technical_view(self) -> dict[str, object]:
        """The technical layer — every number, for CSV and for the defence."""
        return {
            "session_id": self.session_id,
            "segment": self.segment_index,
            "modality": self.modality,
            "phase": self.phase,
            "stress_level": self.response.stress_level.value,
            "confidence": self.response.confidence,
            "reasoning": self.response.reasoning,
            "references": ";".join(self.response.references),
            "uncertainty_notes": self.response.uncertainty_notes,
            "retrieved_ids": ";".join(self.retrieved_ids),
            "retrieval_scores": ";".join(f"{s:.3f}" for s in self.retrieval_scores),
            "kb_version": self.kb_version,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "temperature": self.temperature,
            "invented_numbers": ";".join(self.invented_numbers),
            "unknown_references": ";".join(self.unknown_references),
            "is_trustworthy": self.is_trustworthy,
        }
