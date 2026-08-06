"""
narrative.py — The hybrid path: rule decides the label, LLM writes the words.

    measurements
        -> rule assigns low / moderate / high      (features/stress_level.py)
        -> retrieve knowledge for the session      (retrieval.py)
        -> ONE call: explain the labels in Indonesian
        -> guards check nothing was invented       (guards.py)

Three things this buys over asking the model to classify:

- **The number stops moving.** The same recording gives the same label every time,
  which is the minimum before showing anything to a user.
- **One call instead of five.** About 1,500 input tokens per session rather than
  7,600, and roughly ten seconds of waiting rather than a minute.
- **Each part does what it is good at.** The rule reached macro-F1 0.828 on the
  development subjects; the model writes Indonesian that a person can act on.
  Neither can do the other's job well.

The retrieval query is built from the whole session rather than per question, since
one call needs one context. It names the strongest reaction and any disagreement
between features, because those are what the explanation has to account for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.settings import LLMConfig, settings
from ..core.schemas import SessionNarrative, StressLevel
from ..features.stress_level import StressVerdict
from .guards import (find_fabricated_citations, find_invented_numbers,
                     find_unknown_references)
from .llm import GeminiInterpreter
from .prompt import format_context, load_template
from .query_builder import FEATURE_LABELS, _magnitude_word
from .retrieval import KBIndex


@dataclass
class NarrativeInput:
    """One question's finished measurements, ready to be described."""

    question_no: int
    question_type: str
    verdict: StressVerdict
    reactivity: dict[str, float]
    recovery_pct: float | None
    recovery_note: str
    attribution_hint: str


@dataclass
class NarrativeResult:
    """The session's feedback plus the provenance needed to reproduce it."""

    narrative: SessionNarrative
    retrieved_ids: list[str]
    retrieval_scores: list[float]
    kb_version: str
    prompt_name: str
    model: str
    temperature: float
    invented_numbers: list[str] = field(default_factory=list)
    unknown_references: list[str] = field(default_factory=list)

    @property
    def is_trustworthy(self) -> bool:
        return not self.invented_numbers and not self.unknown_references


def build_session_query(inputs: list[NarrativeInput]) -> str:
    """
    One query describing the session, used to fetch context for the single call.

    Built around the strongest reaction rather than an average, because that is the
    question the feedback will spend most of its words on. Any disagreement between
    features is named explicitly so the chunk explaining atypical patterns can be
    retrieved — without it the model has nothing to reason from exactly when the
    reading is hardest.
    """
    if not inputs:
        return "interview session with no usable measurement"

    strongest = min(
        inputs,
        key=lambda i: i.reactivity.get("delta_pct_rmssd", 0.0),
    )
    parts = []
    for feature in ("rmssd", "mean_hr"):
        value = strongest.reactivity.get(f"delta_pct_{feature}")
        if value is None or value != value:
            continue
        parts.append(f"{FEATURE_LABELS.get(feature, feature)} "
                     f"{_magnitude_word(value)} baseline")

    query = "; ".join(parts) if parts else "measurements unavailable"
    query += f"; during a {strongest.question_type} question"

    levels = {i.verdict.level for i in inputs}
    if StressLevel.HIGH in levels:
        query += "; strong stress response on at least one question"

    if any("disagree" in e for i in inputs for e in i.verdict.evidence):
        query += ("; vagal features rose while heart rate also rose, "
                  "an atypical pattern")

    if any(i.recovery_pct is not None for i in inputs):
        query += "; how quickly the person returned to calm afterwards"

    return query


def _format_questions(inputs: list[NarrativeInput]) -> str:
    """
    Render the per-question block for the prompt.

    The label is stated as already decided, and the evidence behind it is shown so
    the model can explain the reasoning rather than guess at it. Recovery that could
    not be measured says so — reporting it as zero would tell the model the person
    failed to settle when in fact nothing was measured.
    """
    blocks = []
    for i in inputs:
        recovery = (f"{i.recovery_pct:.0f}% of the deviation returned towards baseline"
                    if i.recovery_pct is not None
                    else f"not measurable ({i.recovery_note})")
        blocks.append(
            f"**Question {i.question_no}** ({i.question_type})\n"
            f"- Stress level (decided by rule, do not change): "
            f"**{i.verdict.level.value}**\n"
            f"- Evidence: {'; '.join(i.verdict.evidence)}\n"
            f"- Recovery: {recovery}\n"
            f"- Likely driver: {i.attribution_hint}"
        )
    return "\n\n".join(blocks)


class NarrativeWriter:
    """Turns a finished session into Indonesian feedback, in one call."""

    def __init__(self, index: KBIndex | None = None,
                 interpreter: GeminiInterpreter | None = None,
                 cfg: LLMConfig | None = None) -> None:
        self.cfg = cfg or settings.llm
        self.index = index or KBIndex.load()
        self.interpreter = interpreter or GeminiInterpreter(self.cfg)

    def write(self, inputs: list[NarrativeInput], session_id: str,
              modality: str, device: str, signal_quality: str,
              resilience: str, most_triggering: int | None,
              recovery_summary: str, confounders: list[str],
              baseline_note: str = "") -> NarrativeResult:
        """Fetch context, fill the template, make one call, verify the result."""
        chunks = self.index.search(build_session_query(inputs))

        template = load_template(self.cfg.narrative_prompt)
        prompt = template.format(
            context=format_context(chunks),
            session_id=session_id,
            modality=modality,
            device=device,
            signal_quality=signal_quality,
            confounders=", ".join(confounders) if confounders else "none reported",
            baseline_note=(f"- Baseline warning: {baseline_note}\n"
                           if baseline_note else ""),
            questions=_format_questions(inputs),
            resilience=resilience,
            most_triggering=(f"question {most_triggering}"
                             if most_triggering else "not determined"),
            recovery_summary=recovery_summary,
        )

        narrative = self.interpreter.interpret_as(prompt, SessionNarrative)
        retrieved_ids = [c.chunk.id for c in chunks]

        # The guards run over the Indonesian text too. The user-facing wording is
        # supposed to contain no numbers at all, so anything numeric appearing there
        # is either a quotation from the prompt or an invention — and both are worth
        # knowing about.
        checked = " ".join(
            [q.explanation + " " + q.suggestion for q in narrative.questions]
            + [narrative.session_summary, narrative.encouragement,
               narrative.uncertainty_notes]
        )

        return NarrativeResult(
            narrative=narrative,
            retrieved_ids=retrieved_ids,
            retrieval_scores=[c.similarity for c in chunks],
            kb_version=self.index.kb_version,
            prompt_name=self.cfg.narrative_prompt,
            model=self.cfg.model,
            temperature=self.cfg.temperature,
            invented_numbers=find_invented_numbers(checked, prompt),
            unknown_references=(
                find_unknown_references(narrative.references, retrieved_ids)
                + find_fabricated_citations(checked, retrieved_ids)
            ),
        )
