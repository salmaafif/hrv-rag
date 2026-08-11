"""
session_pipeline.py — One recorded session in, one report out.

This is the product. Everything before it produces parts; this assembles them.

    signal + timeline
        -> preprocess and segment          (existing)
        -> personal baseline               (existing)
        -> group segments per question     (features/question.py)
        -> assess each question            (one LLM call each)
        -> aggregate into a session report (here)

Two things happen only at this level, and both are computed by code rather than by
the LLM: which question provoked the strongest reaction, and where the session lands
in the resilience quadrant. Neither would change if the language model were swapped.

Calls are made per QUESTION, not per segment. A 15-minute session has around 13
assessable segments but only 4-5 questions, so the user waits about a minute instead
of three, and the granularity still matches what the dashboard shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config.settings import LLMConfig, settings
from ..core.schemas import Assessment, AssessmentInput, SignalQuality
from ..core.session import SessionTimeline
from ..core.types import Modality, Phase
from ..features.baseline import BaselineProfile
from ..features.dynamics import ResilienceQuadrant, resilience_quadrant
from ..features.question import (QuestionMeasurement, arousal_index,
                                 cognitive_load_hint, measure_question)
from .pipeline import AssessmentPipeline


@dataclass
class QuestionResult:
    """One question: what was measured, and what the LLM made of it."""

    measurement: QuestionMeasurement
    assessment: Assessment
    arousal_pct: float
    reaction_magnitude: float
    attribution_hint: str


@dataclass
class SessionReport:
    """The finished report for one session, in both layers."""

    session_id: str
    modality: str
    kb_version: str
    prompt_version: str
    model: str

    results: list[QuestionResult] = field(default_factory=list)
    baseline_note: str = ""

    # --- computed by code, not by the LLM ---
    most_triggering: int | None = None
    resilience: ResilienceQuadrant | None = None
    median_reactivity_pct: float = float("nan")
    median_recovery_pct: float | None = None

    def user_view(self) -> dict:
        """
        The user layer — Indonesian, plain language, no feature names (K4).

        Phrased as behaviour rather than as traits: "took longer to settle" instead
        of "poor emotional regulation". The first is something a person can train;
        the second is a verdict about who they are, which this system has no business
        issuing.
        """
        quadrant_id = {
            ResilienceQuadrant.HIGH: "tenang dan cepat pulih",
            ResilienceQuadrant.HELD_IN: "tampak tenang, tetapi ketegangan bertahan",
            ResilienceQuadrant.FLEXIBLE: "bereaksi kuat, tetapi cepat kembali tenang",
            ResilienceQuadrant.LOW: "bereaksi kuat dan butuh waktu untuk kembali tenang",
        }
        return {
            "pertanyaan": [
                {
                    "nomor": r.measurement.question.number,
                    "pertanyaan": r.measurement.question.text,
                    **r.assessment.user_view(),
                }
                for r in self.results
            ],
            "paling_memicu": self.most_triggering,
            "pola_keseluruhan": (quadrant_id.get(self.resilience)
                                 if self.resilience else
                                 "belum dapat disimpulkan"),
        }

    def technical_view(self) -> pd.DataFrame:
        """The technical layer — every number, for inspection and archiving."""
        rows = []
        for r in self.results:
            row = r.assessment.technical_view()
            row.update({
                "question_no": r.measurement.question.number,
                "question_type": r.measurement.question.qtype.value,
                "n_segments": r.measurement.n_segments,
                "arousal_pct": r.arousal_pct,
                "reaction_magnitude": r.reaction_magnitude,
                "recovery_pct": r.measurement.recovery.percent,
                "recovery_note": r.measurement.recovery.reason,
                **r.measurement.reactivity,
            })
            rows.append(row)
        return pd.DataFrame(rows)


class SessionPipeline:
    """Runs a whole session end to end."""

    def __init__(self, assessment_pipeline: AssessmentPipeline | None = None,
                 cfg: LLMConfig | None = None) -> None:
        self.cfg = cfg or settings.llm
        self.pipeline = assessment_pipeline or AssessmentPipeline(cfg=self.cfg)

    def run(self, timeline: SessionTimeline, segments: pd.DataFrame,
            baseline: BaselineProfile, modality: Modality,
            device: str) -> SessionReport:
        """
        Assess every question in the session and assemble the report.

        `segments` is the feature table for this session; `baseline` was built from
        its calibration phase. Both are computed before this runs, so no HRV number
        is produced here — only selected, arranged, and interpreted.
        """
        report = SessionReport(
            session_id=timeline.session_id,
            modality=modality.value,
            kb_version=self.pipeline.index.kb_version,
            prompt_version=self.cfg.prompt_version,
            model=self.pipeline.interpreter.model_label,
        )

        # An unsteady baseline weakens everything derived from it, so it is flagged
        # once here and passed into every prompt rather than silently ignored.
        spread = baseline.relative_spread(settings.dynamics.primary_feature)
        if spread == spread and spread > 0.40:
            report.baseline_note = (
                f"the resting baseline was unsteady (relative IQR {spread:.0%}), "
                f"so reactivity figures are less certain than usual"
            )

        for question in timeline.questions:
            measurement = measure_question(question, segments, baseline)
            if not measurement.has_data:
                continue

            arousal = arousal_index(measurement.reactivity)
            magnitude, hint = cognitive_load_hint(question.qtype,
                                                  measurement.reactivity)

            data = AssessmentInput(
                session_id=timeline.session_id,
                modality=modality,
                device=device,
                phase=Phase.QUESTION,
                segment_index=question.number,
                features=measurement.features,
                reactivity=measurement.reactivity,
                signal_quality=SignalQuality(
                    outlier_pct=measurement.signal_quality_pct,
                    is_acceptable=measurement.signal_quality_pct <= 10.0,
                    notes=measurement.notes,
                ),
                question_no=question.number,
                question_type=f"{question.qtype.value} ({hint})",
                recovery_pct=measurement.recovery.percent,
                recovery_note=measurement.recovery.reason,
                confounders=timeline.confounders,
                baseline_note=report.baseline_note,
            )

            report.results.append(QuestionResult(
                measurement=measurement,
                assessment=self.pipeline.assess(data),
                arousal_pct=arousal,
                reaction_magnitude=magnitude,
                attribution_hint=hint,
            ))

        self._summarise(report)
        return report

    @staticmethod
    def _summarise(report: SessionReport) -> None:
        """
        Fill in the session-level figures. All deterministic.

        The ranking uses RMSSD reactivity, which falls under pressure, so the most
        provoking question is the most negative one. Because this is computed rather
        than asked for, the ordering does not change if the language model does.
        """
        if not report.results:
            return

        deltas = {
            r.measurement.question.number: r.measurement.reactivity.get(
                "delta_pct_rmssd", float("nan"))
            for r in report.results
        }
        valid = {k: v for k, v in deltas.items() if v == v}
        if valid:
            report.most_triggering = min(valid, key=valid.get)
            report.median_reactivity_pct = float(np.median(list(valid.values())))

        recoveries = [r.measurement.recovery.percent for r in report.results
                      if r.measurement.recovery.is_computable]
        if recoveries:
            report.median_recovery_pct = float(np.median(recoveries))

        if report.median_reactivity_pct == report.median_reactivity_pct:
            report.resilience = resilience_quadrant(
                report.median_reactivity_pct, report.median_recovery_pct
            )
