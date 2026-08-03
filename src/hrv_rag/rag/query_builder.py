"""
query_builder.py — Turns computed features into the retrieval query (T4.1).

This is the hinge between the deterministic half of the system and the language
half. The reactivity numbers are already final; this module only describes them in
words, because the knowledge base is written in words and semantic search matches
meaning rather than digits.

Two deliberate choices:

- Magnitudes are described qualitatively ("sharply below baseline") as well as
  numerically. The KB uses phrases like "decreases sharply", so qualitative wording
  matches far better than a bare percentage.
- When the pattern is atypical, that fact is stated explicitly in the query. Without
  it the chunk that explains atypical patterns would never be retrieved, and the LLM
  would have nothing to reason from precisely when it needs it most.
"""

from __future__ import annotations

from ..core.schemas import AssessmentInput

#: Human-readable names used in the query text and in the prompt.
FEATURE_LABELS: dict[str, str] = {
    "rmssd": "RMSSD",
    "sdnn": "SDNN",
    "pnn50": "pNN50",
    "mean_rr": "mean RR interval",
    "mean_hr": "heart rate",
    "lf_welch": "LF power",
    "hf_welch": "HF power",
    "lf_hf_welch": "LF/HF ratio",
}

#: Features named in the query, in priority order. LF and SDNN are omitted
#: deliberately: they add little at 60 seconds and would dilute the query.
QUERY_FEATURES = ("rmssd", "hf_welch", "lf_hf_welch", "mean_hr", "pnn50")


def _magnitude_word(delta_pct: float) -> str:
    """
    Describe the size of a change in words.

    Thresholds: under 10% is treated as unchanged, since normal segment-to-segment
    variation in a resting baseline is already of that order — calling it a change
    would read signal into noise. Above 30% is called sharp, matching the language
    the knowledge base uses for a clear stress response.
    """
    size = abs(delta_pct)
    if size < 10:
        return "roughly unchanged from"
    direction = "above" if delta_pct > 0 else "below"
    if size < 30:
        return f"moderately {direction}"
    return f"sharply {direction}"


def describe_reactivity(reactivity: dict[str, float]) -> str:
    """Render the reactivity numbers as one readable sentence fragment."""
    parts = []
    for feat in QUERY_FEATURES:
        key = f"delta_pct_{feat}"
        value = reactivity.get(key)
        if value is None or value != value:      # skip missing and NaN
            continue
        label = FEATURE_LABELS.get(feat, feat)
        parts.append(f"{label} {_magnitude_word(value)} baseline "
                     f"({value:+.0f}%)")
    return ", ".join(parts) if parts else "no reactivity available"


def is_atypical(reactivity: dict[str, float]) -> bool:
    """
    Detect the inverted pattern: vagal features rising while heart rate also rises.

    This is the pattern found in WESAD subjects S6 and S10. It matters because the
    textbook reading would call it "no stress", whereas the rising heart rate says
    otherwise. Flagging it lets the query pull in the chunk that explains what to do.
    """
    rmssd = reactivity.get("delta_pct_rmssd")
    hr = reactivity.get("delta_pct_mean_hr")
    if rmssd is None or hr is None or rmssd != rmssd or hr != hr:
        return False
    return rmssd > 10.0 and hr > 5.0


def build_query(data: AssessmentInput) -> str:
    """
    Build the retrieval query for one segment.

    The query names the observed pattern, the modality, and — when relevant — the
    question type and the atypical flag. Each of those steers retrieval towards a
    different part of the knowledge base, which is what allows one query to gather
    physiological, modality, and interpretive knowledge in a single search.
    """
    parts = [describe_reactivity(data.reactivity)]

    # Modality is always mentioned, so the reliability chunks stay reachable
    # (Mandatory Rule #5).
    parts.append(f"measured with {data.modality.value}")

    if data.question_type:
        parts.append(f"during a {data.question_type} question")

    if is_atypical(data.reactivity):
        parts.append("vagal features increased while heart rate also increased, "
                     "an atypical pattern")

    if not data.signal_quality.is_acceptable:
        parts.append("signal quality is questionable")

    return "; ".join(parts)
