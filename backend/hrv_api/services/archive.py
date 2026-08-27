"""
archive.py — keeps consented recordings, so real sessions stop being unrepeatable.

WHY THIS EXISTS. Decision K17 records the project's largest missing asset: not
one real interview session with heart data has ever been kept. Every number in
the thesis comes from laboratory datasets, and every pilot session so far was
analysed once and evaporated. This service closes that: a consented session is
written to disk INTACT — the exact request and the exact response — so it can be
re-analysed later under a newer rule or knowledge base, cited in the report, or
labelled afterwards for training.

WHAT AN ARCHIVED SESSION IS NOT, and the report must say this plainly: it is not
training data yet. A recording without a ground-truth label cannot train or
grade anything; it supports direction tests (answering ran tenser than rest) and
re-analysis. It becomes training data only when a label is attached — the
cheapest being the person's own answer to "which question felt most tense?",
which is already the plan's validity metric.

TWO LOCKS, BOTH REQUIRED, storage happens only when they agree:

  1. The CALLER states consent per request (`store_consented: true`). Consent
     lives with the person, and only the caller met the person. The demo
     frontend sends it from an explicit checkbox; KARIRLINK's platform would
     send it from its own SessionConsent flow.
  2. The OPERATOR configures a destination (`HRV_ARCHIVE_DIR`). An unset server
     stores nothing regardless of what callers claim — the module is handed to
     another team eventually, and silent collection must not be a default
     anyone can switch on remotely.

Failing to archive never fails the analysis. The person answered questions and
is owed their result; losing the archive copy is an operational regret, not a
reason to throw their session away.

WHAT IS DELIBERATELY NOT STORED: no name, no email, no account id, no IP.
`session_id` is the opaque id the caller chose — the module has nothing else,
by design (architecture boundary A1), so the archive cannot leak what it never
had. Re-identification, if ever needed, is the caller's mapping to keep under
its own consent regime.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

#: Directory that turns archiving on. Unset (the default) = store nothing.
ARCHIVE_ENV = "HRV_ARCHIVE_DIR"

#: Schema version of the archive file itself, so a later reader knows what it
#: is holding when this format inevitably grows a field.
ARCHIVE_FORMAT = "hrv-session-archive-v1"


def _safe_stem(session_id: str) -> str:
    """
    The session id as a filename fragment, defanged.

    The id arrives from the caller and lands in a filesystem path; stripping it
    to a safe alphabet closes path tricks (`../`, separators) without rejecting
    any honest id.
    """
    stem = re.sub(r"[^A-Za-z0-9_-]", "-", session_id)[:60]
    return stem or "session"


def archive_session(request_body: dict, response_body: dict) -> Path | None:
    """
    Write one consented session to the archive. Returns the path, or None.

    The REQUEST is stored verbatim — including the full `rr_ms` series — because
    the recording is the part that can never be produced again. The response
    can always be recomputed from it; it is stored anyway so the archive also
    documents what the person was actually shown, under which rule, prompt and
    KB versions (`meta` carries all three).
    """
    if not request_body.get("store_consented"):
        return None

    configured = os.getenv(ARCHIVE_ENV, "").strip()
    if not configured:
        # Consent given but no destination: say so once in the log, loudly
        # enough to notice during a pilot, quietly enough not to fail anyone.
        log.warning(
            "session consented to storage but %s is unset — recording NOT kept",
            ARCHIVE_ENV,
        )
        return None

    directory = Path(configured)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        stem = _safe_stem(str(request_body.get("session_id", "session")))
        path = directory / f"{stamp}-{stem}.json"

        record = {
            "format": ARCHIVE_FORMAT,
            "stored_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "request": request_body,
            "response": response_body,
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path
    except OSError as exc:
        log.warning("failed to archive session: %s", exc)
        return None
