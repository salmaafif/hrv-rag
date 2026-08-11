"""
make_protocol_fixture.py — reference numbers for the browser-side device test.

`frontend/uji-protokol-hrv.logic.js` re-implements ectopic correction,
segmentation and the time-domain features in JavaScript, because the three-block
device test runs in the browser with no Python anywhere near it. Two
implementations of the same procedure drift apart; the only question is whether
anything notices.

This script makes something notice. It runs a handful of interval series through
the REAL pipeline — the same functions that produced the validated WESAD numbers —
and writes the answers to a JSON file that the JavaScript test suite asserts
against. If either side changes, the JavaScript test fails and names the quantity
that moved.

    python scripts/make_protocol_fixture.py

The output is committed, so the frontend tests need no Python to run.

WHAT IT DOES NOT COVER: the live time axis. Here every timestamp comes from
`cumsum(rr)`, which assumes an unbroken series. A sensor that drops beats leaves a
real gap in wall-clock time, and there is no way to express that through this
entry point — cumsum simply closes the gap. Dropout behaviour is therefore tested
on the JavaScript side alone, with timestamps supplied explicitly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hrv_rag.core.types import Modality, Phase  # noqa: E402
from hrv_rag.features.segmentation import segment_rr_series  # noqa: E402
from hrv_rag.features.time_domain import mean_hr, mean_rr, rmssd  # noqa: E402
from hrv_rag.preprocessing.base import correct_ectopic  # noqa: E402
from hrv_rag.preprocessing.intervals import rr_series_from_intervals  # noqa: E402

OUT = REPO / "frontend" / "uji-protokol-hrv.fixture.json"


def resting_series(rng: np.random.Generator, n: int = 220) -> np.ndarray:
    """
    A plausible seated, silent recording.

    Built as a slow drift plus beat-to-beat noise rather than as white noise
    around a constant, because a real tachogram wanders — and a series that does
    not wander would leave the 20% relative-difference criterion untested, since
    nothing would ever approach it.
    """
    drift = 40.0 * np.sin(np.linspace(0, 3.0, n))
    jitter = rng.normal(0.0, 22.0, n)
    return 880.0 + drift + jitter


def stressed_series(rng: np.random.Generator, n: int = 240) -> np.ndarray:
    """
    A faster, less variable recording with artefacts deliberately injected.

    Every third artefact is a classic ectopic pair — one short interval followed
    by a compensatory long one — which the correction is specified to flag as two
    beats, not one. The rest are single dropouts of the kind optical sensors
    produce when the band shifts.
    """
    rr = 680.0 + 18.0 * np.sin(np.linspace(0, 5.0, n)) + rng.normal(0.0, 11.0, n)
    for k, i in enumerate(range(25, n - 5, 17)):
        if k % 3 == 0:
            rr[i] *= 0.55        # premature beat
            rr[i + 1] *= 1.45    # compensatory pause
        else:
            rr[i] *= 1.7         # a beat was missed, so two intervals merged
    return rr


def reconnect_series(rng: np.random.Generator, n: int = 200) -> np.ndarray:
    """
    A recording interrupted by a momentary disconnection.

    The gap surfaces as a single interval far outside the physiological range,
    which is criterion 1 rather than criterion 2 — worth covering separately
    because the two criteria are evaluated by different code paths.
    """
    rr = resting_series(rng, n)
    rr[97] = 4200.0
    rr[150] = 180.0
    return rr


def describe(name: str, rr_ms: np.ndarray) -> dict:
    """Run one series through the pipeline and record every published number."""
    corrected, is_outlier = correct_ectopic(rr_ms)

    series = rr_series_from_intervals(
        rr_ms, modality=Modality.PPG, subject=name, phase=Phase.QUESTION
    )
    result = segment_rr_series(series)

    segments = [
        {
            "index": s.index,
            "start_sec": round(float(s.start_sec), 6),
            "n_beats": s.n_beats,
            "outlier_ratio": round(float(s.outlier_ratio), 12),
            "rmssd": round(float(rmssd(s.rr_ms)), 9),
        }
        for s in result.segments
    ]

    return {
        "name": name,
        "rr_ms": [round(float(v), 6) for v in rr_ms],
        "expected": {
            "is_outlier": [bool(b) for b in is_outlier],
            "corrected": [round(float(v), 9) for v in corrected],
            "outlier_ratio": round(float(is_outlier.mean()), 12),
            "mean_rr": round(float(mean_rr(corrected)), 9),
            "mean_hr": round(float(mean_hr(corrected)), 9),
            "rmssd": round(float(rmssd(corrected)), 9),
            "n_kept": result.n_kept,
            "n_dropped_short": result.n_dropped_short,
            "n_dropped_noisy": result.n_dropped_noisy,
            "n_total": result.n_total,
            "segments": segments,
        },
    }


def main() -> None:
    # A fixed seed, so re-running this script cannot quietly move the reference
    # numbers the JavaScript suite is pinned to.
    rng = np.random.default_rng(20260810)

    cases = [
        describe("istirahat_bersih", resting_series(rng)),
        describe("tertekan_berartefak", stressed_series(rng)),
        describe("sambungan_terputus", reconnect_series(rng)),
    ]

    payload = {
        "generated_by": "scripts/make_protocol_fixture.py",
        "source_of_truth": [
            "hrv_rag.preprocessing.base.correct_ectopic",
            "hrv_rag.features.segmentation.segment_rr_series",
            "hrv_rag.features.time_domain",
        ],
        "note": (
            "Timestamps here come from cumsum(corrected)/1000, matching "
            "rr_series_from_intervals. Live capture anchors beats on packet "
            "arrival instead, which is tested on the JavaScript side only."
        ),
        "cases": cases,
    }

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"wrote {OUT.relative_to(REPO)}")
    for c in cases:
        e = c["expected"]
        print(
            f"  {c['name']:22s} n={len(c['rr_ms']):4d} "
            f"outlier={e['outlier_ratio'] * 100:5.2f}% "
            f"windows={e['n_kept']}/{e['n_total']} "
            f"(short {e['n_dropped_short']}, noisy {e['n_dropped_noisy']}) "
            f"meanHR={e['mean_hr']:.2f} RMSSD={e['rmssd']:.2f}"
        )


if __name__ == "__main__":
    main()
