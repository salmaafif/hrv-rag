"""
run_assessment.py — Stage 4 demonstration on real WESAD segments.

Picks a few segments from the feature CSV, runs the full RAG chain, and prints both
output layers plus the guard results.

Usage:
    python scripts/run_assessment.py                # a few contrasting segments
    python scripts/run_assessment.py --consistency  # same segment 3x (T5.4)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                             # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR                 # noqa: E402
from hrv_rag.core.schemas import (AssessmentInput,              # noqa: E402
                                  SignalQuality)
from hrv_rag.core.types import Modality, Phase                  # noqa: E402
from hrv_rag.features.extractor import load_features            # noqa: E402
from hrv_rag.rag.pipeline import AssessmentPipeline             # noqa: E402
from hrv_rag.rag.query_builder import build_query               # noqa: E402

FEATURES_CSV = OUTPUTS_DIR / "features_wesad_ecg_dev.csv"

#: Feature columns expected by the assessment input, in snake_case.
_FEATURES = ("mean_rr", "mean_hr", "sdnn", "rmssd", "pnn50",
             "lf_welch", "hf_welch", "lf_hf_welch")


def row_to_input(row: pd.Series) -> AssessmentInput:
    """
    Build an AssessmentInput from one row of the feature table.

    The row must already carry snake_case names — read the CSV with
    `features.extractor.load_features` rather than `pd.read_csv`.
    """
    features = {f: float(row[f]) for f in _FEATURES
                if f in row and pd.notna(row[f])}
    reactivity = {f"delta_pct_{f}": float(row[f"delta_pct_{f}"])
                  for f in _FEATURES
                  if f"delta_pct_{f}" in row and pd.notna(row[f"delta_pct_{f}"])}

    return AssessmentInput(
        # Subject IDs are already anonymous in WESAD; no personal data is ever sent.
        session_id=str(row["subject"]),
        modality=Modality(row["modality"]),
        device="RespiBAN chest strap, 700 Hz",
        phase=Phase(row["phase"]),
        segment_index=int(row["segment"]),
        features=features,
        reactivity=reactivity,
        signal_quality=SignalQuality(
            outlier_pct=float(row["outlier_pct"]),
            is_acceptable=float(row["outlier_pct"]) <= 10.0,
        ),
        # WESAD has no gap phase, so recovery genuinely cannot be computed here.
        recovery_pct=None,
        recovery_note="WESAD provides no rest phase after TSST",
    )


def show(assessment, data) -> None:
    r = assessment.response
    print(f"\n{'=' * 72}")
    print(f"{data.session_id} segment {data.segment_index} ({data.phase.value})")
    print(f"QUERY: {build_query(data)}")
    print(f"RETRIEVED: {', '.join(assessment.retrieved_ids)}")
    print(f"\n  stress_level : {r.stress_level.value}   confidence: {r.confidence}")
    print(f"  reasoning    : {r.reasoning}")
    if r.uncertainty_notes:
        print(f"  uncertainty  : {r.uncertainty_notes}")
    print(f"  references   : {', '.join(r.references)}")
    print(f"\n  --- user layer (Indonesian) ---")
    for k, v in assessment.user_view().items():
        print(f"  {k}: {v}")
    print(f"\n  guards: trustworthy={assessment.is_trustworthy}"
          f" invented={assessment.invented_numbers or 'none'}"
          f" unknown_refs={assessment.unknown_references or 'none'}")


def main() -> None:
    if not FEATURES_CSV.exists():
        sys.exit(f"{FEATURES_CSV} not found. Run scripts/run_features.py first.")
    data = load_features(FEATURES_CSV)
    pipeline = AssessmentPipeline()

    # Three contrasting cases: a calm calibration segment, a textbook stress
    # response (S14), and one of the inverted subjects (S6).
    picks = [
        data[(data.subject == "S2") & (data.phase == "calibration")].iloc[5],
        data[(data.subject == "S14") & (data.phase == "question")].iloc[5],
        data[(data.subject == "S6") & (data.phase == "question")].iloc[5],
    ]

    if "--consistency" in sys.argv:
        target = row_to_input(picks[1])
        print("Running the same segment 3 times (T5.4)...")
        for i, a in enumerate(pipeline.assess_repeatedly(target, n_runs=3), 1):
            print(f"  run {i}: level={a.response.stress_level.value} "
                  f"confidence={a.response.confidence} "
                  f"refs={','.join(a.response.references)}")
        return

    for row in picks:
        data_in = row_to_input(row)
        show(pipeline.assess(data_in), data_in)


if __name__ == "__main__":
    main()
