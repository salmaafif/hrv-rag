"""
schemas.py — what callers may send.

Validation is strict on purpose. Every field here is something the analysis
divides by, slices with, or reports as provenance, and a wrong value produces a
complete, confident report about the wrong thing rather than an error. Catching it
at the edge is the only place it is still cheap.

The response side is intentionally NOT modelled as Pydantic types. The contract
lives in `frontend/src/types/api.ts`, which the web team already has, and keeping a
second declaration of the same shapes here would give it somewhere to drift to.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from hrv_rag.config.settings import settings

#: Shortest resting period that produces any baseline window at all.
#:
#: Not a style preference. Features are computed over 60-second windows, so one
#: minute of rest yields a beat series spanning about 59 seconds — measured first
#: beat to last, not from when the timer started — and nothing fits. The result is
#: not a weaker baseline but no baseline, which leaves the session unscoreable.
MIN_BASELINE_MINUTES = settings.session.calibration_sec / 60.0


class QuestionTimelineEntry(BaseModel):
    """When one question was asked, in seconds from the start of the recording."""

    number: int
    text: str
    type: str = Field(pattern="^(introduction|behavioural|technical|numerical"
                              "|situational)$")
    answer_start_sec: float = Field(ge=0)
    answer_end_sec: float = Field(ge=0)
    #: End of the quiet stretch after the answer. Equal to `answer_end_sec` when
    #: no gap was observed — which means recovery is NOT MEASURABLE, and is a
    #: different statement from a recovery of zero.
    gap_end_sec: float = Field(ge=0)
    is_difficult: bool = False

    @model_validator(mode="after")
    def _times_run_forwards(self) -> "QuestionTimelineEntry":
        if self.answer_end_sec <= self.answer_start_sec:
            raise ValueError(
                f"question {self.number}: answer_end_sec must come after "
                f"answer_start_sec"
            )
        if self.gap_end_sec and self.gap_end_sec < self.answer_end_sec:
            raise ValueError(
                f"question {self.number}: gap_end_sec cannot precede the answer"
            )
        return self


class AnalyzeRequest(BaseModel):
    """A recording, plus what is needed to interpret it."""

    #: Beat-to-beat intervals in milliseconds, from a Bluetooth sensor.
    rr_ms: list[float] | None = None
    #: Raw CSV text, when the recording was uploaded as a file.
    csv: str | None = None

    baseline_minutes: float = Field(ge=MIN_BASELINE_MINUTES, le=8)
    modality: str = Field(pattern="^(ECG|PPG)$")

    #: Anonymous. Never a name, an email, or a student number.
    session_id: str = "session"

    #: Include feature names, scores and evidence in the response.
    #:
    #: Off by default. Those fields must not reach an end user, and an API cannot
    #: police what its caller renders — so the compliant response is the one
    #: returned to an integrator who never thinks about it.
    include_technical: bool = False

    @model_validator(mode="after")
    def _exactly_one_recording(self) -> "AnalyzeRequest":
        if not self.rr_ms and not self.csv:
            raise ValueError("send either rr_ms or csv")
        if self.rr_ms and self.csv:
            # Refused rather than silently preferring one. Two recordings both
            # produce a complete report, and only one of them is the session the
            # person actually did.
            raise ValueError("send only one of rr_ms or csv, not both")
        return self


class TimelineRequest(AnalyzeRequest):
    """V1: no question timings, so every window is scored on its own."""


class SessionRequest(AnalyzeRequest):
    """V2 and V3: the caller supplies when each question was asked."""

    questions: list[QuestionTimelineEntry] = Field(min_length=1)
