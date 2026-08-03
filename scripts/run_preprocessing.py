"""
run_preprocessing.py — Stage 1 check: WESAD signal -> clean RR series.

Usage:
    python scripts/run_preprocessing.py            # development subjects
    python scripts/run_preprocessing.py S2 S3      # specific subjects
"""

from __future__ import annotations

import sys
from pathlib import Path

# Makes the package under src/ importable without needing `pip install -e .` first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_rag.config.settings import settings                    # noqa: E402
from hrv_rag.core.types import Modality, Phase                  # noqa: E402
from hrv_rag.datasets.wesad import WESADLoader                  # noqa: E402
from hrv_rag.preprocessing.ecg import ECGPreprocessor           # noqa: E402


def process_subject(subject: str) -> None:
    loader = WESADLoader(subject)
    pre = ECGPreprocessor(sampling_rate=loader.sampling_rate(Modality.ECG))

    print(f"\n--- {subject} ---")
    for phase in (Phase.CALIBRATION, Phase.QUESTION):
        raw = loader.load_phase_signal(subject, phase, Modality.ECG)
        series = pre.run(raw, subject=subject, phase=phase)
        print("  " + series.describe())

        # Warn when the series is too dirty to be trusted.
        if series.outlier_ratio > settings.quality.max_outlier_ratio:
            print(f"      WARNING: outliers exceed "
                  f"{settings.quality.max_outlier_ratio:.0%} — "
                  f"many segments will be dropped in Stage 2")


def main(subjects: list[str]) -> None:
    if not subjects:
        subjects = list(settings.split.dev_subjects)
        print(f"Development subjects: {', '.join(subjects)}")
        print("(test subjects deliberately untouched — see BACKLOG U4.1)")

    for subject in subjects:
        process_subject(subject)


if __name__ == "__main__":
    main(sys.argv[1:])
