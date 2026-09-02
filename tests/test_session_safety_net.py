"""
test_session_safety_net.py — the whole-session fallback and honest coverage.

Until 1 September 2026 a session in which no single question held a usable
window produced no result at all: the module answered 422, KARIRLINK's backend
translated that into "the HRV module is unavailable", and the person was told
the feature was broken when they had simply answered quickly. Measured on the
live pipeline, every answer under 31 seconds did that — and the first person to
run the integrated app finished every question inside a minute.

Two behaviours were added, and both are pinned here:

  1. `session_level()` — one reading for the WHOLE answering phase against the
     same personal baseline. It cannot say which question was hardest, and it
     must never be presented as if it could, but "your body ran tenser than
     your calm baseline" is a true statement worth more than an empty screen.
  2. Questions that could not be measured are REPORTED (`unmeasured`,
     `coverage`), not silently dropped — the same principle the acquisition
     document already states for segments: flagged, never removed unannounced.

The 422 still exists, and one test here makes sure of it: when even the
answering phase as a whole yields no window, claiming a measurement would be
the dishonest branch.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from hrv_api.app import app
from hrv_api.responses import TECHNICAL_FIELDS, strip_technical
from hrv_api.routes import session as session_route
from hrv_api.services.analysis import (AnalysisError, build_session, prepare)
from hrv_api.services.narrative import write_session_narrative
from hrv_rag.core.types import Modality

LEVELS = {"low", "moderate", "high"}


def beats(seconds: float, ms: float = 857.0, seed: int = 0) -> list[float]:
    """A steady recording of the requested length, in milliseconds per beat."""
    rng = np.random.default_rng(seed)
    n = int(seconds * 1000 / ms)
    return [float(v) for v in ms + rng.normal(0, 25, n)]


def question(number: int, start: float, end: float, gap_end: float) -> dict:
    return {"number": number, "text": f"Q{number}", "type": "introduction",
            "answer_start_sec": start, "answer_end_sec": end,
            "gap_end_sec": gap_end, "is_difficult": False}


@pytest.fixture(scope="module")
def prepared():
    """Two resting minutes, then five task minutes, one steady recording."""
    return prepare(beats(7 * 60), None, baseline_minutes=2.0,
                   modality=Modality.ECG, session_id="SAFETY-NET")


# ------------------------------------------------------- the safety net
def test_all_quick_answers_fall_back_to_the_session_level(prepared):
    """
    Five questions, each cycle 20 seconds — answer plus gap together under half
    a segment, so not one is individually measurable. The session used to die
    here with a 422; now every question is reported unmeasured, coverage says
    0 of 5 plainly, and the answering phase still gets its one honest reading.
    """
    questions = [question(i, 120 + 20 * (i - 1), 130 + 20 * (i - 1),
                          140 + 20 * (i - 1)) for i in range(1, 6)]

    body, measurements = build_session(prepared, questions)

    assert body["questions"] == []
    assert measurements == []
    assert body["coverage"] == {"measured": 0, "total": 5}
    assert [entry["number"] for entry in body["unmeasured"]] == [1, 2, 3, 4, 5]
    for entry in body["unmeasured"]:
        assert entry["reason"]          # never an empty why

    whole = body["session_level"]
    assert whole is not None
    assert whole["level"] in LEVELS
    assert whole["n_segments"] >= 1
    # The developer numbers exist BEFORE stripping — build_session itself does
    # not withhold; that is the response layer's job, tested further down.
    for field in TECHNICAL_FIELDS:
        assert field in whole


def test_a_mixed_session_reports_measured_and_unmeasured_side_by_side(prepared):
    """
    One quick answer and one generous answer. The generous one is scored per
    question exactly as before; the quick one lands in `unmeasured` with its
    identity intact — the screen can then show five questions where five were
    asked, instead of four and silence.
    """
    questions = [
        question(1, 120, 130, 140),     # 20-second cycle: not measurable
        question(2, 140, 230, 290),     # 90-second answer: measurable
    ]

    body, measurements = build_session(prepared, questions)

    assert body["coverage"] == {"measured": 1, "total": 2}
    assert [q["number"] for q in body["questions"]] == [2]
    assert len(measurements) == 1
    assert [entry["number"] for entry in body["unmeasured"]] == [1]
    assert body["unmeasured"][0]["text"] == "Q1"
    assert body["session_level"] is not None


def test_a_session_with_nothing_measurable_still_refuses(prepared):
    """
    The safety net is a fallback, not a promise. Questions placed entirely off
    the end of the recording leave nothing to read — per question OR session —
    and the honest answer is still a refusal, now worded at the recording
    rather than blaming the (since fixed) clock alignment.
    """
    questions = [question(1, 9000.0, 9010.0, 9020.0)]

    with pytest.raises(AnalysisError, match="answering phase"):
        build_session(prepared, questions)


# ------------------------------------------------- the technical curtain
def test_session_level_is_stripped_like_a_question():
    """
    `session_level` is a dict, not a list of entries, so the pre-existing strip
    loop walked past it untouched — a brand-new field quietly leaking the exact
    numbers the technical curtain exists to withhold. The strip must leave the
    level, the honesty flags, and nothing numeric.
    """
    payload = {
        "questions": [{"number": 1, "level": "high", "score": 3,
                       "delta_rmssd_pct": -31.0, "delta_hr_pct": 17.0,
                       "evidence": ["x"], "features_disagree": False}],
        "session_level": {"level": "moderate", "score": 2,
                          "delta_rmssd_pct": -22.0, "delta_hr_pct": 6.0,
                          "evidence": ["y"], "n_segments": 7,
                          "features_disagree": True},
    }

    stripped = strip_technical(payload)

    for field in TECHNICAL_FIELDS:
        assert field not in stripped["session_level"]
        assert field not in stripped["questions"][0]
    # What the interface legitimately needs survives.
    assert stripped["session_level"] == {"level": "moderate", "n_segments": 7,
                                         "features_disagree": True}


def test_a_missing_session_level_does_not_break_the_strip():
    """Timeline responses have no `session_level` at all; the strip must not
    invent one or crash reaching for it."""
    stripped = strip_technical({"questions": []})
    assert "session_level" not in stripped


# ------------------------------------------------- the narrative shortcut
def test_narrative_skips_the_model_when_nothing_was_measured():
    """
    With zero per-question measurements there is nothing for the model to
    describe, so no request is spent — and no silence is offered for it to
    fill. `prepared=None` is deliberate: if the guard were removed, the model
    path would reach for the baseline and crash, so this test cannot pass by
    accident.
    """
    body = {"questions": []}

    narrative, meta = write_session_narrative(
        None, body, [], Modality.ECG, "SESSION")

    assert meta["trustworthy"] is False
    assert narrative["penyemangat"] == ""
    assert isinstance(narrative["ringkasan_sesi"], str)


# ------------------------------------------------------- over the wire
KEY = "safety-net-key"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("HRV_API_KEYS", KEY)
    monkeypatch.setattr(
        session_route, "write_session_narrative",
        lambda *a, **k: ({"ringkasan_sesi": "", "penyemangat": ""},
                         {"kb_version": "", "model": "", "trustworthy": False}),
    )
    return TestClient(app)


def test_a_quick_answer_session_returns_200_with_the_fallback(client):
    """
    End to end: the exact shape that used to produce the 422 — one question,
    answered fast — now comes back 200 with the session-level reading, the
    question honestly listed as unmeasured, and the developer numbers already
    withheld (an ordinary key gets the stripped view; nothing here opts in).
    """
    body = {
        "rr_ms": beats(7 * 60),
        "baseline_minutes": 2,
        "modality": "ECG",
        "questions": [{"number": 1, "text": "Ceritakan tentang dirimu",
                       "type": "introduction", "answer_start_sec": 120,
                       "answer_end_sec": 135, "gap_end_sec": 150,
                       "is_difficult": False}],
    }

    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})

    assert response.status_code == 200
    data = response.json()
    assert data["questions"] == []
    assert data["coverage"] == {"measured": 0, "total": 1}
    assert data["unmeasured"][0]["number"] == 1
    assert data["session_level"]["level"] in LEVELS
    for field in TECHNICAL_FIELDS:
        assert field not in data["session_level"]
