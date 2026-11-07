"""
Tests for scripts/replay_web_recording.py — the diagnosis of a recorded web session.

The recordings here are built by hand in the web app's shape, with answers worked
out on paper: a watch that went silent for ten seconds, a question that runs past
the end of the stream, and a chest strap whose questions must be placed on the
interval clock, not the report clock.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

from hrv_api.schemas import SessionRequest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "replay_web_recording.py"
_spec = importlib.util.spec_from_file_location("replay_web_recording", _PATH)
replay = importlib.util.module_from_spec(_spec)
# Registered before running it: dataclasses look their module up by name.
sys.modules[_spec.name] = replay
_spec.loader.exec_module(replay)


def _question(number: int, start: float, end: float, gap_end: float) -> dict:
    return {"number": number, "text": f"Pertanyaan {number}", "type": "technical",
            "answerStartSec": start, "answerEndSec": end, "gapEndSec": gap_end,
            "isDifficult": False}


def watch_recording() -> dict:
    """
    A watch reporting once a second from clock second 500, silent for 10 s.

    Reports at 500..649 and 660..799: 290 reports, span 299 s, hole 150-160 s from
    the first report (the first second after 649 is still report 649's own).
    bpmOffsetSec 100 moves every question 100 s later on the stream:
      Q1 session 20-60   -> stream 120-160: overlaps the hole
      Q2 session 70-110  -> stream 170-210: clean
      Q3 session 150-205 -> stream 250-305: past the end at 299
    offsetSec is deliberately different (7) so using the wrong clock is visible.
    """
    times = [*range(500, 650), *range(660, 800)]
    readings = [{"atSec": float(t), "bpm": 70.0 + (t % 5)} for t in times]
    return {
        "format": replay.RECORDING_FORMAT,
        "capturedAt": "2026-09-16T03:04:05.000Z",
        "device": {"name": "Amazfit Band 7", "wornAt": "wrist",
                   "sendsRrIntervals": False},
        "anchor": {"startedAtMs": 0, "offsetSec": 0, "bpmOffsetSec": 100},
        "answered": [],
        "rrIntervals": [],
        "bpmReadings": readings,
        "submission": {
            "rrMs": [],
            "baselineMinutes": 2,
            "modality": "PPG",
            "offsetSec": 7,
            "questions": [_question(1, 20, 40, 60), _question(2, 70, 100, 110),
                          _question(3, 150, 190, 205)],
            "bpmSamples": [{"atSec": r["atSec"] - 500, "bpm": r["bpm"]}
                           for r in readings],
            "rrCoverage": 0,
            "bpmOffsetSec": 100,
        },
        "whyNotSubmitted": None,
    }


def strap_recording() -> dict:
    """A chest strap: 400 intervals of 900 ms (360 s) and reports covering it all."""
    recording = watch_recording()
    rr = [900.0] * 400
    readings = [{"atSec": float(t), "bpm": 66.0} for t in range(0, 361)]
    recording["rrIntervals"] = rr
    recording["bpmReadings"] = readings
    recording["submission"].update({
        "rrMs": rr, "modality": "ECG", "offsetSec": 30, "rrCoverage": 1.0,
        "bpmSamples": [dict(r) for r in readings], "bpmOffsetSec": 90,
        "questions": [_question(1, 120, 200, 240)],
    })
    return recording


def test_rejects_a_file_of_another_format(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"format": "something-else/1"}), encoding="utf-8")
    with pytest.raises(replay.RecordingError, match="something-else"):
        replay.load_recording(path)


def test_watch_stream_is_described_from_its_reports():
    d = replay.diagnose(watch_recording())

    assert d.n_reports == 290
    assert d.report_span_sec == 299
    assert d.cadence_sec == 1
    assert d.bpm_range == (70, 74)
    assert d.path == "bpm"
    assert d.gaps_sec == [(150.0, 160.0)]


def test_watch_questions_are_placed_on_the_report_clock():
    placements = {q.number: q for q in replay.diagnose(watch_recording()).questions}

    assert (placements[1].start_sec, placements[1].end_sec) == (120, 160)
    assert placements[1].gaps_sec == [(150.0, 160.0)]
    assert placements[1].inside_stream

    assert (placements[2].start_sec, placements[2].end_sec) == (170, 210)
    assert placements[2].gaps_sec == []

    assert (placements[3].start_sec, placements[3].end_sec) == (250, 305)
    assert not placements[3].inside_stream


def test_strap_questions_are_placed_on_the_interval_clock():
    d = replay.diagnose(strap_recording())

    assert d.path == "beat_intervals"
    assert d.interval_span_sec == 360
    (q,) = d.questions
    # offsetSec 30, not bpmOffsetSec 90.
    assert (q.start_sec, q.end_sec) == (150, 270)
    assert q.inside_stream
    assert q.gaps_sec == []


def test_low_coverage_strap_falls_to_the_heart_rate_path():
    recording = strap_recording()
    recording["submission"]["rrCoverage"] = 0.5
    d = replay.diagnose(recording)

    assert d.path == "bpm"
    (q,) = d.questions
    assert (q.start_sec, q.end_sec) == (210, 330)


def test_recording_without_submission_is_still_diagnosed():
    recording = watch_recording()
    recording["submission"] = None
    recording["whyNotSubmitted"] = "tidak ada jawaban yang waktu pengerjaannya sempat terekam"
    d = replay.diagnose(recording)

    assert d.n_reports == 290
    assert d.path == "bpm"
    assert d.rr_coverage is None
    assert d.questions == []


def test_request_matches_the_service_contract():
    request = replay.to_service_request(watch_recording()["submission"], "replay-x")
    parsed = SessionRequest.model_validate(request)

    assert parsed.bpm_offset_sec == 100
    assert parsed.offset_sec == 7
    assert parsed.rr_coverage == 0
    assert len(parsed.bpm_samples) == 290
    assert parsed.questions[2].gap_end_sec == 205
    assert parsed.store_consented is False
    assert parsed.include_technical is False


def test_request_omits_heart_rate_fields_the_browser_did_not_send():
    submission = strap_recording()["submission"]
    for key in ("bpmSamples", "rrCoverage", "bpmOffsetSec"):
        submission.pop(key)
    request = replay.to_service_request(submission, "replay-x")

    assert not {"bpm_samples", "rr_coverage", "bpm_offset_sec"} & request.keys()
    SessionRequest.model_validate(request)


def test_cli_diagnoses_and_saves_a_request(tmp_path, capsys):
    path = tmp_path / "rekaman.json"
    path.write_text(json.dumps(watch_recording()), encoding="utf-8")
    out = tmp_path / "request.json"

    assert replay.main([str(path), "--save-request", str(out)]) == 0

    printed = capsys.readouterr().out
    assert "jalur bpm" in printed
    assert "kena lubang 150–160 s" in printed
    assert "MELEWATI akhir aliran" in printed
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["session_id"] == "replay-rekaman"
    SessionRequest.model_validate(saved)


def test_cli_prints_on_a_windows_console(tmp_path, monkeypatch):
    """A cp1252 console cannot encode the arrows and dashes the diagnosis prints."""
    path = tmp_path / "rekaman.json"
    path.write_text(json.dumps(watch_recording()), encoding="utf-8")
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)

    assert replay.main([str(path)]) == 0

    console.flush()
    assert "jalur bpm" in raw.getvalue().decode("utf-8")


def test_cli_refuses_to_replay_without_a_submission(tmp_path, capsys):
    recording = watch_recording()
    recording["submission"] = None
    path = tmp_path / "rekaman.json"
    path.write_text(json.dumps(recording), encoding="utf-8")

    assert replay.main([str(path), "--send"]) == 1
    assert "Tidak ada kiriman" in capsys.readouterr().err
