"""
run_ppg.py — Stage 6: PPG branch and the paired modality comparison.

Processes WESAD wrist BVP through the PPG branch, then compares the resulting
features against the ECG features from the SAME subjects and the SAME segments.

No API calls are involved, so this runs regardless of the Gemini quota.

Usage:
    python scripts/run_ppg.py              # development subjects
    python scripts/run_ppg.py S2 S6
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings        # noqa: E402
from hrv_rag.core.types import Modality, Phase                   # noqa: E402
from hrv_rag.datasets.wesad import WESADLoader                   # noqa: E402
from hrv_rag.evaluation.modality import compare_feature          # noqa: E402
from hrv_rag.features.baseline import BaselineProfile            # noqa: E402
from hrv_rag.features.extractor import extract_features          # noqa: E402
from hrv_rag.preprocessing.ecg import ECGPreprocessor            # noqa: E402
from hrv_rag.preprocessing.ppg import PPGPreprocessor            # noqa: E402

#: Features compared between modalities. RMSSD and heart rate lead because the
#: knowledge base identifies them as the most dependable on 60-second segments.
COMPARED = ["rmssd", "mean_hr", "sdnn", "pnn50", "hf_welch", "lf_hf_welch"]

#: Relaxed ectopic threshold used FOR THE COMPARISON STUDY ONLY.
#:
#: The production gate of 20% (set for ECG) rejects roughly 98% of WESAD wrist-BVP
#: segments. That rejection is correct behaviour — the data really is that noisy —
#: but it leaves too few paired segments to compare anything.
#:
#: This study therefore deliberately admits worse data so that agreement can be
#: measured at all. The result is a CEILING: whatever agreement is found here is the
#: best case, and the production pipeline sees less. Loosening the gate in
#: production would merely feed noise to the assessment.
STUDY_MAX_REL_DIFF = 0.50


def process_modality(subject: str, modality: Modality) -> pd.DataFrame:
    """Run one subject through one modality branch and return its feature table."""
    loader = WESADLoader(subject)
    fs = loader.sampling_rate(modality)

    tables, series_by_phase = {}, {}
    for phase in (Phase.CALIBRATION, Phase.QUESTION):
        raw = loader.load_phase_signal(subject, phase, modality)

        if modality is Modality.ECG:
            pre = ECGPreprocessor(sampling_rate=fs)
        else:
            # Wrist acceleration lets the PPG branch reject beats recorded while
            # the arm was moving — the dominant artefact source for optical sensors.
            acc = loader.load_phase_accelerometer(subject, phase, target_fs=fs)
            pre = PPGPreprocessor(
                sampling_rate=fs, accelerometer=acc,
                quality=replace(settings.quality,
                                max_rel_diff=STUDY_MAX_REL_DIFF),
            )

        series = pre.run(raw, subject=subject, phase=phase)
        df, seg = extract_features(series)
        tables[phase] = df
        series_by_phase[phase] = series
        print(f"    {modality.value:<4} {phase.value:<12} "
              f"{series.n_beats:5d} beats, outliers {series.outlier_ratio:5.1%}, "
              f"{seg.summary()}")

    combined = pd.concat(tables.values(), ignore_index=True)
    if tables[Phase.CALIBRATION].empty:
        # Without calibration segments there is no personal baseline, so reactivity
        # cannot be computed. The raw features are still returned for comparison.
        print(f"    (no calibration segment survived — reactivity unavailable)")
        return combined

    # Finer resting hop, matching how the development and holdout tables are
    # built — otherwise the ECG and PPG baselines would not be comparable.
    baseline = BaselineProfile.from_series(
        subject, series_by_phase[Phase.CALIBRATION]
    )
    reactivity = pd.DataFrame(
        [baseline.reactivity(r) for r in combined.to_dict("records")]
    )
    return pd.concat([combined, reactivity], axis=1)


def main(subjects: list[str]) -> None:
    if not subjects:
        subjects = list(settings.split.dev_subjects)
        print(f"Development subjects: {', '.join(subjects)}\n")

    all_ecg, all_ppg = [], []
    for subject in subjects:
        print(f"--- {subject} ---")
        ecg = process_modality(subject, Modality.ECG)
        ppg = process_modality(subject, Modality.PPG)

        # Pair segments by phase and START TIME. "Paired" has to mean the same 60
        # seconds of wall-clock time, or the comparison measures nothing.
        #
        # This used to join on the `segment` column, back when that column held a
        # segment's rank among the ones that survived the quality gates. PPG loses
        # far more segments than ECG, so the two columns counted differently and the
        # join silently lined up windows recorded minutes apart: of 91 supposedly
        # paired segments only 2 covered the same time, the median offset was 210
        # seconds, and 74 pairs did not overlap at all. Every ICC and Bland-Altman
        # figure in T6.4 came out of that.
        #
        # `segment` is now a true window number and would join correctly, but
        # `start_sec` states the intent outright and cannot drift again.
        merged = ecg.merge(ppg, on=["subject", "phase", "start_sec"],
                           suffixes=("_ecg", "_ppg"))

        # A pairing this important should not be taken on trust.
        if len(merged) and not (merged["end_sec_ecg"] == merged["end_sec_ppg"]).all():
            raise RuntimeError(
                f"{subject}: paired segments disagree on end time — "
                "the two branches are not describing the same windows"
            )
        print(f"    paired segments: {len(merged)}"
              f"  (ECG had {len(ecg)}, PPG had {len(ppg)})\n")
        all_ecg.append(ecg)
        all_ppg.append(merged)

    paired = pd.concat(all_ppg, ignore_index=True)

    print("=" * 78)
    print(f"PAIRED MODALITY AGREEMENT — {len(paired)} segments, "
          f"{len(subjects)} subjects (T6.4)")
    print("=" * 78)
    print("  ICC(2,1) absolute agreement; bias = PPG minus ECG; "
          "slope = proportional bias\n")

    for feature in COMPARED:
        col_ecg, col_ppg = f"{feature}_ecg", f"{feature}_ppg"
        if col_ecg not in paired or col_ppg not in paired:
            continue
        print(compare_feature(paired[col_ecg], paired[col_ppg], feature).summary())

    # Agreement on reactivity matters more than on the raw values, because
    # reactivity is what the assessment actually consumes.
    print("\n  reactivity (percent change against each subject's own baseline):")
    for feature in COMPARED:
        col_ecg, col_ppg = f"delta_pct_{feature}_ecg", f"delta_pct_{feature}_ppg"
        if col_ecg not in paired or col_ppg not in paired:
            continue
        print(compare_feature(paired[col_ecg], paired[col_ppg],
                              f"d%{feature}").summary())

    # Split by phase: the knowledge base predicts agreement degrades under stress.
    print("\n  RMSSD agreement per phase:")
    for phase, rows in paired.groupby("phase"):
        print(f"    [{phase}]")
        print("    " + compare_feature(rows["rmssd_ecg"], rows["rmssd_ppg"],
                                       "rmssd").summary())

    out = OUTPUTS_DIR / "modality_paired_wesad_dev.csv"
    paired.to_csv(out, index=False)
    print(f"\nPaired table written to: {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
