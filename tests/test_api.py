"""
Tests for the HTTP surface KARIRLINK's gateway will call.

No API key is spent here. The narrative is stubbed, which is not a shortcut but
the point: the label comes from a deterministic rule that never talks to a model,
so the interesting question is what the service returns when the model is
UNAVAILABLE — and that is the state a free-tier quota spends most of its day in.

What matters most below, in order:

  - a recording in the wrong unit is refused with a reason, not analysed;
  - the technical numbers stay out of the response unless asked for;
  - `recovery_pct: null` never becomes 0;
  - a failed model call costs the prose and nothing else.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from hrv_api.app import app
# The narrative writers are patched where they are USED, not where they are
# defined — each route module imported the name into its own namespace, so
# patching the definition would leave the route still holding the original.
from hrv_api.routes import session as session_route
from hrv_api.routes import timeline as timeline_route

KEY = "test-key"
DEBUG_KEY = "test-debug-key"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("HRV_API_KEYS", KEY)
    # Every test runs with the model unavailable unless it says otherwise. That
    # is the honest default: the numbers must stand on their own.
    monkeypatch.setattr(
        session_route, "write_session_narrative",
        lambda *a, **k: ({"ringkasan_sesi": "", "penyemangat": ""},
                         {"kb_version": "", "model": "", "trustworthy": False}),
    )
    monkeypatch.setattr(
        timeline_route, "write_timeline_narrative",
        lambda *a, **k: ({"ringkasan": "", "rekomendasi": "", "penyemangat": ""},
                         {"kb_version": "", "model": "", "trustworthy": False}),
    )


@pytest.fixture
def client():
    return TestClient(app)


def beats(minutes: float, ms: float = 857.0) -> list[float]:
    """A steady recording of the requested length."""
    rng = np.random.default_rng(0)
    n = int(minutes * 60 * 1000 / ms)
    return [float(v) for v in ms + rng.normal(0, 25, n)]


def session_body(**overrides) -> dict:
    body = {
        "rr_ms": beats(6),
        "baseline_minutes": 2,
        "modality": "ECG",
        "questions": [
            {"number": 1, "text": "Ceritakan tentang dirimu",
             "type": "introduction", "answer_start_sec": 120,
             "answer_end_sec": 210, "gap_end_sec": 270, "is_difficult": True},
        ],
    }
    body.update(overrides)
    return body


# ------------------------------------------------------------------ access
def test_health_needs_no_key(client):
    assert client.get("/health").status_code == 200


def test_a_request_without_a_key_is_refused(client):
    # The Gemini quota behind this endpoint belongs to one person. An open URL is
    # an open invitation to empty it.
    response = client.post("/api/v1/analyze/timeline", json=session_body())
    assert response.status_code == 401


def test_a_request_with_the_wrong_key_is_refused(client):
    response = client.post("/api/v1/analyze/timeline", json=session_body(),
                           headers={"X-API-Key": "guessed"})
    assert response.status_code == 401


def test_an_unconfigured_service_refuses_everyone(client, monkeypatch):
    """
    With no keys configured the service closes rather than opens.

    The opposite default fails silently and expensively: it would work perfectly
    in testing and be wide open in production.
    """
    monkeypatch.delenv("HRV_API_KEYS", raising=False)
    response = client.post("/api/v1/analyze/timeline", json=session_body(),
                           headers={"X-API-Key": KEY})
    assert response.status_code == 503


# ------------------------------------------------------------ bad recordings
def test_a_recording_in_seconds_is_refused_with_a_reason(client):
    # Left to run, every value would fall outside human physiology, every window
    # would be discarded, and the caller would get a baffling "no data" instead
    # of "you sent the wrong unit".
    body = session_body(rr_ms=[v / 1000 for v in beats(6)])
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 422
    assert "SECONDS" in response.json()["detail"]


def test_heart_rate_instead_of_intervals_is_refused(client):
    """
    The dangerous one: bpm and intervals are inverses, so reading one as the
    other does not merely rescale the answer — it reverses it. A racing heart
    would be reported as a calm one.
    """
    body = session_body(rr_ms=[70.0] * 400)
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 422
    assert "HEART RATE" in response.json()["detail"]


def test_a_resting_period_below_the_floor_is_refused(client):
    # One minute yields no baseline window at all, so the session would be
    # unscoreable.
    body = session_body(baseline_minutes=1)
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 422


def test_the_floor_is_enforced_by_the_schema_not_only_by_the_analysis():
    """
    Pins WHICH guard rejects a too-short resting period.

    Two independent ones exist: the schema refuses the value outright, and the
    analysis fails later because no baseline window can be built. That redundancy
    is welcome, but it makes an endpoint test unable to tell which one fired —
    the request is refused either way. Checking the schema directly keeps the
    cheap guard from quietly disappearing behind the expensive one.
    """
    from pydantic import ValidationError

    from hrv_api.schemas import MIN_BASELINE_MINUTES, SessionRequest

    with pytest.raises(ValidationError):
        SessionRequest(
            rr_ms=[850.0] * 400, baseline_minutes=MIN_BASELINE_MINUTES - 0.5,
            modality="ECG",
            questions=[{"number": 1, "text": "?", "type": "introduction",
                        "answer_start_sec": 120, "answer_end_sec": 210,
                        "gap_end_sec": 270, "is_difficult": False}],
        )


def test_sending_both_a_file_and_live_beats_is_refused(client):
    # Both are valid recordings and both would produce a complete report. Only
    # one of them is the session the person actually did.
    body = session_body(csv="856\n842\n")
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 422


def test_sending_no_recording_at_all_is_refused(client):
    body = session_body()
    del body["rr_ms"]
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 422


def test_a_question_whose_times_run_backwards_is_refused(client):
    body = session_body()
    body["questions"][0]["answer_end_sec"] = 100      # before the start
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 422


# ------------------------------------------------------------- the response
def test_session_response_matches_the_contract(client):
    response = client.post("/api/v1/analyze/session", json=session_body(),
                           headers={"X-API-Key": KEY})
    assert response.status_code == 200
    body = response.json()

    assert set(body) >= {"session_id", "modality", "tier", "baseline",
                         "questions", "summary", "narrative", "meta"}
    assert body["modality"] == "ECG"
    question = body["questions"][0]
    assert set(question) >= {"number", "text", "type", "level", "recovery_pct",
                             "recovery_note", "penjelasan", "saran"}
    assert question["level"] in {"low", "moderate", "high"}


def test_the_baseline_reports_how_many_windows_it_rests_on(client):
    # Every percentage in the response is divided by this median, so how much is
    # behind it is part of the result, not a detail.
    response = client.post("/api/v1/analyze/session", json=session_body(),
                           headers={"X-API-Key": KEY})
    baseline = response.json()["baseline"]
    assert baseline["n_segments"] >= 2
    assert baseline["rmssd_ms"] > 0


def test_technical_numbers_are_withheld_by_default(client):
    """
    Users must never be shown feature names or a raw score. An API cannot police
    how a caller renders things, so the compliant response is the one returned to
    an integrator who never thinks about it.
    """
    response = client.post("/api/v1/analyze/session", json=session_body(),
                           headers={"X-API-Key": KEY})
    question = response.json()["questions"][0]
    for field in ("score", "delta_rmssd_pct", "delta_hr_pct", "evidence"):
        assert field not in question


def test_technical_numbers_appear_for_a_debug_scoped_key(client, monkeypatch):
    # A debug key must also be an accepted key — HRV_API_KEYS_DEBUG narrows
    # who gets the technical layer, it does not replace HRV_API_KEYS as the
    # check for whether the caller may call the service at all.
    monkeypatch.setenv("HRV_API_KEYS", f"{KEY},{DEBUG_KEY}")
    monkeypatch.setenv("HRV_API_KEYS_DEBUG", DEBUG_KEY)
    response = client.post("/api/v1/analyze/session",
                           json=session_body(include_technical=True),
                           headers={"X-API-Key": DEBUG_KEY})
    question = response.json()["questions"][0]
    assert "score" in question and "evidence" in question


def test_a_debug_scoped_key_still_needs_include_technical_asked_for(client, monkeypatch):
    # Scope alone is not enough either — both `debug_scope` and
    # `request.include_technical` must be true. A debug key should not change
    # the default response shape for a caller who never asked for more.
    monkeypatch.setenv("HRV_API_KEYS", f"{KEY},{DEBUG_KEY}")
    monkeypatch.setenv("HRV_API_KEYS_DEBUG", DEBUG_KEY)
    response = client.post("/api/v1/analyze/session", json=session_body(),
                           headers={"X-API-Key": DEBUG_KEY})
    question = response.json()["questions"][0]
    assert "score" not in question


def test_an_ordinary_key_cannot_grant_itself_the_technical_layer(client):
    """
    The finding A6 exists to close: `include_technical` used to be the whole
    gate, and it lives in the request body — a field the caller writes. A key
    that never appears in `HRV_API_KEYS_DEBUG` must not be able to unlock the
    technical layer just by asking for it, no matter what the body says.
    """
    response = client.post("/api/v1/analyze/session",
                           json=session_body(include_technical=True),
                           headers={"X-API-Key": KEY})
    assert response.status_code == 200
    question = response.json()["questions"][0]
    for field in ("score", "delta_rmssd_pct", "delta_hr_pct", "evidence"):
        assert field not in question


def test_the_disagreement_flag_survives_stripping(client):
    """
    Not a measurement but a warning: the two markers pointed opposite ways, so
    the reading is less certain. Removing it would let an uncertain result be
    presented as a confident one.
    """
    response = client.post("/api/v1/analyze/session", json=session_body(),
                           headers={"X-API-Key": KEY})
    assert "features_disagree" in response.json()["questions"][0]


def test_unmeasurable_recovery_is_null_and_never_zero(client):
    """
    Zero would claim the person did not settle at all — a far stronger statement
    than "there was no gap long enough to look at".
    """
    body = session_body()
    # No quiet stretch after the answer at all.
    body["questions"][0]["gap_end_sec"] = body["questions"][0]["answer_end_sec"]
    response = client.post("/api/v1/analyze/session", json=body,
                           headers={"X-API-Key": KEY})

    question = response.json()["questions"][0]
    assert question["recovery_pct"] is None
    assert question["recovery_note"] != ""


def test_timeline_response_scores_every_window(client):
    body = {"rr_ms": beats(6), "baseline_minutes": 2, "modality": "ECG"}
    response = client.post("/api/v1/analyze/timeline", json=body,
                           headers={"X-API-Key": KEY})
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["timeline"]) > 0
    assert payload["duration_sec"] > 0
    counts = payload["summary"]
    assert (counts["count_low"] + counts["count_moderate"]
            + counts["count_high"]) == len(payload["timeline"])


def test_timeline_windows_carry_authoritative_seconds(client):
    # `minute` is a display label and can be fractional, because windows advance
    # every 30 seconds. The seconds are what anything downstream should use.
    body = {"rr_ms": beats(6), "baseline_minutes": 2, "modality": "ECG"}
    payload = client.post("/api/v1/analyze/timeline", json=body,
                          headers={"X-API-Key": KEY}).json()

    first = payload["timeline"][0]
    # `approx`, because both ends are rounded to a tenth from a start that now
    # falls on a beat boundary rather than on a whole second. 179.3 - 119.3 is
    # exactly 60 in decimal and 59.999... in binary floating point.
    assert first["end_sec"] - first["start_sec"] == pytest.approx(60)
    # The first window starts where the resting period ENDED, which is a beat
    # boundary near the requested two minutes rather than exactly on it. It used
    # to read 120.0 because the code added `baseline_minutes * 60` — the same
    # assumption that put every question window in the wrong place.
    assert first["start_sec"] == pytest.approx(120, abs=2)


def test_modality_travels_with_the_result(client):
    # The interface has to be able to say whether a reading came from a chest
    # strap or a watch, because that is what decides how much it is trusted.
    body = session_body(modality="PPG")
    payload = client.post("/api/v1/analyze/session", json=body,
                          headers={"X-API-Key": KEY}).json()
    assert payload["modality"] == "PPG"


def test_tier_matches_the_modality(client):
    """
    Decision A5: a client must be able to tell which product surface it may
    render (docs/ARSITEKTUR_KARIRLINK_HRV.md A4's T0/T1/T2 table) without
    inferring it from which fields happen to be present.
    """
    ecg = client.post("/api/v1/analyze/session", json=session_body(modality="ECG"),
                      headers={"X-API-Key": KEY}).json()
    ppg = client.post("/api/v1/analyze/session", json=session_body(modality="PPG"),
                      headers={"X-API-Key": KEY}).json()
    assert ecg["tier"] == "T2"
    assert ppg["tier"] == "T1"


# ----------------------------------------------------- degrading gracefully
def test_an_unavailable_model_costs_the_prose_but_not_the_numbers(client):
    """
    The whole reason the label is decided by a rule instead of by the model.

    With Gemini unreachable — the state a free-tier quota spends most of its day
    in — every measurement is still returned, and `trustworthy` says the prose
    should not be shown as it stands.
    """
    payload = client.post("/api/v1/analyze/session", json=session_body(),
                          headers={"X-API-Key": KEY}).json()

    assert payload["questions"][0]["level"] in {"low", "moderate", "high"}
    assert payload["baseline"]["rmssd_ms"] > 0
    assert payload["meta"]["trustworthy"] is False


def test_a_narrative_that_raises_does_not_take_the_response_with_it(
    client, monkeypatch,
):
    def explode(*args, **kwargs):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr("hrv_rag.rag.narrative.NarrativeWriter", explode)
    # Restore the real wrapper so its own error handling is what runs.
    from hrv_api.services.narrative import write_session_narrative
    monkeypatch.setattr(session_route, "write_session_narrative",
                        write_session_narrative)

    response = client.post("/api/v1/analyze/session", json=session_body(),
                           headers={"X-API-Key": KEY})
    assert response.status_code == 200
    assert response.json()["meta"]["trustworthy"] is False


# ------------------------------------------------------- the session archive
def test_a_consented_session_is_kept_whole(client, tmp_path, monkeypatch):
    """
    The archive is the answer to K17: no real session had ever been kept, so
    nothing could be re-analysed, cited, or later labelled. What it stores must
    be the EXACT recording — the response can always be recomputed from it, the
    recording can never be produced again.
    """
    monkeypatch.setenv("HRV_ARCHIVE_DIR", str(tmp_path))
    body = session_body(store_consented=True, session_id="pilot-01")

    reply = client.post("/api/v1/analyze/session", json=body,
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    import json as jsonlib
    kept = jsonlib.loads(files[0].read_text(encoding="utf-8"))
    assert kept["format"] == "hrv-session-archive-v1"
    assert kept["request"]["rr_ms"] == body["rr_ms"]          # verbatim, whole
    assert kept["response"]["questions"], "the shown result travels with it"


def test_no_consent_means_nothing_is_stored(client, tmp_path, monkeypatch):
    """
    The unticked checkbox is a complete answer. A configured server must not
    'helpfully' keep the recording anyway — that would turn an infrastructure
    setting into a consent override.
    """
    monkeypatch.setenv("HRV_ARCHIVE_DIR", str(tmp_path))

    reply = client.post("/api/v1/analyze/session", json=session_body(),
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200
    assert list(tmp_path.glob("*.json")) == []


def test_an_unconfigured_server_stores_nothing_even_with_consent(
        client, tmp_path, monkeypatch):
    """
    The second lock. The module will run on somebody else's infrastructure one
    day; a caller's flag alone must not be able to start collection on a server
    whose operator never chose a destination for it.
    """
    monkeypatch.delenv("HRV_ARCHIVE_DIR", raising=False)

    reply = client.post("/api/v1/analyze/session",
                        json=session_body(store_consented=True),
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200
    assert list(tmp_path.glob("*.json")) == []

    # Asked DIRECTLY, because "nothing appeared in tmp_path" cannot see a write
    # that went somewhere else. A fallback directory smuggled in as a default
    # would make this return a path — and that is precisely the mutation this
    # line exists to catch.
    from hrv_api.services.archive import archive_session
    assert archive_session({"store_consented": True, "session_id": "x"},
                           {}) is None


def test_a_hostile_session_id_cannot_escape_the_archive_directory(
        client, tmp_path, monkeypatch):
    """
    `session_id` comes from the caller and ends up in a filename. Dots and
    separators are stripped, so `../../etc/passwd` can only ever name a file
    INSIDE the archive directory.
    """
    monkeypatch.setenv("HRV_ARCHIVE_DIR", str(tmp_path))
    body = session_body(store_consented=True, session_id="../../etc/passwd")

    reply = client.post("/api/v1/analyze/session", json=body,
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert ".." not in files[0].name and "/" not in files[0].name


def test_a_failed_archive_never_fails_the_analysis(client, monkeypatch):
    """
    The person answered questions and is owed their result. Losing the archive
    copy is an operational regret, not a reason to throw their session away —
    so a directory that cannot be written costs a log line, never a 500.
    """
    monkeypatch.setenv("HRV_ARCHIVE_DIR", "Z:/tidak-ada/dan-tidak-bisa-dibuat")

    reply = client.post("/api/v1/analyze/session",
                        json=session_body(store_consented=True),
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200
    assert reply.json()["questions"]


# ---------------------------------------------------- signal fitness masking
def test_untrusted_rmssd_loses_its_vote_but_keeps_being_reported(client):
    """
    The whole point of the fitness check, proven through the HTTP surface.

    The recording is built so the two features DISAGREE on purpose: RMSSD
    collapses to zero after the rest (a -100% drop, worth two points), while
    heart rate barely moves. And the recording's clock is 100 ms coarse against
    a resting RMSSD of ~100 ms — a signal whose jitter figures are mostly its
    own quantization. Without the mask the label would be `moderate` on the
    say-so of a number the instrument cannot resolve; with it, the rule hears
    only heart rate and says `low`.
    """
    rest = [900.0, 1000.0] * 65            # ~123 s, RMSSD 100 ms, 100 ms grid
    task = [1000.0] * 200                  # RMSSD 0 -> -100%; HR -5% (calm)
    body = {"rr_ms": rest + task, "baseline_minutes": 2, "modality": "PPG"}

    reply = client.post("/api/v1/analyze/timeline", json=body,
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200
    data = reply.json()

    fitness = data["signal_fitness"]
    assert fitness["rmssd_trusted"] is False
    assert any("clock" in r for r in fitness["reasons"])

    # The mask decided the label: every window scored from heart rate alone.
    assert {p["level"] for p in data["timeline"]} == {"low"}


def test_a_trusted_recording_still_scores_with_rmssd(client):
    """
    The control. Same shape of disagreement, but on a millisecond-fine clock —
    the drop is now a measurement, not quantization, and the rule must hear it.
    A mask that silenced RMSSD everywhere would pass the test above and fail
    this one.
    """
    rest = [900.0 + (i * 37) % 23 + 60 * (i % 2) for i in range(130)]
    task = [1000.0 + (i * 41) % 7 for i in range(200)]     # near-flat jitter
    body = {"rr_ms": rest + task, "baseline_minutes": 2, "modality": "PPG"}

    reply = client.post("/api/v1/analyze/timeline", json=body,
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 200
    data = reply.json()

    assert data["signal_fitness"]["rmssd_trusted"] is True
    assert "moderate" in {p["level"] for p in data["timeline"]} or \
           "high" in {p["level"] for p in data["timeline"]}


def test_a_consented_failure_keeps_the_recording_too(client, tmp_path, monkeypatch):
    """
    The third real pilot session failed with a 422 and its recording evaporated,
    because archiving only ran after success. A failed consented session is
    still a recording — often the MORE valuable kind, since failures are what
    the field metrics count and re-analysis needs the bytes that failed.
    """
    monkeypatch.setenv("HRV_ARCHIVE_DIR", str(tmp_path))
    body = session_body(store_consented=True, rr_ms=[850.0] * 40)  # far too short

    reply = client.post("/api/v1/analyze/session", json=body,
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 422

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    import json as jsonlib
    kept = jsonlib.loads(files[0].read_text(encoding="utf-8"))
    assert kept["request"]["rr_ms"] == body["rr_ms"]
    assert "error" in kept["response"]


def test_an_unconsented_failure_still_stores_nothing(client, tmp_path, monkeypatch):
    monkeypatch.setenv("HRV_ARCHIVE_DIR", str(tmp_path))

    reply = client.post("/api/v1/analyze/session",
                        json=session_body(rr_ms=[850.0] * 40),
                        headers={"X-API-Key": KEY})
    assert reply.status_code == 422
    assert list(tmp_path.glob("*.json")) == []
