"""
session.py — The session timeline, and how segments group into questions.

Everything else in this project works on 60-second segments. The product does not:
a user finishes an interview and expects ONE report about ONE session. This module
is the bridge between the two.

The unit of assessment is the QUESTION, not the segment. Three reasons:

1. It matches how people understand their own results. Nobody asks "how was I at
   minute seven"; they ask "which question rattled me".
2. It keeps the number of LLM calls sane. A 15-minute session yields about 13
   assessable segments but only about 5 questions, so the user waits one minute
   instead of three.
3. Recovery only exists at question level anyway — it compares the answer window
   against the gap that follows it, which is a property of the question, not of any
   single segment.

A question therefore owns the segments that overlap its answer window, plus the
segment in the gap that follows when there is one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QuestionType(str, Enum):
    """
    Kind of question, used to interpret the reaction rather than to measure it.

    The physiological signature of cognitive load is practically identical to that
    of social-evaluative pressure, so HRV alone cannot separate them. What separates
    them is what the person was actually doing. This field carries that context into
    the prompt, and the resulting attribution must always be phrased as a hypothesis.
    """

    INTRODUCTION = "introduction"     # tell me about yourself — social pressure
    BEHAVIOURAL = "behavioural"       # describe a time when — social pressure
    TECHNICAL = "technical"           # explain how X works — cognitive load
    NUMERICAL = "numerical"           # estimate / calculate — cognitive load
    SITUATIONAL = "situational"       # what would you do if — mixed

    @property
    def leans_cognitive(self) -> bool:
        """Whether this type is expected to load thinking more than self-image."""
        return self in (QuestionType.TECHNICAL, QuestionType.NUMERICAL)


@dataclass(frozen=True)
class Question:
    """One interview question and the time window it occupied."""

    number: int
    text: str
    qtype: QuestionType
    answer_start_sec: float
    answer_end_sec: float

    #: End of the quiet gap after the answer. None when the gap was too short to
    #: yield a segment, in which case recovery simply is not reported for this
    #: question — as opposed to being reported as zero.
    gap_end_sec: float | None = None

    #: Flagged difficult, which is what earns a full 60-second recovery gap.
    is_difficult: bool = False

    @property
    def has_recovery_window(self) -> bool:
        return self.gap_end_sec is not None


@dataclass
class SessionTimeline:
    """
    The full timeline of one recorded session.

    Filled from the real session in production, and from dataset labels during
    validation. Keeping one shape for both is what lets the same pipeline serve
    both purposes without branching.
    """

    session_id: str                  # anonymous; never a name or student number
    calibration_start_sec: float
    calibration_end_sec: float
    questions: list[Question] = field(default_factory=list)

    briefing_start_sec: float | None = None
    briefing_end_sec: float | None = None

    #: Self-reported factors that can mimic or mask a stress response.
    confounders: list[str] = field(default_factory=list)

    def question_by_number(self, number: int) -> Question:
        for q in self.questions:
            if q.number == number:
                return q
        raise KeyError(f"Question {number} is not in this session.")

    @property
    def n_questions(self) -> int:
        return len(self.questions)

    def describe(self) -> str:
        difficult = sum(1 for q in self.questions if q.is_difficult)
        return (f"session {self.session_id}: {self.n_questions} questions "
                f"({difficult} marked difficult), calibration "
                f"{self.calibration_end_sec - self.calibration_start_sec:.0f}s")
