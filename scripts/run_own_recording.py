"""
run_own_recording.py — analyse YOUR OWN recording, offline, without a backend.

    python scripts/run_own_recording.py rekaman.csv --wear chest
    python scripts/run_own_recording.py rekaman.csv --wear wrist --baseline 5

The file is one inter-beat interval per line, in MILLISECONDS, no header:

    856
    842
    871

That is what heart-rate apps export (Polar Sensor Logger, Elite HRV and similar),
so no editing should be needed. If the numbers turn out to be seconds or beats per
minute the script says so and stops, rather than producing a confident report built
on the wrong unit.

WHY THIS EXISTS SEPARATELY FROM THE WEB DEMO. The frontend currently talks to a
fixture backend that ignores the uploaded file entirely, and the real FastAPI
backend does not exist yet (BACKLOG T9.1). So uploading a recording to the web
demo today returns invented numbers with no connection to it. This script runs the
same validated pipeline the WESAD results came from, and needs no server and no API
key — the stress level is decided by the scoring rule, which is deterministic and
offline (decision K16).

WHAT IT DOES NOT DO. It reports a timeline of 60-second windows, not per-question
results. Per-question analysis needs to know when each answer began and ended, which
only the V3 interview flow can record.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_rag.core.types import Modality, Phase  # noqa: E402
from hrv_rag.features.baseline import BaselineProfile, check_baseline  # noqa: E402
from hrv_rag.features.extractor import extract_features  # noqa: E402
from hrv_rag.features.stress_level import classify  # noqa: E402
from hrv_rag.preprocessing.intervals import (IntervalFormatError,  # noqa: E402
                                             check_looks_like_milliseconds,
                                             parse_rr_csv,
                                             rr_series_from_intervals,
                                             split_baseline_and_task)

#: Where the sensor was worn -> which modality that makes it. Kept in the same
#: shape as the frontend's `modalityFor`, because asking "chest or wrist" is a
#: question nobody can answer wrongly, while "ECG or PPG" is one most people can.
WEAR_TO_MODALITY = {"chest": Modality.ECG, "wrist": Modality.PPG}


def describe_recording(rr_ms: np.ndarray) -> None:
    """Print what was actually read, before any interpretation of it."""
    duration_min = float(np.sum(rr_ms)) / 60000.0
    median = float(np.median(rr_ms))
    print(f"  intervals read    : {rr_ms.size}")
    print(f"  duration          : {duration_min:.1f} minutes")
    print(f"  median interval   : {median:.0f} ms  "
          f"({60000.0 / median:.0f} bpm)")


def report(path: Path, wear: str, baseline_minutes: float) -> int:
    modality = WEAR_TO_MODALITY[wear]

    try:
        rr_all = parse_rr_csv(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        print(f"Could not read {path}: {exc}")
        return 1
    except IntervalFormatError as exc:
        print(f"{path.name}: {exc}")
        return 1

    print(f"--- {path.name} ---")

    # Check the unit BEFORE describing the recording. Left until the per-phase
    # step, the summary above the error would report a median of "0.79 ms
    # (75949 bpm)" — nonsense that reads like the script's own confusion rather
    # than a problem with the file.
    try:
        check_looks_like_milliseconds(rr_all)
    except IntervalFormatError as exc:
        print(f"  {exc}")
        return 1

    describe_recording(rr_all)
    print(f"  worn on           : {wear} -> {modality.value}")
    print(f"  baseline claimed  : first {baseline_minutes:g} minutes\n")

    rest_rr, task_rr, _ = split_baseline_and_task(rr_all, baseline_minutes)

    tables, series_by_phase = {}, {}
    for phase, rr in ((Phase.CALIBRATION, rest_rr), (Phase.QUESTION, task_rr)):
        try:
            series = rr_series_from_intervals(rr, modality, path.stem, phase)
            series_by_phase[phase] = series
        except IntervalFormatError as exc:
            label = ("resting period" if phase is Phase.CALIBRATION
                     else "period after the baseline")
            print(f"  {label}: {exc}")
            return 1

        table, seg = extract_features(series)
        print(f"  {phase.value:12s} {series.n_beats:5d} beats, "
              f"outliers {100 * series.outlier_ratio:4.1f}%, {seg.summary()}")
        tables[phase] = table

    if tables[Phase.CALIBRATION].empty:
        print("\n  No usable resting window, so there is no personal reference to\n"
              "  compare against. Reactivity cannot be computed — this is a\n"
              "  limitation of the recording, not a failure of the analysis.")
        return 1
    if tables[Phase.QUESTION].empty:
        print("\n  Nothing usable after the baseline. Either the recording stops\n"
              "  there, or those minutes were too noisy to measure.")
        return 1

    # From the series, not the table: the resting period is sampled every 15
    # seconds rather than every 30, which is what makes a two-minute rest yield
    # enough windows for a stable median.
    baseline = BaselineProfile.from_series(
        path.stem, series_by_phase[Phase.CALIBRATION]
    )
    verdict = check_baseline(baseline)
    print(f"\n  baseline RMSSD    : {baseline.values['rmssd']:.1f} ms "
          f"(relative IQR {verdict.relative_spread:.0%}, "
          f"{verdict.resting_hr_bpm:.0f} bpm at rest)")
    if not verdict.is_acceptable:
        for reason in verdict.reasons:
            print(f"  WARNING: {reason}")
        print("           Every percentage below is measured against this resting\n"
              "           period, so all of them are less certain than they look.\n"
              "           In a live session this is the point to record the quiet\n"
              "           minutes again, before the interview rather than after.")

    print(f"\n  {'minute':>7} {'RMSSD':>8} {'dRMSSD':>9} {'dHR':>8}  "
          f"{'LEVEL':<9} score")
    print("  " + "-" * 58)

    levels: list[str] = []
    for _, row in tables[Phase.QUESTION].iterrows():
        reactivity = baseline.reactivity(
            {c: row[c] for c in baseline.values if c in row}
        )
        verdict = classify(reactivity)
        levels.append(verdict.level.value)

        minute = baseline_minutes + row["start_sec"] / 60.0
        disagree = " (!)" if any("disagree" in e for e in verdict.evidence) else ""
        print(f"  {minute:7.1f} {row['rmssd']:8.1f} "
              f"{reactivity.get('delta_pct_rmssd', float('nan')):8.1f}% "
              f"{reactivity.get('delta_pct_mean_hr', float('nan')):7.1f}%  "
              f"{verdict.level.value:<9} {verdict.points}/4{disagree}")

    counts = pd.Series(levels).value_counts()
    print(f"\n  windows           : " + ", ".join(
        f"{n} {lvl}" for lvl, n in counts.items()))
    print("  (!) marks a window where the two features disagreed: RMSSD rose "
          "while heart rate also rose.")
    print("\n  These are windows of physiological pressure, NOT a diagnosis of\n"
          "  anxiety. Reported against your own resting period, so they say\n"
          "  nothing about how you compare with anyone else.")
    return 0


def main(argv: list[str]) -> int:
    """
    Walk the arguments once, so an option's VALUE is never mistaken for the
    filename. Filtering on a leading "--" would leave "chest" behind as a
    positional, and `--wear chest rekaman.csv` would then try to open "chest".
    """
    wear = "chest"
    baseline_minutes = 4.0
    positional: list[str] = []

    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("--wear", "--baseline"):
            if index + 1 >= len(argv):
                print(f"{token} needs a value")
                return 1
            value = argv[index + 1]
            if token == "--wear":
                if value not in WEAR_TO_MODALITY:
                    print(f"--wear needs one of: {', '.join(WEAR_TO_MODALITY)}")
                    return 1
                wear = value
            else:
                try:
                    baseline_minutes = float(value)
                except ValueError:
                    print(f"--baseline needs a number, got {value!r}")
                    return 1
                if baseline_minutes <= 0:
                    print("--baseline must be greater than zero")
                    return 1
            index += 2
            continue
        if token.startswith("--"):
            print(f"unknown option {token}")
            return 1
        positional.append(token)
        index += 1

    if not positional:
        print(__doc__)
        return 1
    return report(Path(positional[0]), wear, baseline_minutes)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
