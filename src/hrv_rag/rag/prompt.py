"""
prompt.py — Assembles the prompt from the versioned template (T4.3).

The template lives in `prompts/vN.md` rather than in this file. That separation is
deliberate: in a RAG design the prompt is part of the system, comparable to model
architecture in a deep-learning design. Keeping it in a versioned file means a
change to the wording is visible, dateable, and reversible — and results can always
be traced back to the exact prompt that produced them.
"""

from __future__ import annotations

from pathlib import Path

from ..config.settings import PROMPTS_DIR, settings
from ..core.schemas import AssessmentInput
from .query_builder import FEATURE_LABELS
from .retrieval import RetrievedChunk

#: Features shown in the MEASUREMENTS block, in the order they appear.
SHOWN_FEATURES = ("rmssd", "sdnn", "pnn50", "mean_hr", "hf_welch", "lf_hf_welch")


def load_template(version: str | None = None,
                  prompts_dir: Path | None = None) -> str:
    """
    Load a prompt template by version.

    Everything before the `## SYSTEM INSTRUCTION` heading is editorial commentary
    about the file and is stripped, so it never reaches the model and never costs
    tokens.
    """
    version = version or settings.llm.prompt_version
    path = (prompts_dir or PROMPTS_DIR) / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template {path} not found.")

    raw = path.read_text(encoding="utf-8")
    marker = "## SYSTEM INSTRUCTION"
    return raw[raw.index(marker):] if marker in raw else raw


def format_context(chunks: list[RetrievedChunk]) -> str:
    """
    Render retrieved chunks as the CONTEXT block.

    Each chunk keeps its ID visible, because the model is required to cite the IDs
    it relied on. Without them in the context, the `references` field could only be
    guessed — and a guessed citation is exactly what the faithfulness check
    (BACKLOG T5.6) is designed to catch.
    """
    if not chunks:
        return ("(no knowledge chunk passed the relevance threshold — "
                "you do not have enough context to reach a conclusion)")

    blocks = []
    for hit in chunks:
        blocks.append(
            f"### {hit.chunk.id} — {hit.chunk.title}\n"
            f"(relevance {hit.similarity:.3f}; sources: {hit.chunk.references})\n\n"
            f"{hit.chunk.text}"
        )
    return "\n\n".join(blocks)


def _format_features(features: dict[str, float]) -> str:
    lines = []
    for feat in SHOWN_FEATURES:
        value = features.get(feat)
        if value is None or value != value:
            continue
        label = FEATURE_LABELS.get(feat, feat)
        unit = " bpm" if feat == "mean_hr" else (" ms" if feat in
                                                 ("rmssd", "sdnn", "mean_rr") else "")
        lines.append(f"- {label}: {value:.2f}{unit}")
    return "\n".join(lines) if lines else "- (none available)"


def _format_reactivity(reactivity: dict[str, float]) -> str:
    lines = []
    for feat in SHOWN_FEATURES:
        value = reactivity.get(f"delta_pct_{feat}")
        if value is None or value != value:
            continue
        label = FEATURE_LABELS.get(feat, feat)
        lines.append(f"- {label}: {value:+.1f}% vs baseline")
    return "\n".join(lines) if lines else "- (no baseline comparison available)"


def _format_recovery(data: AssessmentInput) -> str:
    """
    Render recovery, keeping "not computable" distinct from "did not recover".

    Reporting an unmeasurable recovery as 0% would tell the model the person failed
    to settle, when in fact nothing was measured. The distinction is preserved all
    the way into the prompt.
    """
    if data.recovery_pct is None:
        note = data.recovery_note or "no quiet period followed this segment"
        return f"- Not computable ({note}). Do not treat this as a failure to recover."
    return f"- {data.recovery_pct:.1f}% of the deviation returned towards baseline"


def build_prompt(data: AssessmentInput, chunks: list[RetrievedChunk],
                 version: str | None = None) -> str:
    """Fill the template with retrieved context and the computed measurements."""
    template = load_template(version)

    question_line = ""
    if data.question_no is not None:
        qtype = f", type: {data.question_type}" if data.question_type else ""
        question_line = f"- Question number: {data.question_no}{qtype}\n"

    baseline_note = ""
    if data.baseline_note:
        baseline_note = f"\n### Baseline warning\n- {data.baseline_note}\n"

    confounders = ("\n".join(f"- {c}" for c in data.confounders)
                   if data.confounders else "- (none reported)")

    return template.format(
        context=format_context(chunks),
        session_id=data.session_id,
        segment_index=data.segment_index,
        phase=data.phase.value,
        modality=data.modality.value,
        device=data.device,
        signal_quality=data.signal_quality.describe(),
        question_line=question_line,
        features=_format_features(data.features),
        reactivity=_format_reactivity(data.reactivity),
        recovery=_format_recovery(data),
        confounders=confounders,
        baseline_note=baseline_note,
    )
