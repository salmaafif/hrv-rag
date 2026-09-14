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


#: Heart-rate bounds, the same physiology the interval path enforces
#: (`QualityConfig.rr_min_sec`/`rr_max_sec`: 300-2000 ms, i.e. 200-30 bpm). One
#: source for both, so a value accepted here is never silently flagged as an
#: ectopic beat once rebuilt.
MIN_BPM = 60.0 / settings.quality.rr_max_sec
MAX_BPM = 60.0 / settings.quality.rr_min_sec


class BpmSample(BaseModel):
    """One heart-rate report from a device that does not deliver beat intervals."""

    #: Seconds from the FIRST sample of the recording — the recording's own clock,
    #: the same one `offset_sec` is measured on. Never the device's wall clock.
    at_sec: float = Field(ge=0)
    bpm: float = Field(ge=MIN_BPM, le=MAX_BPM)


class AnalyzeRequest(BaseModel):
    """A recording, plus what is needed to interpret it."""

    #: Beat-to-beat intervals in milliseconds, from a Bluetooth sensor.
    rr_ms: list[float] | None = None
    #: Raw CSV text, when the recording was uploaded as a file.
    csv: str | None = None

    #: Heart-rate reports, from a device that may not deliver beat intervals.
    bpm_samples: list[BpmSample] | None = None
    #: Fraction of the session covered by real beat intervals. Decides which path
    #: the session takes (`settings.tier.min_rr_coverage`); required whenever both
    #: `rr_ms` and `bpm_samples` are sent, because without it the choice is a guess.
    rr_coverage: float | None = Field(default=None, ge=0.0, le=1.0)

    #: `offset_sec`, measured on the heart-rate report clock instead.
    #:
    #: A live device sending both streams has two clocks: the beat intervals add
    #: up to one, the reports' own timestamps make the other, and the two drift
    #: apart whenever beats go missing — which is exactly when a session falls to
    #: heart rate. `offset_sec` belongs to the interval clock. When the session is
    #: scored from heart rate, this one places the questions; when it is omitted,
    #: `offset_sec` serves both.
    bpm_offset_sec: float | None = Field(default=None, ge=0.0, le=1800.0)

    baseline_minutes: float = Field(ge=MIN_BASELINE_MINUTES, le=8)
    modality: str = Field(pattern="^(ECG|PPG)$")

    #: Anonymous. Never a name, an email, or a student number.
    session_id: str = "session"

    #: How many seconds of recording already existed when the session clock
    #: reached zero.
    #:
    #: Zero for an uploaded file, where the recording and the session begin
    #: together. Non-zero whenever a Bluetooth sensor was connected before the
    #: person pressed start — the sensor streams from the moment it pairs, so the
    #: array can begin minutes earlier than every timestamp the caller reports.
    #: Left unstated, that difference silently shifts both the resting period and
    #: every question window.
    offset_sec: float = Field(default=0.0, ge=0.0, le=1800.0)

    #: Include feature names, scores and evidence in the response.
    #:
    #: Off by default. Those fields must not reach an end user, and an API cannot
    #: police what its caller renders — so the compliant response is the one
    #: returned to an integrator who never thinks about it.
    include_technical: bool = False

    #: The person agreed to their recording being kept for research.
    #:
    #: Off by default, and the flag alone stores nothing: the server must also
    #: have `HRV_ARCHIVE_DIR` configured (two locks — the caller holds consent,
    #: the operator holds the destination; see `services/archive.py`). Consent
    #: is a statement by the CALLER, who is the only party that ever met the
    #: person; this module has no identity to attach it to, by design (A1).
    store_consented: bool = False

    @model_validator(mode="after")
    def _one_coherent_recording(self) -> "AnalyzeRequest":
        live = bool(self.rr_ms) or bool(self.bpm_samples)
        if not live and not self.csv:
            raise ValueError("send rr_ms, bpm_samples, or csv")
        if self.csv and live:
            # Refused rather than silently preferring one. Two recordings both
            # produce a complete report, and only one of them is the session the
            # person actually did.
            raise ValueError("send either a csv file or a live recording, not both")
        if self.rr_ms and self.bpm_samples and self.rr_coverage is None:
            raise ValueError(
                "rr_coverage is required when both rr_ms and bpm_samples are sent"
            )
        return self


class SessionRequest(AnalyzeRequest):
    """An interview session: the caller supplies when each question was asked."""

    questions: list[QuestionTimelineEntry] = Field(min_length=1)
