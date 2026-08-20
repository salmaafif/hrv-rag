"""
analyse_baseline_duration.py — how long must the resting period actually be?

    python scripts/analyse_baseline_duration.py

Every percentage in the system is a change relative to the person's own resting
value (Mandatory Rule #2), so the resting period is the denominator under the
whole report. `SessionConfig.calibration_sec` was shortened from 240 to 180 to 120
seconds for the person waiting, and each cut was argued from user comfort — never
from a measurement of what the shortening costs. This script supplies the missing
half of that trade.

THE QUESTION IT ANSWERS. WESAD records roughly twenty minutes of rest per subject.
Treating the median over all of it as the truth, the script asks: had we recorded
only N minutes, how far from that truth could we have landed — purely because of
WHICH N minutes we happened to catch, with nothing about the person changing?

WHAT "RANGE" MEANS, AND DOES NOT. It is the worst case: the highest minus the
lowest baseline obtainable from any contiguous stretch of that length. Because the
stretches overlap heavily they are not independent draws, so this overstates the
error a single recording would typically suffer. The worst case is nevertheless
the right quantity for a protocol decision, because Gate 3 in the acquisition
protocol exists precisely to catch the bad draw rather than the average one.

TWO THINGS IT CANNOT TELL YOU. WESAD's twenty-minute median is itself an estimate,
not ground truth. And WESAD's rest is a seated laboratory baseline recorded before
a stressor — a person at home facing a webcam may settle faster or slower.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from hrv_rag.config.settings import OUTPUTS_DIR, settings          # noqa: E402
from hrv_rag.features.extractor import load_features               # noqa: E402

#: Durations swept, in minutes. Bounded above by WESAD's own resting length.
DURATIONS = (2, 3, 4, 5, 6, 8, 10, 12)

#: Feature the baseline is judged on — the same one the scoring rule keys off.
FEATURE = "rmssd"

#: Sliding step for the candidate stretches, in seconds. Matches the standard
#: segmentation hop so every stretch starts on a real window boundary.
STEP_SEC = 30

#: A running median counts as settled once it moves less than this, this many
#: windows in a row.
STABLE_TOLERANCE = 0.05
STABLE_RUN = 3


def load_resting() -> pd.DataFrame:
    """Every WESAD resting segment, development and sealed subjects alike."""
    frames = []
    for split in ("dev", "holdout"):
        path = OUTPUTS_DIR / f"features_wesad_ecg_{split}.csv"
        if not path.exists():
            raise SystemExit(
                f"{path.name} not found. Run scripts/run_features.py and "
                f"scripts/run_holdout.py first."
            )
        frames.append(load_features(path))
    df = pd.concat(frames, ignore_index=True)
    return df[df.phase == "calibration"].copy()


def range_for(group: pd.DataFrame, duration_sec: int) -> float | None:
    """Worst-case relative spread of the baseline over stretches of one length."""
    group = group.sort_values("start_sec")
    truth = group[FEATURE].median()
    medians = []
    last_start = group.start_sec.max() - duration_sec
    for start in np.arange(group.start_sec.min(), last_start, STEP_SEC):
        window = group[(group.start_sec >= start)
                       & (group.start_sec < start + duration_sec)]
        if len(window) >= 3:
            medians.append(window[FEATURE].median())
    if len(medians) < 2:
        return None
    scaled = np.asarray(medians) / truth
    return float(scaled.max() - scaled.min())


def settling_time(group: pd.DataFrame) -> tuple[float, float]:
    """
    When a running median stops moving, and how right it is at that moment.

    This tests the tempting shortcut — "record until it stabilises" — and finds
    it does not rescue a short rest: stabilising early is not the same as
    stabilising on the correct value.
    """
    group = group.sort_values("start_sec")
    values = group[FEATURE].values
    truth = np.median(values)

    run = 0
    stop = len(values) - 1
    for i in range(3, len(values)):
        previous, current = np.median(values[:i]), np.median(values[:i + 1])
        run = run + 1 if abs(current - previous) / previous < STABLE_TOLERANCE else 0
        if run >= STABLE_RUN:
            stop = i
            break
    return float(group.end_sec.values[stop]), float(np.median(values[:stop + 1]) / truth)


def main() -> int:
    resting = load_resting()
    rule = settings.stress_rule
    moderate = abs(rule.rmssd_moderate_pct)
    high = abs(rule.rmssd_high_pct)

    print("\n=== Seberapa jauh baseline bisa meleset, menurut durasi istirahat ===\n")
    print(f"  Acuan: median {FEATURE.upper()} atas seluruh fase istirahat WESAD")
    print(f"  Ambang aturan: sedang {moderate:.0f}%, tinggi {high:.0f}%\n")
    print(f"  {'durasi':<9}{'rentang median':>16}{'terburuk':>11}"
          f"{'>' + f'{moderate:.0f}%':>8}{'>' + f'{high:.0f}%':>7}")
    print("  " + "-" * 51)

    current = settings.session.calibration_sec / 60
    for minutes in DURATIONS:
        spreads = [r for r in (range_for(g, minutes * 60)
                               for _, g in resting.groupby("subject")) if r is not None]
        if not spreads:
            continue
        spreads = np.asarray(spreads)
        mark = "  <- sekarang" if abs(minutes - current) < 0.01 else ""
        print(f"  {str(minutes) + ' mnt':<9}{np.median(spreads):>15.0%}"
              f"{spreads.max():>11.0%}"
              f"{(spreads > moderate / 100).sum():>6}/{len(spreads)}"
              f"{(spreads > high / 100).sum():>5}/{len(spreads)}{mark}")

    print("\n  \"rentang\" = baseline tertinggi dikurangi terendah yang bisa didapat")
    print("  dari potongan waktu berbeda pada fase istirahat yang SAMA. Kasus")
    print("  terburuk, bukan galat tipikal — lihat docstring berkas ini.\n")

    print("=== Apakah \"rekam sampai stabil\" bisa menyelamatkan durasi pendek? ===\n")
    times, accuracies = [], []
    for _, group in resting.groupby("subject"):
        stop_sec, ratio = settling_time(group)
        times.append(stop_sec)
        accuracies.append(abs(ratio - 1))
    times, accuracies = np.asarray(times), np.asarray(accuracies)

    print(f"  Waktu berhenti : median {np.median(times) / 60:.1f} mnt, "
          f"terburuk {times.max() / 60:.1f} mnt")
    for minutes in (2, 3, 4):
        print(f"  Selesai <= {minutes} mnt : {(times <= minutes * 60).sum()}/{len(times)}")
    print(f"\n  Ketepatan pada titik berhenti: galat median "
          f"{np.median(accuracies):.0%}, terburuk {accuracies.max():.0%}")
    print(f"  Masih meleset >{moderate:.0f}%: "
          f"{(accuracies > moderate / 100).sum()}/{len(accuracies)} subjek")
    print("\n  Berhenti lebih awal bukan berarti berhenti pada nilai yang benar.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
