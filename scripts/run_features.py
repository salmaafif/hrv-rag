"""
run_features.py — Run Stage 2 on the WESAD development subjects.

Produces one CSV of per-segment features with their reactivity, then prints a
summary for a quick sanity check.

Usage:
    python scripts/run_features.py            # 5 development subjects
    python scripts/run_features.py S2
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings        # noqa: E402
from hrv_rag.core.types import Modality, Phase                   # noqa: E402
from hrv_rag.datasets.wesad import WESADLoader                   # noqa: E402
from hrv_rag.features.baseline import BaselineProfile            # noqa: E402
from hrv_rag.features.extractor import (extract_features,        # noqa: E402
                                        to_display_columns)
from hrv_rag.preprocessing.ecg import ECGPreprocessor            # noqa: E402


def process_subject(subject: str) -> pd.DataFrame:
    """One subject: signal -> features -> reactivity against their own baseline."""
    loader = WESADLoader(subject)
    pre = ECGPreprocessor(sampling_rate=loader.sampling_rate(Modality.ECG))

    print(f"\n--- {subject} ---")
    tables, series_by_phase = {}, {}
    for phase in (Phase.CALIBRATION, Phase.QUESTION):
        raw = loader.load_phase_signal(subject, phase, Modality.ECG)
        series = pre.run(raw, subject=subject, phase=phase)
        df, seg_result = extract_features(series)
        tables[phase] = df
        series_by_phase[phase] = series
        print(f"  {phase.value:12s}: {seg_result.summary()}")

    # The baseline is built ONLY from this subject's own calibration phase, and
    # from the SERIES rather than the table above: it needs the finer resting hop,
    # while the table keeps the standard one because its rows are also the
    # low-stress class this system is scored against.
    baseline = BaselineProfile.from_series(subject, series_by_phase[Phase.CALIBRATION])
    print(f"  {baseline.describe()}")

    # Reactivity is computed for every phase, calibration included — those segments
    # should come out near 0%, which makes a useful sanity check.
    combined = pd.concat(tables.values(), ignore_index=True)
    reactivity = pd.DataFrame(
        [baseline.reactivity(row) for row in combined.to_dict("records")]
    )
    return pd.concat([combined, reactivity], axis=1)


def main(subjects: list[str]) -> None:
    if not subjects:
        subjects = list(settings.split.dev_subjects)
        print(f"Development subjects: {', '.join(subjects)}")
        print("(10 test subjects sealed — BACKLOG U4.1)")

    all_rows = [process_subject(s) for s in subjects]
    data = pd.concat(all_rows, ignore_index=True)

    # --- Reactivity summary per phase ---
    # The MEDIAN is used, not the mean. Percentage change is asymmetric: a decrease
    # bottoms out at -100% while an increase is unbounded (observed up to +442% on
    # S10). The mean is therefore dragged upward by the right tail and can invert
    # the conclusion — on this data the mean pNN50 read +61.8% while the median was
    # -61.2%.
    cols = ["delta_pct_rmssd", "delta_pct_pnn50", "delta_pct_hf_welch",
            "delta_pct_lf_hf_welch", "delta_pct_mean_hr"]
    cols = [c for c in cols if c in data.columns]
    print("\n=== Median reactivity per phase (%) ===")
    print(data.groupby("phase")[cols].median().round(1).to_string())

    # --- Response direction per subject ---
    # Checked per person rather than pooled, because a single subject with an
    # inverted pattern would otherwise be hidden inside the aggregate.
    print("\n=== Response direction per subject (median, question phase) ===")
    q = data[data["phase"] == Phase.QUESTION.value]
    per_subject = q.groupby("subject")[cols].median().round(1)
    # Textbook pattern under pressure: RMSSD falls AND heart rate rises.
    per_subject["pattern"] = [
        "as expected" if r["delta_pct_rmssd"] < 0 and r["delta_pct_mean_hr"] > 0
        else "INVERTED" if r["delta_pct_rmssd"] > 0 and r["delta_pct_mean_hr"] > 0
        else "mixed"
        for _, r in per_subject.iterrows()
    ]
    print(per_subject.to_string())

    # --- Comparing the two PSD methods (T2.12) ---
    print("\n=== Welch vs Lomb-Scargle: LF/HF ===")
    both = data[["lf_hf_welch", "lf_hf_ls"]].dropna()
    if not both.empty:
        corr = both["lf_hf_welch"].corr(both["lf_hf_ls"])
        rel = ((both["lf_hf_ls"] - both["lf_hf_welch"]).abs()
               / both["lf_hf_welch"]).median()
        print(f"  Pearson correlation      : {corr:.3f}")
        print(f"  median relative difference: {rel:.1%}")
        print(f"  mean Welch {both['lf_hf_welch'].mean():.2f} | "
              f"mean Lomb-Scargle {both['lf_hf_ls'].mean():.2f}")

    # Only a full development run may claim the development table.
    #
    # The single-subject form is documented at the top of this file, and it used to
    # write to the same path — so `run_features.py S2` quietly replaced the
    # five-subject table with one subject. Nothing downstream noticed: the file is
    # the input to calibrate_rule.py, run_session.py and run_evaluation.py, and
    # calibrate_rule.py printed all five subject names regardless of what it read.
    # A threshold sweep on one subject would have reported macro-F1 0.94 and looked
    # like an improvement on the honest 0.85.
    expected = set(settings.split.dev_subjects)
    if set(data["subject"].unique()) == expected:
        path = OUTPUTS_DIR / "features_wesad_ecg_dev.csv"
    else:
        stem = "_".join(sorted(data["subject"].unique()))
        path = OUTPUTS_DIR / f"features_wesad_ecg_{stem}.csv"
        print(f"\nPartial run ({stem}) — the development table is left untouched.")

    to_display_columns(data).to_csv(path, index=False)
    print(f"\nCSV: {path}")
    print(f"Total segments: {len(data)}")


if __name__ == "__main__":
    main(sys.argv[1:])
