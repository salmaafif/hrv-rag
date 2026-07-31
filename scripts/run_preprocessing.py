"""
run_preprocessing.py — Verifikasi Tahap 1: sinyal WESAD -> deret RR bersih.

Cara pakai:
    python scripts/run_preprocessing.py            # subjek pengembangan
    python scripts/run_preprocessing.py S2 S3      # subjek tertentu
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agar paket di src/ bisa di-import tanpa perlu `pip install -e .` dulu.
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

        # Peringatan bila deretnya terlalu kotor untuk dipercaya.
        if series.outlier_ratio > settings.quality.max_outlier_ratio:
            print(f"      PERINGATAN: outlier melebihi "
                  f"{settings.quality.max_outlier_ratio:.0%} — "
                  f"banyak segmen akan dibuang di Tahap 2")


def main(subjects: list[str]) -> None:
    if not subjects:
        subjects = list(settings.split.dev_subjects)
        print(f"Subjek pengembangan: {', '.join(subjects)}")
        print("(subjek uji sengaja tidak disentuh — lihat BACKLOG U4.1)")

    for subject in subjects:
        process_subject(subject)


if __name__ == "__main__":
    main(sys.argv[1:])
