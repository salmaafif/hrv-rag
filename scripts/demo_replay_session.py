"""
demo_replay_session.py — replay an archived pilot session against the live API.

The demo tool for supervision meetings: it takes a REAL recording (a consented
pilot session archived by the backend) and sends its request to a running
hrv_api instance, then prints what an integrator would see. One command, no
hardware, real human data.

    python scripts/demo_replay_session.py [path-ke-arsip.json]

Defaults to the oldest archive in outputs/session_archive/. Requires the API
running locally (see docs) and the same X-API-Key it was started with.

WHAT THIS DEMONSTRATES, in the order a supervisor will ask about it:
  1. The service answers over plain HTTP with an API key — server-to-server,
     exactly how KARIRLINK's backend calls it.
  2. Labels come from the deterministic rule (identical on every replay);
     only the narrative involves the LLM.
  3. Technical numbers are withheld by default (no RMSSD in the response) —
     the display rules are enforced by the API's own default.
  4. If Gemini is down or out of quota, labels still come back and
     meta.trustworthy flags the narrative — graceful degradation, live.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

API_URL = os.environ.get("HRV_API_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("HRV_API_KEY", "kunci-lokal")
ARCHIVE_DIR = Path("outputs/session_archive")


def pick_archive() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    candidates = sorted(ARCHIVE_DIR.glob("*-session.json"))
    if not candidates:
        raise SystemExit(f"tidak ada arsip di {ARCHIVE_DIR}/")
    return candidates[0]


def main() -> None:
    # Konsol Windows (cp1252) tersedak karakter non-ASCII dari narasi — jebakan
    # lama yang sudah pernah menggigit proyek ini.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    path = pick_archive()
    with open(path, encoding="utf-8") as f:
        archived = json.load(f)
    request = archived["request"]

    print(f"Arsip     : {path.name}")
    print(f"Rekaman   : {len(request['rr_ms'])} interval RR "
          f"({request['modality']}), {len(request['questions'])} pertanyaan, "
          f"baseline {request['baseline_minutes']} menit")
    print(f"Mengirim  : POST {API_URL}/api/v1/analyze/session")
    print()

    req = urllib.request.Request(
        f"{API_URL}/api/v1/analyze/session",
        data=json.dumps(request).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.load(resp)

    print(f"Label sesi: tier={body['tier']}, "
          f"baseline stable={body['baseline']['is_stable']}, "
          f"evidence={body['baseline']['evidence']}")
    for q in body["questions"]:
        recovery = q.get("recovery_pct")
        print(f"  Q{q['number']}: {q['level']:<8} "
              f"recovery={'belum terukur' if recovery is None else f'{recovery}%'}")
    summary = body.get("summary") or {}
    print(f"Paling menegangkan: pertanyaan "
          f"{summary.get('most_triggering_question')}")
    meta = body["meta"]
    print(f"Provenance: kb={meta.get('kb_version')} "
          f"prompt={meta.get('prompt_version')} rule={meta.get('rule_version')} "
          f"model={meta.get('model')} trustworthy={meta.get('trustworthy')}")
    narrative = body.get("narrative") or {}
    ringkasan = narrative.get("ringkasan_sesi") or "(kosong — degradasi anggun)"
    print(f"\nNarasi    : {ringkasan[:300]}")


if __name__ == "__main__":
    main()
