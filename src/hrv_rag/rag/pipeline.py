"""
pipeline.py — Wires the RAG stages together into one assessment.

The chain, for a single 60-second segment:

    computed features
        -> textual query          (query_builder)
        -> retrieve chunks        (retrieval)
        -> assemble prompt        (prompt)
        -> Gemini                 (llm)
        -> verify the output      (guards)
        -> Assessment (two layers)

Nothing here computes an HRV number. By the time a segment reaches this module,
every measurement is final; this module only arranges them, fetches knowledge, and
records what came back — including the provenance needed to reproduce it later.
"""

from __future__ import annotations

from ..config.settings import LLMConfig, settings
from ..core.schemas import Assessment, AssessmentInput
from .guards import (find_fabricated_citations, find_invented_numbers,
                     find_unknown_references)
from .llm import BaseInterpreter, make_interpreter
from .prompt import build_prompt
from .query_builder import build_query
from .retrieval import KBIndex


class AssessmentPipeline:
    """
    Runs the full retrieve-then-interpret chain.

    Holds the KB index and the API clients so they are built once and reused across
    many segments — loading the index and opening a client per segment would be
    wasteful, and the index in particular must stay identical across a whole run for
    the results to be comparable.
    """

    def __init__(self, index: KBIndex | None = None,
                 interpreter: BaseInterpreter | None = None,
                 cfg: LLMConfig | None = None) -> None:
        self.cfg = cfg or settings.llm
        self.index = index or KBIndex.load()
        self.interpreter = interpreter or make_interpreter(self.cfg)

    def assess(self, data: AssessmentInput,
               temperature: float | None = None) -> Assessment:
        """Assess one segment and return both output layers with full provenance."""
        query = build_query(data)
        chunks = self.index.search(query)
        prompt = build_prompt(data, chunks, version=self.cfg.prompt_version)

        temp = temperature if temperature is not None else self.cfg.temperature
        response = self.interpreter.interpret(prompt, temperature=temp)

        # Guards run against the prompt that was actually sent, so the check covers
        # both the supplied measurements and the retrieved knowledge.
        #
        # EVERY generated field is checked, including the two the user actually
        # reads. Only `reasoning` and `uncertainty_notes` used to be, which left the
        # Indonesian summary and recommendation — the only text a KARIRLINK user
        # ever sees — completely unguarded. A response could tell someone their
        # heart rate rose 47% and their stress scored 8 out of 10, with all four
        # numbers invented, and still be recorded as trustworthy.
        checked_text = " ".join([
            response.reasoning,
            response.uncertainty_notes,
            response.user_summary,
            response.user_recommendation,
        ])
        retrieved_ids = [c.chunk.id for c in chunks]

        return Assessment(
            session_id=data.session_id,
            segment_index=data.segment_index,
            modality=data.modality.value,
            phase=data.phase.value,
            kb_version=self.index.kb_version,
            prompt_version=self.cfg.prompt_version,
            # What actually answered, not what was configured — the two differ as
            # soon as more than one backend exists, and provenance must name the
            # real one (U4.4).
            model=self.interpreter.model_label,
            temperature=temp,
            retrieved_ids=retrieved_ids,
            retrieval_scores=[c.similarity for c in chunks],
            response=response,
            invented_numbers=find_invented_numbers(checked_text, prompt),
            unknown_references=(
                find_unknown_references(response.references, retrieved_ids)
                + find_fabricated_citations(checked_text, retrieved_ids)
            ),
        )

    def assess_repeatedly(self, data: AssessmentInput, n_runs: int = 3,
                          temperature: float | None = None) -> list[Assessment]:
        """
        Assess the same segment several times (BACKLOG T5.4).

        An LLM is stochastic, so a single result says nothing about how stable the
        system is. Repeating an identical prompt and measuring the variation is a
        RAG-specific validation requirement with no counterpart in a deep-learning
        pipeline — and one an examiner is almost certain to ask about.
        """
        return [self.assess(data, temperature=temperature) for _ in range(n_runs)]
