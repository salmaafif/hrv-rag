"""
extractor.py — Perakit: RRSeries -> tabel fitur per segmen.

Modul ini tidak menghitung apa-apa sendiri. Tugasnya hanya merangkai
segmentasi, fitur domain waktu, dan fitur domain frekuensi menjadi satu
tabel, lalu melekatkan kolom jejak (subjek, modalitas, fase, mutu sinyal).

Kolom jejak itu wajib (T2.4) karena CLAUDE.md melarang menggabungkan hasil
antar dataset dan antar modalitas ke dalam satu perhitungan metrik. Tanpa
kolom penanda, larangan itu mustahil ditegakkan saat evaluasi.
"""

from __future__ import annotations

import pandas as pd

from ..core.types import RRSeries
from .frequency_domain import frequency_features
from .segmentation import SegmentationResult, segment_rr_series
from .time_domain import time_domain_features

#: Pemetaan nama atribut Python -> nama kolom untuk CSV dan laporan.
#: Kode memakai snake_case sesuai PEP 8; tabel di laporan memakai notasi
#: ilmiah yang dikenali penguji (RMSSD, pNN50, dan seterusnya).
DISPLAY_NAMES: dict[str, str] = {
    "mean_rr": "meanRR",
    "mean_hr": "meanHR",
    "sdnn": "SDNN",
    "rmssd": "RMSSD",
    "pnn50": "pNN50",
    "lf_welch": "LF_welch",
    "hf_welch": "HF_welch",
    "lf_hf_welch": "LF/HF_welch",
    "lf_ls": "LF_ls",
    "hf_ls": "HF_ls",
    "lf_hf_ls": "LF/HF_ls",
}


def extract_features(series: RRSeries) -> tuple[pd.DataFrame, SegmentationResult]:
    """
    Ubah satu `RRSeries` menjadi tabel fitur, satu baris per segmen.

    Dikembalikan juga `SegmentationResult` agar pemanggil bisa melaporkan
    berapa jendela dibuang dan alasannya — informasi mutu ini ikut masuk
    ke prompt supaya LLM dapat menyesuaikan skor keyakinan.
    """
    result = segment_rr_series(series)

    rows = []
    for seg in result.segments:
        row: dict[str, object] = {
            # --- kolom jejak (T2.4) ---
            "subjek": series.subject,
            "modalitas": series.modality.value,
            "fase": series.phase.value,
            "segmen": seg.index,
            "mulai_dtk": round(seg.start_sec, 1),
            "selesai_dtk": round(seg.end_sec, 1),
            "n_denyut": seg.n_beats,
            "outlier_pct": round(seg.outlier_ratio * 100, 2),
        }
        row.update(time_domain_features(seg.rr_ms))
        row.update(frequency_features(seg.rr_ms))
        rows.append(row)

    return pd.DataFrame(rows), result


def to_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ganti nama kolom fitur ke notasi ilmiah, termasuk kolom reaktivitas.

    Dipakai hanya saat menulis CSV atau menampilkan tabel. Di dalam kode,
    nama snake_case tetap dipakai supaya konsisten dengan PEP 8.
    """
    mapping = dict(DISPLAY_NAMES)
    for attr, shown in DISPLAY_NAMES.items():
        mapping[f"delta_pct_{attr}"] = f"delta%_{shown}"
    return df.rename(columns=mapping)
