"""
test_recovery_wording.py — every recovery reason the backend can send has Indonesian words.

The reasons in `RecoveryResult` are English code strings: they also travel into
the model's prompt, where English is the rule. The web demo shows them to a
person, so `frontend/src/lib/format.ts` translates each one — and an English
sentence reached the screen before that existed.

This test reads the backend source for every reason it can produce and fails
when one has no entry in the frontend's table. It reads files rather than
calling code because a reason can be written inline anywhere a
`RecoveryResult(None, ...)` is built.
"""

from __future__ import annotations

import re
from pathlib import Path

from hrv_rag.features.question import RECOVERY_NOT_MEASURED

REPO = Path(__file__).resolve().parents[1]
SOURCES = [REPO / "src/hrv_rag/features/question.py",
           REPO / "src/hrv_rag/features/dynamics.py"]
FORMAT_TS = REPO / "frontend/src/lib/format.ts"

#: `RecoveryResult(None, "text")` or `RecoveryResult(None, f"text {x}")`.
INLINE_REASON = re.compile(r'RecoveryResult\(\s*None,\s*f?"([^"]+)"')
#: `['prefix',` rows of RECOVERY_REASONS.
FRONTEND_KEY = re.compile(r"\[\s*'([^']+)',")


def backend_reasons() -> set[str]:
    reasons = {RECOVERY_NOT_MEASURED}
    for path in SOURCES:
        for text in INLINE_REASON.findall(path.read_text(encoding="utf-8")):
            # An f-string's figures differ every time; its opening does not.
            reasons.add(text.split("{")[0].rstrip(" ("))
    return reasons


def frontend_prefixes() -> list[str]:
    source = FORMAT_TS.read_text(encoding="utf-8")
    table = source[source.index("RECOVERY_REASONS"):]
    table = table[:table.index("]\n\n")]
    return FRONTEND_KEY.findall(table)


def test_the_scan_actually_finds_reasons():
    # Without this, a regex that matched nothing would pass the test below.
    reasons = backend_reasons()
    assert len(reasons) >= 6
    assert "no quiet gap followed this question" in reasons
    assert any(r.startswith("reaction too small") for r in reasons)
    assert len(frontend_prefixes()) >= 6


def test_every_backend_recovery_reason_is_translated_on_the_web():
    prefixes = frontend_prefixes()
    untranslated = sorted(r for r in backend_reasons()
                          if not any(r.startswith(p) for p in prefixes))
    assert untranslated == []
