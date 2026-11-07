"""
replay_web_recording.py — examine and replay a heart-rate session recorded in the KARIRLINK web app.

    python scripts/replay_web_recording.py rekaman-detak-2026-09-16T03-04-05.json
    python scripts/replay_web_recording.py rekaman.json --send
    python scripts/replay_web_recording.py rekaman.json --save-request tests/fixtures/watch.json

The recording comes from the development-only "Unduh rekaman detak (dev)" button in
the KARIRLINK web app (`apps/web/src/lib/heart-rate/recording.ts`). It holds the raw
material of one session — the anchor, the answer times, both streams exactly as the
browser collected them — plus the submission the browser built from them.

WHY THIS EXISTS. A session with a real device is expensive to repeat, and the one
worth repeating is the one that went wrong. This script turns that session into
something that can be looked at without the device:

  1. A STREAM DIAGNOSIS, computed before any service is involved: how often the device
     reported, where it went silent, which path the service will take, and where each
     question lands on the stream. Those are the questions a strange result raises
     first, and every one of them is answerable from the recording alone.
  2. A REPLAY (--send): the same submission, translated to the service contract the
     way KARIRLINK's backend translates it, sent to a running hrv_api.
  3. A FIXTURE (--save-request): the translated request written to disk, so a session
     that exposed a bug can become a test.

NO SECOND COPY OF THE SCIENCE. The path decision is `choose_source` and the gaps are
`beats_from_bpm` — the functions the service itself runs — so the diagnosis cannot
disagree with the analysis about either.

Sibling of `demo_replay_session.py`, which replays a request the BACKEND archived;
this one starts from what the BROWSER saw, one step earlier.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "backend"))

from hrv_api.services.analysis import BPM, choose_source  # noqa: E402
from hrv_rag.preprocessing.bpm import beats_from_bpm  # noqa: E402

#: Must match `RECORDING_FORMAT` in the web app. A file of another shape is refused
#: rather than half-read.
RECORDING_FORMAT = "karirlink-heart-rate-recording/1"


class RecordingError(ValueError):
    """The file is not a recording this script understands."""


def load_recording(path: Path) -> dict:
    try:
        recording = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecordingError(f"{path} is not JSON: {exc}") from None
    found = recording.get("format") if isinstance(recording, dict) else None
    if found != RECORDING_FORMAT:
        raise RecordingError(
            f"{path} has format {found!r}; expected {RECORDING_FORMAT!r}"
        )
    return recording


@dataclass(frozen=True)
class QuestionPlacement:
    """Where one question sits on the stream the service will read."""

    number: int
    #: Answer start and end of the following gap, in RECORDING seconds.
    start_sec: float
    end_sec: float
    #: False when the question reaches past the end of the stream.
    inside_stream: bool
    #: Unreported stretches overlapping the question (heart-rate path only). A hit
    #: does not make the question unmeasured by itself: only the windows the hole
    #: spoils are dropped, and the service reports the interruption as the reason
    #: only when no window of that question survives.
    gaps_sec: list[tuple[float, float]] = field(default_factory=list)


@dataclass(frozen=True)
class StreamDiagnosis:
    n_reports: int
    #: First report to last, seconds.
    report_span_sec: float
    #: The device's own reporting interval (median spacing), or None.
    cadence_sec: float | None
    bpm_range: tuple[float, float] | None
    n_intervals: int
    #: Sum of the intervals, seconds.
    interval_span_sec: float
    #: What the browser sent; None when there was no submission or no reports.
    rr_coverage: float | None
    #: "beat_intervals" or "bpm" — decided by the service's own function.
    path: str
    #: Unreported stretches, recording seconds from the first report.
    gaps_sec: list[tuple[float, float]]
    questions: list[QuestionPlacement]


def diagnose(recording: dict) -> StreamDiagnosis:
    """Everything about the stream that can be known without calling the service."""
    readings = recording.get("bpmReadings") or []
    rr_ms = recording.get("rrIntervals") or []
    submission = recording.get("submission")

    at_sec = np.asarray([r["atSec"] for r in readings], dtype=float)
    bpm = np.asarray([r["bpm"] for r in readings], dtype=float)
    report_span = float(at_sec[-1] - at_sec[0]) if at_sec.size >= 2 else 0.0
    cadence = float(np.median(np.diff(at_sec))) if at_sec.size >= 2 else None
    gaps = beats_from_bpm(at_sec, bpm).gaps_sec if at_sec.size >= 2 else []

    if submission:
        samples = [{"at_sec": s["atSec"], "bpm": s["bpm"]}
                   for s in submission.get("bpmSamples") or []]
        coverage = submission.get("rrCoverage")
        path = choose_source(submission["rrMs"], None, samples, coverage)
    else:
        samples = [{"at_sec": r["atSec"], "bpm": r["bpm"]} for r in readings]
        coverage = None
        path = choose_source(rr_ms, None, samples if len(samples) >= 2 else None,
                             None)

    interval_span = float(np.sum(rr_ms) / 1000.0)
    placements: list[QuestionPlacement] = []
    if submission:
        on_bpm = path == BPM
        bpm_offset = submission.get("bpmOffsetSec")
        # The same substitution `prepare` makes: on the heart-rate path the report
        # clock places the questions, not the interval clock.
        offset = bpm_offset if on_bpm and bpm_offset is not None \
            else submission["offsetSec"]
        stream_end = report_span if on_bpm else interval_span
        for q in submission["questions"]:
            start = q["answerStartSec"] + offset
            end = q["gapEndSec"] + offset
            placements.append(QuestionPlacement(
                number=q["number"], start_sec=start, end_sec=end,
                inside_stream=end <= stream_end,
                gaps_sec=[g for g in gaps if g[0] < end and g[1] > start]
                if on_bpm else [],
            ))

    return StreamDiagnosis(
        n_reports=int(at_sec.size), report_span_sec=report_span,
        cadence_sec=cadence,
        bpm_range=(float(bpm.min()), float(bpm.max())) if bpm.size else None,
        n_intervals=len(rr_ms), interval_span_sec=interval_span,
        rr_coverage=coverage, path=path, gaps_sec=gaps, questions=placements,
    )


def to_service_request(submission: dict, session_id: str,
                       include_technical: bool = False) -> dict:
    """
    The submission in the service's snake_case contract.

    Mirrors `HrvModuleService.analyzeSession` in KARIRLINK's backend field for field,
    including what it leaves out: the heart-rate fields only when present, and
    `store_consented` false, because a replay is not a consent.
    """
    request: dict = {
        "rr_ms": submission["rrMs"],
        "baseline_minutes": submission["baselineMinutes"],
        "modality": submission["modality"],
        "session_id": session_id,
        "offset_sec": submission["offsetSec"],
        "include_technical": include_technical,
        "store_consented": False,
        "questions": [
            {
                "number": q["number"],
                "text": q["text"],
                "type": q["type"],
                "answer_start_sec": q["answerStartSec"],
                "answer_end_sec": q["answerEndSec"],
                "gap_end_sec": q["gapEndSec"],
                "is_difficult": q["isDifficult"],
            }
            for q in submission["questions"]
        ],
    }
    if submission.get("bpmSamples"):
        request["bpm_samples"] = [{"at_sec": s["atSec"], "bpm": s["bpm"]}
                                  for s in submission["bpmSamples"]]
    if submission.get("rrCoverage") is not None:
        request["rr_coverage"] = submission["rrCoverage"]
    if submission.get("bpmOffsetSec") is not None:
        request["bpm_offset_sec"] = submission["bpmOffsetSec"]
    return request


def send(request: dict, url: str, api_key: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        url.rstrip("/") + "/api/v1/analyze/session",
        data=json.dumps(request).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


# ── Printing: for a person reading a terminal, so in Indonesian ─────────────────

def _span(pair: tuple[float, float]) -> str:
    return f"{pair[0]:.0f}–{pair[1]:.0f} s"


def print_diagnosis(recording: dict, d: StreamDiagnosis) -> None:
    device = recording.get("device") or {}
    print(f"Perangkat     : {device.get('name') or '—'} "
          f"(dipakai di {device.get('wornAt') or '?'}, "
          f"kirim interval: {device.get('sendsRrIntervals')})")
    print(f"Laporan bpm   : {d.n_reports} laporan selama {d.report_span_sec:.0f} s"
          + (f", tiap {d.cadence_sec:.2f} s" if d.cadence_sec is not None else "")
          + (f", rentang {d.bpm_range[0]:.0f}–{d.bpm_range[1]:.0f} bpm"
             if d.bpm_range else ""))
    print(f"Interval RR   : {d.n_intervals} interval, {d.interval_span_sec:.0f} s")
    print(f"Cakupan RR    : {'—' if d.rr_coverage is None else f'{d.rr_coverage:.2f}'}"
          f"  →  jalur {d.path}")
    print(f"Lubang aliran : {', '.join(map(_span, d.gaps_sec)) or 'tidak ada'}")

    if not recording.get("submission"):
        print(f"\nTidak ada kiriman: {recording.get('whyNotSubmitted') or 'sebab tidak tercatat'}")
        return
    print("\nPertanyaan di jam aliran:")
    for q in d.questions:
        notes = []
        if not q.inside_stream:
            notes.append("MELEWATI akhir aliran")
        if q.gaps_sec:
            notes.append("kena lubang " + ", ".join(map(_span, q.gaps_sec)))
        print(f"  Q{q.number}: {_span((q.start_sec, q.end_sec))}"
              + (f"  ← {'; '.join(notes)}" if notes else ""))


def print_response(status: int, body: dict) -> None:
    print(f"\nHTTP {status}")
    if status != 200:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return
    summary = body.get("summary") or {}
    meta = body.get("meta") or {}
    print(f"source {body.get('source')} | tier {body.get('tier')} | "
          f"terukur {(body.get('coverage') or {}).get('measured')}/"
          f"{(body.get('coverage') or {}).get('total')}")
    for q in body.get("questions") or []:
        print(f"  Q{q.get('number')}: {q.get('level')}"
              + (f" — {q['recovery_note']}" if q.get("recovery_note") else ""))
    for q in body.get("unmeasured") or []:
        print(f"  Q{q.get('number')}: tidak terukur — {q.get('reason')}")
    print(f"paling memicu Q{summary.get('most_triggering_question')} "
          f"(dasar {summary.get('reactivity_basis')})")
    print(f"prompt {meta.get('prompt_version')} | layak dipercaya "
          f"{meta.get('trustworthy')} | galat narasi {meta.get('narrative_error')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("recording", type=Path)
    parser.add_argument("--send", action="store_true",
                        help="kirim ke hrv_api yang sedang berjalan")
    parser.add_argument("--url", default=os.environ.get("HRV_API_URL",
                                                        "http://127.0.0.1:8000"))
    parser.add_argument("--technical", action="store_true",
                        help="minta angka teknis (hanya untuk riset)")
    parser.add_argument("--save-request", type=Path,
                        help="tulis permintaan snake_case ke berkas ini")
    args = parser.parse_args(argv)

    # A Windows console defaults to cp1252, which has no "→" or "–"; without this
    # the diagnosis crashes halfway through printing (found replaying a real file).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    try:
        recording = load_recording(args.recording)
    except (OSError, RecordingError) as exc:
        print(exc, file=sys.stderr)
        return 2

    print_diagnosis(recording, diagnose(recording))

    submission = recording.get("submission")
    if not (args.send or args.save_request):
        return 0
    if not submission:
        print("\nTidak ada kiriman untuk diputar ulang.", file=sys.stderr)
        return 1

    request = to_service_request(submission, f"replay-{args.recording.stem}",
                                 include_technical=args.technical)
    if args.save_request:
        args.save_request.write_text(json.dumps(request, indent=2), encoding="utf-8")
        print(f"\nPermintaan ditulis ke {args.save_request}")
    if args.send:
        api_key = os.environ.get("HRV_API_KEY")
        if not api_key:
            print("\nHRV_API_KEY belum diisi.", file=sys.stderr)
            return 2
        print_response(*send(request, args.url, api_key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
