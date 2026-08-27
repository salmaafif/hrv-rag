"""
Tests for backend/hrv_api/services/narrative.py's `meta` assembly.

These bypass `write_session_narrative`/`write_timeline_narrative` entirely and
call `_meta`/`_fallback_meta` directly, because test_api.py's fixtures stub
those two public functions wholesale — a real HTTP test never reaches this
code, so the reproducibility fields (§3.3, docs/ARSITEKTUR_KARIRLINK_HRV.md)
would otherwise ship untested.
"""

from dataclasses import dataclass

from hrv_api.services.narrative import _fallback_meta, _meta
from hrv_rag.config.settings import settings
from hrv_rag.features.stress_level import RULE_VERSION


@dataclass
class FakeNarrativeResult:
    """The subset of `NarrativeResult` that `_meta` actually reads."""

    kb_version: str
    model: str
    prompt_name: str
    is_trustworthy: bool


def test_meta_carries_rule_and_prompt_version_on_success():
    result = FakeNarrativeResult(kb_version="kb_v2.0", model="gemini-2.5-flash",
                                 prompt_name="HRV_session_narrative",
                                 is_trustworthy=True)
    meta = _meta(result)

    assert meta["rule_version"] == RULE_VERSION
    assert meta["prompt_version"] == "HRV_session_narrative"


def test_fallback_meta_still_names_the_rule_and_intended_prompt():
    """
    The rule already produced every number before the narrative was even
    attempted, so its version is known even when the model call failed —
    only the narrative-specific fields (kb_version, model) are genuinely
    unknown in this branch.
    """
    meta = _fallback_meta("quota exhausted")

    assert meta["rule_version"] == RULE_VERSION
    assert meta["prompt_version"] == settings.llm.narrative_prompt
    assert meta["kb_version"] == ""
    assert meta["trustworthy"] is False
