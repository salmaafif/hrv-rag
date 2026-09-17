"""
test_real_watch_session.py — the first real heart-rate-only session, frozen.

Every other test of the bpm path feeds it numbers this project invented. This one
feeds it a session a person actually sat through: 17 September 2026, a HUAWEI Band
HR-B88 broadcasting heart rate and no beat intervals, 838 reports over fourteen
minutes, two answered questions, recorded through the KARIRLINK web app and
downloaded with the development-only recording button.

WHAT IT GUARDS. Synthetic sessions are built to be clean: perfectly regular
reporting, a calm baseline, a heart rate that rises when the script says it should.
This one is none of those things — the resting window is unsteady enough that the
baseline check flags it, and the reactivity is near zero — and that is exactly why
it is worth keeping. A change that quietly alters the clock arithmetic, the window
gate, the baseline restriction, or the reason a recovery is not measured will move
one of the numbers below.

The expected values were not chosen. They are what the code produced on the day,
and they are asserted to the decimal the API reports.

WHAT THIS SESSION CANNOT GUARD, stated so nobody trusts it to. Both offsets in the
request are the same number, 133.517, because a browser with no intervals measures
the anchor on the report clock and writes it into both fields. So substituting one
clock for the other changes nothing here, and deleting that substitution leaves
every assertion below passing. The synthetic
`test_tier_bpm.py::test_a_heart_rate_session_places_questions_on_the_report_clock`
is what fails then, and it was verified to fail. Real data is a witness, not a
replacement for a case built to separate two quantities.

THE WORDING OF THE QUESTIONS WAS REPLACED before the fixture entered the
repository: the real ones quote the candidate's own history. Timings, heart rate,
and every number are untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hrv_api.schemas import SessionRequest
from hrv_api.services.analysis import (BPM, baseline_block, build_session,
                                       prepare)
from hrv_rag.core.types import Modality

FIXTURE = Path(__file__).parent / "fixtures" / "watch_bpm_session_2026_09_17.json"


@pytest.fixture(scope="module")
def request_body() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["request"]


@pytest.fixture(scope="module")
def analysed(request_body):
    prepared = prepare(
        request_body["rr_ms"], None, request_body["baseline_minutes"],
        Modality.PPG, "real-watch-session",
        offset_sec=request_body["offset_sec"],
        bpm_samples=request_body["bpm_samples"],
        rr_coverage=request_body["rr_coverage"],
        bpm_offset_sec=request_body["bpm_offset_sec"],
    )
    body, _ = build_session(prepared, request_body["questions"])
    return prepared, body


def test_the_recorded_request_still_satisfies_the_contract(request_body):
    parsed = SessionRequest.model_validate(request_body)

    assert len(parsed.bpm_samples) == 838
    assert parsed.rr_ms == []
    assert parsed.rr_coverage == 0
    assert parsed.modality == "PPG"


def test_the_session_takes_the_heart_rate_path_on_the_report_clock(analysed):
    prepared, _ = analysed

    assert prepared.source == BPM
    # The watch was connected 8 seconds before the session clock was anchored, and
    # the first question came 259 seconds later; the zero point sent to the module
    # is `baseline` minutes before it. Both numbers come from the report clock,
    # because this device produced no intervals to measure the other one on.
    assert prepared.offset_sec == pytest.approx(133.517)
    assert prepared.rest_end_sec == pytest.approx(266.8, abs=0.1)
    # A stream this device never interrupted.
    assert prepared.stream_gaps_sec == []


def test_the_baseline_reports_heart_rate_only_and_says_it_was_unsteady(analysed):
    prepared, _ = analysed
    block = baseline_block(prepared)

    assert set(prepared.baseline.values) == {"mean_hr"}
    assert block["rmssd_ms"] is None
    assert block["mean_hr_bpm"] == pytest.approx(100.9)
    assert block["n_segments"] == 14
    # The resting minutes were spent reading a consent screen, not resting, and the
    # module says so rather than reporting a confident comparison.
    assert block["is_stable"] is False
    assert "belum benar-benar tenang" in block["warning"]


def test_both_questions_are_measured_and_neither_claims_a_recovery(analysed):
    _, body = analysed
    first, second = body["questions"]

    assert body["unmeasured"] == []
    assert body["coverage"] == {"measured": 2, "total": 2}
    assert (first["level"], second["level"]) == ("low", "low")
    assert first["recovery_pct"] is None and second["recovery_pct"] is None
    # Two different reasons, and the difference matters: the first could never be
    # measured because the device gives no intervals; the second had no quiet gap
    # because the session ended on it.
    assert "this device reports heart rate only" in first["recovery_note"]
    assert second["recovery_note"] == "no quiet gap followed this question"


def test_the_summary_is_ordered_by_heart_rate_and_withholds_resilience(analysed):
    _, body = analysed

    assert body["summary"] == {
        "most_triggering_question": 1,
        "resilience": None,
        "median_reactivity_pct": -0.3,
        "median_recovery_pct": None,
        "reactivity_basis": "mean_hr",
    }
    assert body["session_level"]["level"] == "low"
    assert body["session_level"]["delta_rmssd_pct"] is None
    assert body["session_level"]["delta_hr_pct"] == -0.4
    assert body["session_level"]["n_segments"] == 12


def test_nothing_in_the_body_is_a_nan_or_a_variability_number(analysed):
    _, body = analysed

    # allow_nan=False turns a NaN into an exception instead of a token no JSON
    # parser accepts — the whole class of leaks, caught by one call.
    json.dumps(body, allow_nan=False)

    def numbers_named_after_variability(node, path=""):
        found = []
        if isinstance(node, dict):
            for key, value in node.items():
                named = {"rmssd", "sdnn", "pnn50", "lf", "hf"} & set(key.lower().split("_"))
                if named and isinstance(value, (int, float)) and not isinstance(value, bool):
                    found.append(f"{path}.{key}")
                found += numbers_named_after_variability(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                found += numbers_named_after_variability(item, f"{path}[{index}]")
        return found

    assert numbers_named_after_variability(body) == []
