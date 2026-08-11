"""
cache.py — Persist assessments so a run can resume across days.

The Gemini free tier allows only 20 requests per day for gemini-2.5-flash. A single
full evaluation of the 293 development segments therefore cannot complete in one
sitting, and without persistence every interrupted run would throw away calls that
had already been spent against that daily allowance.

Each completed assessment is appended to a JSONL file immediately. On the next run
the cache is loaded first and matching segments are skipped, so the work accumulates
day by day until the evaluation is complete.

JSONL rather than a database, for the same reason as everywhere else in this
project: one line per assessment, appended atomically, readable with a text editor,
and diffable. A crash mid-write costs at most the final line.

The cache key deliberately includes every setting that can change the answer — KB
version, prompt version, model, temperature, and whether the rubric chunk was
pinned. Changing any of them makes previous results non-comparable, so they must not
be silently reused. This is the same reproducibility discipline that requires every
output to carry its provenance.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..core.schemas import Assessment, LLMResponse


def cache_key(subject: str, phase: str, segment: int, modality: str,
              kb_version: str, prompt_version: str, model: str,
              temperature: float, pinned: str | None) -> str:
    """
    Identity of one assessment under one exact configuration.

    `modality` belongs in here even though it names the recording rather than the
    settings. WESAD is the whole reason the modality comparison is possible: the
    same subject, the same phase and the same 60 seconds exist twice, once as ECG
    and once as PPG. Without modality in the key those two are the same entry, so
    asking for the PPG assessment would hand back the ECG one that was already
    stored — and the paired comparison in T6.4 would be ECG measured against
    itself, reporting perfect agreement that was never computed.
    """
    pin = pinned or "none"
    return (f"{subject}|{phase}|{segment}|{modality}|{kb_version}"
            f"|{prompt_version}|{model}|{temperature}|{pin}")


class AssessmentCache:
    """Append-only store of completed assessments."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """
        Read whatever is already on disk.

        A malformed final line is skipped rather than fatal: it means a previous run
        was interrupted mid-write, and losing one assessment is far better than
        refusing to start.
        """
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                self._entries[entry["cache_key"]] = entry
            except (json.JSONDecodeError, KeyError):
                continue

    def __len__(self) -> int:
        return len(self._entries)

    def has(self, key: str) -> bool:
        return key in self._entries

    def get(self, key: str) -> Assessment | None:
        """Rebuild a stored Assessment, or None when it is not cached."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        payload = dict(entry)
        payload.pop("cache_key", None)
        payload["response"] = LLMResponse(**payload["response"])
        return Assessment(**payload)

    def put(self, key: str, assessment: Assessment) -> None:
        """
        Store an assessment and flush it to disk immediately.

        Written straight away rather than batched at the end, because the whole
        point is surviving an interruption — and with a 20-per-day allowance, an
        interruption is likely.
        """
        entry = asdict(assessment)
        entry["response"] = assessment.response.model_dump(mode="json")
        entry["cache_key"] = key

        self._entries[key] = entry
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def summary(self) -> str:
        return f"{len(self)} assessments cached at {self.path.name}"
