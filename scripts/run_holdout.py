"""
run_holdout.py — The headline evaluation, on the sealed test subjects.

Runs the FROZEN stress rule against the ten WESAD subjects that were kept out of
development. These figures are the honest ones: nothing about the rule was chosen
by looking at these people.

Run this ONCE, after the thresholds are frozen. If a threshold is later changed and
this is run again, the result is no longer a clean holdout — it becomes another
round of tuning, and must be reported as such.

No API calls; the rule assigns the label.

Usage:
    python scripts/run_holdout.py
    python scripts/run_holdout.py --recompute   # rebuild features first
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings        # noqa: E402
from hrv_rag.core.types import Modality, Phase                   # noqa: E402
from hrv_rag.datasets.wesad import WESADLoader                   # noqa: E402
from hrv_rag.evaluation.labels import (EvaluationRecord,         # noqa: E402
                                       TrueLabel, true_label)
from hrv_rag.evaluation.metrics import (evaluate_classification,  # noqa: E402
                                        evaluate_per_subject)
from hrv_rag.features.baseline import BaselineProfile            # noqa: E402
from hrv_rag.features.extractor import (extract_features,        # noqa: E402
                                        load_features,
                                        to_display_columns)
from hrv_rag.features.stress_level import classify               # noqa: E402
from hrv_rag.preprocessing.ecg import ECGPreprocessor            # noqa: E402

HOLDOUT_CSV = OUTPUTS_DIR / "features_wesad_ecg_holdout.csv"


def build_features(subjects: list[str]) -> pd.DataFrame:
    """Run the full signal pipeline for the held-out subjects."""
    frames = []
    for subject in subjects:
        loader = WESADLoader(subject)
        pre = ECGPreprocessor(sampling_rate=loader.sampling_rate(Modality.ECG))

        tables, series_by_phase = {}, {}
        for phase in (Phase.CALIBRATION, Phase.QUESTION):
            raw = loader.load_phase_signal(subject, phase, Modality.ECG)
            series = pre.run(raw, subject=subject, phase=phase)
            df, seg = extract_features(series)
            tables[phase] = df
            series_by_phase[phase] = series
            print(f"  {subject} {phase.value:<12} {seg.summary()}")

        if tables[Phase.CALIBRATION].empty:
            print(f"  {subject}: no calibration segment — skipped")
            continue

        # Built from the series, with the finer resting hop — the SAME way the
        # development subjects are processed. A sealed test set measured by a
        # different procedure than the one it is meant to validate would not be a
        # test of anything.
        baseline = BaselineProfile.from_series(
            subject, series_by_phase[Phase.CALIBRATION]
        )
        combined = pd.concat(tables.values(), ignore_index=True)
        reactivity = pd.DataFrame(
            [baseline.reactivity(r) for r in combined.to_dict("records")]
        )
        frames.append(pd.concat([combined, reactivity], axis=1))

    return pd.concat(frames, ignore_index=True)


def to_binary(level) -> TrueLabel:
    """WESAD has no middle condition, so anything above low is stressed."""
    from hrv_rag.core.schemas import StressLevel
    return TrueLabel.LOW if level is StressLevel.LOW else TrueLabel.HIGH


def main() -> None:
    subjects = list(settings.split.test_subjects)
    cfg = settings.stress_rule

    print("=" * 70)
    print("HOLDOUT EVALUATION — sealed test subjects")
    print("=" * 70)
    print(f"  subjects  : {', '.join(subjects)}")
    print(f"  thresholds: RMSSD {cfg.rmssd_moderate_pct:.0f}/"
          f"{cfg.rmssd_high_pct:.0f}, HR {cfg.hr_moderate_pct:.0f}/"
          f"{cfg.hr_high_pct:.0f}  (frozen)")
    print("  These subjects were not looked at while the rule was tuned.\n")

    if HOLDOUT_CSV.exists() and "--recompute" not in sys.argv:
        data = load_features(HOLDOUT_CSV)
        print(f"Reusing {HOLDOUT_CSV.name} ({len(data)} segments)\n")
    else:
        print("Building features...\n")
        data = build_features(subjects)
        to_display_columns(data).to_csv(HOLDOUT_CSV, index=False)
        print(f"\nWritten to {HOLDOUT_CSV}\n")

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
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(report.summary())

    print("\n  accuracy per subject:")
    for subject, acc in evaluate_per_subject(records).items():
        print(f"    {subject:<5} {acc:.3f}")

    # The three-level distribution is worth seeing even though WESAD cannot score
    # it: the moderate/high split is where the uncalibrated thresholds live.
    counts = pd.Series([r.raw_level for r in records]).value_counts()
    print("\n  three-level output (WESAD cannot score this split):")
    for level, n in counts.items():
        print(f"    {level:<10} {n:4d}  ({n / len(records):.1%})")

    print("\n  Reminder: segments overlap by 30 s, so they are not independent "
          "observations.")


if __name__ == "__main__":
    main()
