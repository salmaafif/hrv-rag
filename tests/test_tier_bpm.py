"""
test_tier_bpm.py — two measurement paths, and the proof that neither leaks into the other.

A session is scored from beat-to-beat intervals when the device delivered them,
and from heart rate alone when it did not. The second path rebuilds a beat series
from the bpm curve so the validated window machinery can run unchanged — which
makes it the one place in the project where a heart-rate-variability number could
be computed from beats that never existed. Every test below guards some part of
that boundary.

THE REGRESSION ANCHOR. `fixtures/golden_rr_sessions.json` holds two sessions,
request and response, captured from the code BEFORE either path existed. The RR
path must reproduce them field for field; the only permitted differences are keys
that did not exist then.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import hrv_rag.rag.narrative as rag_narrative
from hrv_api.app import app
from hrv_api.responses import build_response
from hrv_api.routes import session as session_route
from hrv_api.schemas import MAX_BPM, MIN_BPM, SessionRequest
from hrv_api.services import analysis
from hrv_api.services.analysis import (STREAM_INTERRUPTED, build_session,
                                       prepare)
from hrv_api.services.narrative import write_session_narrative
from hrv_rag.config.settings import settings
from hrv_rag.core.types import Modality
from hrv_rag.features.baseline import BPM_TIER_FEATURES, BaselineProfile
from hrv_rag.features.question import RECOVERY_NOT_MEASURED
from hrv_rag.features.signal_fitness import BPM_ONLY_REASON
from hrv_rag.features.stress_level import classify
from hrv_rag.preprocessing.bpm import beats_from_bpm
from hrv_rag.rag.prompt import load_template

KEY = "test-key"
DEBUG_KEY = "test-debug-key"
GOLDEN = Path(__file__).parent / "fixtures" / "golden_rr_sessions.json"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("HRV_API_KEYS", f"{KEY},{DEBUG_KEY}")
    monkeypatch.setenv("HRV_API_KEYS_DEBUG", DEBUG_KEY)
    monkeypatch.delenv("HRV_ARCHIVE_DIR", raising=False)
    monkeypatch.setattr(
        session_route, "write_session_narrative",
        lambda *a, **k: ({"ringkasan_sesi": "", "penyemangat": ""},
                         {"kb_version": "", "model": "", "trustworthy": False}),
    )


@pytest.fixture
def client():
    return TestClient(app)


def golden(case: str) -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))[case]


# ================================================================== recordings
QUESTIONS = [
    {"number": 1, "text": "Ceritakan tentang dirimu", "type": "introduction",
     "answer_start_sec": 120, "answer_end_sec": 210, "gap_end_sec": 270,
     "is_difficult": True},
    {"number": 2, "text": "Jelaskan cara kerja indeks basis data",
     "type": "technical", "answer_start_sec": 270, "answer_end_sec": 330,
     "gap_end_sec": 350, "is_difficult": False},
    {"number": 3, "text": "Hitung estimasi biaya proyek ini", "type": "numerical",
     "answer_start_sec": 350, "answer_end_sec": 440, "gap_end_sec": 500,
     "is_difficult": True},
]

#: (until session second, bpm): resting at 68, then a rise per answer. Question 2
#: carries the largest rise, so it is the one a correct summary must name.
HR_PROFILE = [(120, 68), (210, 80), (270, 72), (330, 92), (350, 76), (440, 79),
              (500, 72), (540, 71)]


def heart_rate_samples(prelude_sec: float = 0.0, drop: tuple = (),
                       seed: int = 3) -> list[dict]:
    """One report per second, like a broadcasting watch, in recording seconds."""
    rng = np.random.default_rng(seed)
    samples = []
    for t in np.arange(0.0, HR_PROFILE[-1][0] + prelude_sec, 1.0):
        session_t = t - prelude_sec
        if any(a <= session_t < b for a, b in drop):
            continue
        level = next((bpm for end, bpm in HR_PROFILE if session_t < end),
                     HR_PROFILE[-1][1])
        samples.append({"at_sec": float(t),
                        "bpm": float(round(level + rng.normal(0, 1.5)))})
    return samples


def bpm_body(**overrides) -> dict:
    body = {"bpm_samples": heart_rate_samples(), "baseline_minutes": 2,
            "modality": "PPG", "questions": [dict(q) for q in QUESTIONS]}
    body.update(overrides)
    return body


def post(client, body: dict, debug: bool = False) -> dict:
    headers = {"X-API-Key": DEBUG_KEY if debug else KEY}
    if debug:
        body = {**body, "include_technical": True}
    reply = client.post("/api/v1/analyze/session", json=body, headers=headers)
    assert reply.status_code == 200, reply.text
    return reply.json()


def prepared_bpm(body: dict | None = None):
    body = body or bpm_body()
    return prepare(None, None, body["baseline_minutes"], Modality.PPG, "s",
                   offset_sec=body.get("offset_sec", 0.0),
                   bpm_samples=body["bpm_samples"])


# ============================================================ RR path regression
def _diff(expected, actual, path: str = "") -> list[str]:
    """Every place `actual` departs from `expected`. Keys new in `actual` are not diffs."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected an object"]
        out = []
        for key, value in expected.items():
            if key not in actual:
                out.append(f"{path}.{key}: missing")
            else:
                out.extend(_diff(value, actual[key], f"{path}.{key}"))
        return out
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return [f"{path}: list differs in length"]
        return [d for i, (e, a) in enumerate(zip(expected, actual))
                for d in _diff(e, a, f"{path}[{i}]")]
    return [] if expected == actual else [f"{path}: {expected!r} -> {actual!r}"]


def _new_keys(expected, actual, path: str = "") -> set[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = {f"{path}.{k}" for k in actual if k not in expected}
        for key in expected:
            if key in actual:
                found |= _new_keys(expected[key], actual[key], f"{path}.{key}")
        return found
    if isinstance(expected, list) and isinstance(actual, list):
        return {k for e, a in zip(expected, actual) for k in _new_keys(e, a, path)}
    return set()


#: Keys the RR response may carry that the golden capture predates.
#:
#: The three `*_index` keys are the same quantities the golden capture already
#: holds, rescaled to 0-5 for KARIRLINK's result screen (18 September 2026). They
#: are listed here one by one on purpose: a wildcard would let a genuinely new
#: measurement slip into the RR path without anyone noticing.
ALLOWED_NEW_KEYS = {".source", ".summary.reactivity_basis",
                    ".summary.calm_index", ".summary.recovery_index",
                    ".summary.resilience_index"}


@pytest.mark.parametrize("case", ["ecg_offset", "ppg_no_offset"])
@pytest.mark.parametrize("scope", ["standard", "debug"])
def test_the_beat_interval_path_reproduces_the_golden_session(client, case, scope):
    """
    A session recorded with real beat intervals gives exactly the response it gave
    before the heart-rate-only path was written — every level, delta, recovery,
    fitness figure and baseline value, to the last rounded digit.
    """
    stored = golden(case)
    actual = post(client, stored["request"], debug=(scope == "debug"))

    assert _diff(stored[scope], actual) == []
    assert _new_keys(stored[scope], actual) <= ALLOWED_NEW_KEYS
    assert actual["source"] == "beat_intervals"
    assert actual["summary"]["reactivity_basis"] == "rmssd"


# ======================================================== nothing leaks, anywhere
VARIABILITY_TOKENS = {"rmssd", "sdnn", "pnn50", "lf", "hf"}


def variability_leaks(node, path: str = "") -> list[str]:
    """Every number filed under a variability key, and every sentence naming one."""
    leaks = []
    if isinstance(node, dict):
        for key, value in node.items():
            named = set(key.lower().split("_")) & VARIABILITY_TOKENS
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if named and is_number:
                leaks.append(f"{path}.{key}={value!r}")
            leaks += variability_leaks(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            leaks += variability_leaks(item, f"{path}[{i}]")
    elif isinstance(node, str):
        lowered = node.lower()
        if any(word in lowered for word in ("rmssd", "sdnn", "pnn50", "lf/hf")):
            leaks.append(f"{path}: {node!r}")
    return leaks


def test_the_response_is_valid_json_without_a_single_nan():
    """
    Written first, because it closes a whole class at once. JSON has no NaN; one
    anywhere in the payload means a missing measurement escaped as a number.
    """
    body = bpm_body()
    prepared = prepared_bpm(body)
    result, _ = build_session(prepared, body["questions"])
    request = SessionRequest(**{**body, "include_technical": True})
    payload = build_response(request, prepared, result, {}, {}, Modality.PPG,
                             debug_scope=True)

    json.dumps(payload, allow_nan=False)


def test_no_variability_number_appears_anywhere_in_a_heart_rate_session(client):
    payload = post(client, bpm_body(), debug=True)
    assert variability_leaks(payload) == []


def test_the_leak_detector_does_find_variability_in_a_beat_interval_session(client):
    # The control. A detector that finds nothing anywhere would pass the test above.
    payload = post(client, golden("ecg_offset")["request"], debug=True)
    assert variability_leaks(payload)


def test_questions_and_the_whole_session_carry_heart_rate_but_no_rmssd_delta(client):
    # Debug scope, or `delta_rmssd_pct` is stripped anyway and this proves nothing.
    payload = post(client, bpm_body(), debug=True)

    assert payload["questions"]
    for entry in payload["questions"] + [payload["session_level"]]:
        assert entry["delta_rmssd_pct"] is None
        assert isinstance(entry["delta_hr_pct"], float)
        assert not any("RMSSD" in line for line in entry["evidence"])


def test_the_baseline_reports_heart_rate_and_null_rmssd(client):
    baseline = post(client, bpm_body())["baseline"]
    assert baseline["rmssd_ms"] is None
    assert baseline["mean_hr_bpm"] == pytest.approx(68, abs=3)


def test_the_baseline_keeps_heart_rate_and_nothing_else():
    body = bpm_body()
    prepared = prepared_bpm(body)
    _, measurements = build_session(prepared, body["questions"])

    assert set(prepared.baseline.values) == {"mean_hr"}
    assert set(prepared.baseline.spread) == {"mean_hr"}
    # Deleted, not NaN: the key does not exist at all.
    for _, measurement, _, _ in measurements:
        assert set(measurement.reactivity) == {"delta_pct_mean_hr"}


def test_the_allow_list_admits_nothing_it_does_not_name():
    # A feature that does not exist yet must be excluded without anyone listing it.
    full = BaselineProfile("s", values={"mean_hr": 70.0, "mean_rr": 857.0,
                                        "rmssd": 42.0, "lf_hf_ls": 1.8,
                                        "feature_added_next_year": 3.0},
                           spread={"mean_hr": 2.0, "rmssd": 5.0}, n_segments=4)
    kept = full.restricted_to(BPM_TIER_FEATURES)

    assert kept.values == {"mean_hr": 70.0}
    assert kept.spread == {"mean_hr": 2.0}
    assert kept.n_segments == 4
    assert "rmssd" in full.values, "the original profile must not be altered"


def test_the_signal_checks_are_never_run_on_rebuilt_beats(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("assess_signal ran on a heart-rate-only session")

    monkeypatch.setattr(analysis, "assess_signal", refuse)
    assert prepared_bpm().signal_fitness.rmssd_trusted is False

    # The control: the patch point is live, so the line above proves something.
    with pytest.raises(AssertionError):
        request = golden("ecg_offset")["request"]
        prepare(request["rr_ms"], None, 2, Modality.ECG, "s",
                offset_sec=request["offset_sec"])


def test_signal_fitness_says_why_and_claims_no_instrument_numbers(client):
    fitness = post(client, bpm_body())["signal_fitness"]
    assert fitness["rmssd_trusted"] is False
    assert fitness["reasons"] == [BPM_ONLY_REASON]
    assert "bpm" in fitness["reasons"][0]
    for key in ("quantization_step_ms", "missed_beat_ratio", "task_outlier_ratio"):
        assert fitness[key] is None


def test_recovery_is_reported_unmeasured_with_the_true_reason(client):
    body = bpm_body()
    body["questions"][1]["gap_end_sec"] = body["questions"][1]["answer_end_sec"]
    payload = post(client, body)
    by_number = {q["number"]: q for q in payload["questions"]}

    # The device is the reason for BOTH, and the gap makes no difference to it.
    # Question 1 had a gap; question 2 had none, which is the shape of every
    # session's last answer. Telling question 2 "no quiet gap followed this
    # question" was true and still wrong: it names a missing pause as the cause,
    # when this device could not have produced a recovery from any pause at all.
    assert by_number[1]["recovery_pct"] is None
    assert by_number[1]["recovery_note"] == RECOVERY_NOT_MEASURED
    assert by_number[2]["recovery_pct"] is None
    assert by_number[2]["recovery_note"] == RECOVERY_NOT_MEASURED

    assert payload["summary"]["median_recovery_pct"] is None
    assert payload["summary"]["resilience"] is None


def test_the_most_triggering_question_is_named_by_its_heart_rate_rise(client):
    summary = post(client, bpm_body())["summary"]

    assert summary["most_triggering_question"] == 2
    assert summary["reactivity_basis"] == "mean_hr"
    assert summary["median_reactivity_pct"] > 0
    # A reactivity median now exists, and the quadrant must STILL be withheld.
    assert summary["resilience"] is None


@pytest.mark.parametrize("modality", ["ECG", "PPG"])
def test_source_and_tier_name_the_heart_rate_path(client, modality):
    payload = post(client, bpm_body(modality=modality))
    assert payload["source"] == "bpm"
    assert payload["tier"] == "T1-BPM"
    assert payload["modality"] == modality


# ================================================================ rebuilding beats
def test_a_steady_rate_is_not_rounded_down_to_whole_beats():
    # 70 bpm reported once a second. Restarting the beat count at each sample
    # gives exactly one beat per second — 60 bpm — with no error anywhere.
    rebuilt = beats_from_bpm(np.arange(0.0, 120.0), np.full(120, 70.0))
    assert 60000.0 / float(np.mean(rebuilt.rr_ms)) == pytest.approx(70, abs=0.3)


def test_each_window_reads_the_heart_rate_the_device_reported():
    rng = np.random.default_rng(5)
    walk = np.clip(80 + np.cumsum(rng.normal(0, 2, 600)), 55, 120)
    at_sec = np.arange(0.0, 600.0)
    rebuilt = beats_from_bpm(at_sec, walk)
    beat_end = np.cumsum(rebuilt.rr_ms) / 1000.0

    for start in range(0, 540, 30):
        inside = (beat_end >= start) & (beat_end < start + 60)
        rebuilt_hr = 60000.0 / float(np.mean(rebuilt.rr_ms[inside]))
        reported = float(np.mean(walk[(at_sec >= start) & (at_sec < start + 60)]))
        assert rebuilt_hr == pytest.approx(reported, abs=1.0), start


def test_rebuilt_time_matches_reported_time():
    at_sec = np.arange(0.0, 900.0)
    rebuilt = beats_from_bpm(at_sec, 60 + 30 * np.sin(at_sec / 50))
    # Short of the last sample by less than one beat, never beyond it.
    total = float(np.sum(rebuilt.rr_ms)) / 1000.0
    assert 899.0 - 60.0 / 30.0 < total <= 899.0


def test_a_hole_in_the_stream_is_marked_rather_than_passed_off():
    at_sec = np.concatenate([np.arange(0.0, 100.0), np.arange(140.0, 300.0)])
    rebuilt = beats_from_bpm(at_sec, np.full(at_sec.size, 72.0))
    beat_end = np.cumsum(rebuilt.rr_ms) / 1000.0

    assert rebuilt.gaps_sec == [pytest.approx((100.0, 140.0))]
    flagged = beat_end[rebuilt.in_gap]
    assert flagged.min() > 100.0 and flagged.max() <= 140.0
    assert flagged.size == pytest.approx(40 * 72 / 60, abs=1)
    # Time kept: a dropped stretch must not pull later beats earlier.
    assert float(beat_end[-1]) == pytest.approx(299.0, abs=1.0)


def test_a_slow_reporting_device_is_not_mistaken_for_a_broken_one():
    # A report every five seconds is this device's normal, read from its own data.
    rebuilt = beats_from_bpm(np.arange(0.0, 300.0, 5.0), np.full(60, 75.0))
    assert rebuilt.gaps_sec == []
    assert not rebuilt.in_gap.any()


def test_samples_that_run_backwards_are_refused():
    with pytest.raises(ValueError):
        beats_from_bpm([0.0, 2.0, 1.0], [70.0, 71.0, 72.0])


def test_a_hole_during_an_answer_leaves_that_question_unmeasured_and_says_why(client):
    body = bpm_body(bpm_samples=heart_rate_samples(drop=((360, 420),)))
    payload = post(client, body)

    assert payload["coverage"] == {"measured": 2, "total": 3}
    assert payload["unmeasured"] == [{
        "number": 3, "text": QUESTIONS[2]["text"], "type": "numerical",
        "reason": STREAM_INTERRUPTED,
    }]


# ================================================================ choosing the path
def interval_recording(mean_ms: float, seconds: float, seed: int = 9) -> list[float]:
    rng = np.random.default_rng(seed)
    beats, clock = [], 0.0
    while clock < seconds:
        value = float(mean_ms + rng.normal(0, 30))
        beats.append(value)
        clock += value / 1000.0
    return beats


def test_the_path_follows_coverage_and_the_two_are_never_spliced(client):
    # Intervals at ~50 bpm, heart-rate samples at ~68 bpm: which path ran is
    # readable straight off the baseline heart rate.
    threshold = settings.tier.min_rr_coverage
    body = bpm_body(rr_ms=interval_recording(1200.0, 540.0))

    enough = post(client, {**body, "rr_coverage": threshold})
    assert enough["source"] == "beat_intervals"
    assert enough["baseline"]["mean_hr_bpm"] == pytest.approx(50, abs=3)

    short = post(client, {**body, "rr_coverage": threshold - 0.01})
    assert short["source"] == "bpm"
    assert short["baseline"]["mean_hr_bpm"] == pytest.approx(68, abs=3)
    assert short["baseline"]["rmssd_ms"] is None


def test_heart_rate_samples_alone_are_a_valid_request():
    SessionRequest(**bpm_body())


def test_both_recordings_without_coverage_are_refused():
    with pytest.raises(ValidationError):
        SessionRequest(**bpm_body(rr_ms=[850.0] * 400))


def test_a_file_together_with_heart_rate_samples_is_refused():
    with pytest.raises(ValidationError):
        SessionRequest(**bpm_body(csv="856\n842\n"))


def test_heart_rate_bounds_come_from_the_interval_physiology():
    assert (MIN_BPM, MAX_BPM) == (30.0, 200.0)
    for bad in (MIN_BPM - 1, MAX_BPM + 1):
        samples = heart_rate_samples()
        samples[5] = {"at_sec": samples[5]["at_sec"], "bpm": bad}
        with pytest.raises(ValidationError):
            SessionRequest(**bpm_body(bpm_samples=samples))


# ======================================================================= the clock
def test_a_watch_connected_early_does_not_move_the_questions(client):
    plain = post(client, bpm_body(), debug=True)
    early = post(client, bpm_body(bpm_samples=heart_rate_samples(prelude_sec=60),
                                  offset_sec=60), debug=True)

    assert early["summary"]["most_triggering_question"] == 2
    for a, b in zip(plain["questions"], early["questions"]):
        assert b["delta_hr_pct"] == pytest.approx(a["delta_hr_pct"], abs=3)


def test_a_heart_rate_session_places_questions_on_the_report_clock(client):
    """
    A device sending both streams has two clocks. When the session falls to
    heart rate, the offset measured on the report clock must place the
    questions — the interval-clock offset describes a series that was set aside.
    """
    plain = post(client, bpm_body(), debug=True)
    both = dict(bpm_samples=heart_rate_samples(prelude_sec=60),
                rr_ms=interval_recording(1200.0, 600.0),
                rr_coverage=settings.tier.min_rr_coverage - 0.2)

    honest = post(client, bpm_body(**both, offset_sec=5, bpm_offset_sec=60),
                  debug=True)
    assert honest["source"] == "bpm"
    assert honest["summary"]["most_triggering_question"] == 2
    for a, b in zip(plain["questions"], honest["questions"]):
        assert b["delta_hr_pct"] == pytest.approx(a["delta_hr_pct"], abs=3)

    # The control: the interval-clock offset alone lands on the wrong minutes.
    wrong = post(client, bpm_body(**both, offset_sec=5), debug=True)
    q2 = [q for q in honest["questions"] if q["number"] == 2][0]
    q2_wrong = [q for q in wrong["questions"] if q["number"] == 2][0]
    assert abs(q2["delta_hr_pct"] - q2_wrong["delta_hr_pct"]) > 10


def test_ignoring_the_early_minute_is_what_would_move_them(client):
    # The control: the same recording, told nothing about its prelude.
    honest = post(client, bpm_body(bpm_samples=heart_rate_samples(prelude_sec=60),
                                   offset_sec=60), debug=True)
    blind = post(client, bpm_body(bpm_samples=heart_rate_samples(prelude_sec=60)),
                 debug=True)
    q2 = [q for q in honest["questions"] if q["number"] == 2][0]
    q2_blind = [q for q in blind["questions"] if q["number"] == 2][0]
    assert abs(q2["delta_hr_pct"] - q2_blind["delta_hr_pct"]) > 10


# ======================================================================= narrative
def _capture_writer(monkeypatch) -> dict:
    captured: dict = {}

    class FakeWriter:
        def __init__(self, cfg=None, **_):
            captured["prompt"] = cfg.narrative_prompt

        def write(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                narrative=SimpleNamespace(questions=[], session_summary="",
                                          encouragement=""),
                kb_version="kb", model="m", is_trustworthy=True,
                prompt_name=captured["prompt"])

    monkeypatch.setattr(rag_narrative, "NarrativeWriter", FakeWriter)
    return captured


def test_a_heart_rate_session_is_described_with_the_prompt_that_says_so(monkeypatch):
    captured = _capture_writer(monkeypatch)
    body = bpm_body()
    prepared = prepared_bpm(body)
    result, measurements = build_session(prepared, body["questions"])

    _, meta = write_session_narrative(prepared, result, measurements,
                                      Modality.PPG, "s")

    assert captured["prompt"] == settings.llm.narrative_prompt_heart_rate_only
    assert meta["prompt_version"] == settings.llm.narrative_prompt_heart_rate_only
    assert "bpm" in captured["device"]
    assert not any("RMSSD" in line
                   for item in captured["inputs"] for line in item.verdict.evidence)


def test_a_beat_interval_session_keeps_its_original_prompt(monkeypatch):
    captured = _capture_writer(monkeypatch)
    request = golden("ecg_offset")["request"]
    prepared = prepare(request["rr_ms"], None, 2, Modality.ECG, "s",
                       offset_sec=request["offset_sec"])
    result, measurements = build_session(prepared, request["questions"])

    write_session_narrative(prepared, result, measurements, Modality.ECG, "s")

    assert captured["prompt"] == settings.llm.narrative_prompt
    assert captured["device"] == "ECG sensor"


def test_the_heart_rate_prompt_never_claims_variability_was_recorded():
    original = load_template(settings.llm.narrative_prompt)
    heart_rate = load_template(settings.llm.narrative_prompt_heart_rate_only)

    assert "variability was recorded" in original          # the control
    assert "variability was recorded" not in heart_rate
    assert "NOT measured" in heart_rate
    # Same placeholders, so the writer fills it without knowing which it holds.
    fields = dict(context="", session_id="", modality="", device="",
                  signal_quality="", confounders="", baseline_note="",
                  questions="", resilience="", most_triggering="",
                  recovery_summary="")
    original.format(**fields)
    heart_rate.format(**fields)


def test_the_retrieval_query_centres_on_the_largest_heart_rate_rise():
    body = bpm_body()
    prepared = prepared_bpm(body)
    _, measurements = build_session(prepared, body["questions"])
    inputs = [rag_narrative.NarrativeInput(
        question_no=q.number, question_type=q.qtype.value,
        verdict=classify(m.reactivity), reactivity=m.reactivity,
        recovery_pct=None, recovery_note="", attribution_hint="")
        for q, m, _, _ in measurements]

    # Question 2 is the technical one, and the largest rise.
    assert "during a technical question" in rag_narrative.build_session_query(inputs)
