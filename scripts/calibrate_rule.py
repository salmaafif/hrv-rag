"""
calibrate_rule.py — Tune the stress-rule thresholds, on development subjects only.

The rule assigns the label the user sees, so its thresholds matter more than any
other number in the system. They were first set by reasoning; this script sets them
from data.

**Only the five development subjects are used.** The ten test subjects stay sealed.
Tuning against the test set would let the rule memorise it, and the headline figures
would then describe how well the thresholds were fitted rather than how well the
system works.

Runs entirely offline — no API calls.

Usage:
    python scripts/calibrate_rule.py            # sweep and recommend
    python scripts/calibrate_rule.py --detail   # full grid
"""

from __future__ import annotations

import sys
from dataclasses import replace
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings        # noqa: E402
from hrv_rag.core.schemas import StressLevel                     # noqa: E402
from hrv_rag.evaluation.labels import (EvaluationRecord,         # noqa: E402
                                       TrueLabel, true_label)
from hrv_rag.evaluation.metrics import evaluate_classification   # noqa: E402
from hrv_rag.features.extractor import load_features             # noqa: E402
from hrv_rag.features.stress_level import classify               # noqa: E402

FEATURES_CSV = OUTPUTS_DIR / "features_wesad_ecg_dev.csv"

#: Candidate thresholds. Kept deliberately coarse: a fine grid over 293 segments
#: would start fitting the noise, and every extra option is another chance to pick a
#: value that happens to suit these five people rather than people in general.
RMSSD_MODERATE = [-10.0, -15.0, -20.0]
RMSSD_HIGH = [-25.0, -30.0, -40.0]
HR_MODERATE = [3.0, 5.0, 8.0]
HR_HIGH = [10.0, 15.0, 20.0]


def to_binary(level: StressLevel) -> TrueLabel:
    """
    Fold the three-level output onto WESAD's binary ground truth.

    WESAD offers no middle condition — a subject is either at rest or undergoing
    TSST — so anything above "low" belongs on the stressed side.
    """
    return TrueLabel.LOW if level is StressLevel.LOW else TrueLabel.HIGH


def score_thresholds(data: pd.DataFrame, cfg) -> tuple[float, float, float]:
    """Return (macro-F1, kappa, accuracy) for one threshold combination."""
    records = []
    for _, row in data.iterrows():
        truth = true_label(row["phase"])
        if truth is None:
            continue
        reactivity = {c: row[c] for c in row.index if c.startswith("delta_pct_")}
        verdict = classify(reactivity, cfg)
        records.append(EvaluationRecord(
            subject=str(row["subject"]), phase=str(row["phase"]),
            segment=int(row["segment"]), modality=str(row["modality"]),
            truth=truth, predicted=to_binary(verdict.level),
            raw_level=verdict.level.value, confidence=1.0,
            references=[], retrieved_ids=[], reasoning="", is_trustworthy=True,
        ))
    report = evaluate_classification(records)
    return report.macro_f1, report.kappa, report.accuracy


def main() -> None:
    if not FEATURES_CSV.exists():
        sys.exit(f"{FEATURES_CSV} not found. Run scripts/run_features.py first.")

    data = load_features(FEATURES_CSV)
    dev = list(settings.split.dev_subjects)
    data = data[data["subject"].isin(dev)]

    # Report who is actually in the table, not who was supposed to be. Printing the
    # configured list meant the header claimed five subjects whatever the CSV held,
    # so a table that had been overwritten by a single-subject run still announced
    # "S2, S6, S10, S14, S17" — and the inflated macro-F1 underneath it looked
    # trustworthy. Thresholds get frozen from this output and carried into the
    # thesis, so it has to describe the data it read.
    present = sorted(data["subject"].unique(), key=lambda s: dev.index(s))
    missing = [s for s in dev if s not in present]

    print("Calibrating the stress rule on DEVELOPMENT subjects only.")
    print(f"  subjects : {', '.join(present)}")
    print(f"  segments : {len(data)}")
    print(f"  test subjects ({len(settings.split.test_subjects)}) remain sealed.")
    if missing:
        sys.exit(
            f"\n  ABORTED: {', '.join(missing)} missing from {FEATURES_CSV.name}.\n"
            f"  Calibrating on a subset would freeze thresholds fitted to fewer\n"
            f"  people than the protocol specifies. Rerun scripts/run_features.py."
        )
    print()

    base = settings.stress_rule
    results = []
    for rm, rh, hm, hh in product(RMSSD_MODERATE, RMSSD_HIGH,
                                  HR_MODERATE, HR_HIGH):
        if rh >= rm:                       # "high" must be a bigger drop
            continue
        if hh <= hm:                       # "high" must be a bigger rise
            continue
        cfg = replace(base, rmssd_moderate_pct=rm, rmssd_high_pct=rh,
                      hr_moderate_pct=hm, hr_high_pct=hh)
        f1, kappa, acc = score_thresholds(data, cfg)
        results.append((f1, kappa, acc, rm, rh, hm, hh))

    results.sort(reverse=True)

    if "--detail" in sys.argv:
        print(f"{'macroF1':>8} {'kappa':>7} {'acc':>7}   "
              f"{'RMSSD mod/high':>16}  {'HR mod/high':>12}")
        print("-" * 60)
        for f1, kappa, acc, rm, rh, hm, hh in results:
            print(f"{f1:8.3f} {kappa:7.3f} {acc:7.3f}   "
                  f"{rm:7.0f} /{rh:7.0f}  {hm:5.0f} /{hh:5.0f}")
        print()

    print(f"Top 5 of {len(results)} combinations tried:\n")
    print(f"{'rank':>4} {'macroF1':>8} {'kappa':>7} {'acc':>7}   "
          f"{'RMSSD mod/high':>16}  {'HR mod/high':>12}")
    print("-" * 66)
    for i, (f1, kappa, acc, rm, rh, hm, hh) in enumerate(results[:5], 1):
        print(f"{i:>4} {f1:8.3f} {kappa:7.3f} {acc:7.3f}   "
              f"{rm:7.0f} /{rh:7.0f}  {hm:5.0f} /{hh:5.0f}")

    current = score_thresholds(data, base)
    print(f"\nCurrent settings  macro-F1 {current[0]:.3f}  "
          f"kappa {current[1]:.3f}  accuracy {current[2]:.3f}")
    print(f"  RMSSD {base.rmssd_moderate_pct:.0f}/{base.rmssd_high_pct:.0f}, "
          f"HR {base.hr_moderate_pct:.0f}/{base.hr_high_pct:.0f}")

    best = results[0]
    print(f"\nBest on development  macro-F1 {best[0]:.3f}  kappa {best[1]:.3f}")
    print(f"  RMSSD {best[3]:.0f}/{best[4]:.0f}, HR {best[5]:.0f}/{best[6]:.0f}")

    gain = best[0] - current[0]
    if gain < 0.01:
        print("\nThe gain over the current settings is under 0.01 — not worth "
              "changing. A difference that small is noise on five subjects, and "
              "chasing it is how thresholds end up fitted to individuals.")
    else:
        print(f"\nGain of {gain:+.3f} macro-F1. Worth adopting, but note that the "
              f"best cell of a grid is optimistic by construction: it was chosen "
              f"BECAUSE it scored highest here. The sealed test subjects are what "
              f"will show the honest figure.")


if __name__ == "__main__":
    main()
