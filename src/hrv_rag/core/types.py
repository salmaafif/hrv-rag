"""
types.py — Objek domain yang dipakai lintas modul.

Kenapa dataclass, bukan dict? Karena dict tidak memaksa apa pun: salah ketik
nama kunci baru ketahuan saat program jalan. Dataclass mendokumentasikan
bentuk data secara eksplisit — penting untuk kode yang harus dijelaskan
baris per baris saat sidang.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class Modality(str, Enum):
    """
    Modalitas sumber data.

    Ikut dibawa sampai ke prompt LLM (Aturan Wajib #5): ECG adalah acuan,
    PPG divalidasi terhadapnya dan lebih rentan artefak gerakan, sehingga
    skor keyakinan perlu disesuaikan.
    """

    ECG = "ECG"
    PPG = "PPG"


class Phase(str, Enum):
    """
    Fase dalam satu sesi.

    Saat validasi, fase diisi dari label dataset (WESAD label 1 -> CALIBRATION,
    label 2 -> QUESTION). Saat produksi, diisi dari linimasa sesi nyata.
    Skemanya sengaja sama agar kode RAG dan validasi tidak perlu bercabang.
    """

    ADAPTATION = "adaptasi"
    CALIBRATION = "kalibrasi"     # -> baseline personal
    BRIEFING = "pengarahan"       # -> antisipasi tingkat sesi
    QUESTION = "pertanyaan"       # -> reaktivitas
    RECOVERY = "jeda"             # -> pemulihan


@dataclass(frozen=True)
class QualityReport:
    """Hasil pemeriksaan kualitas sinyal mentah, sebelum difilter."""

    clipping_ratio: float          # proporsi sampel menempel di nilai ekstrem
    flatline_ratio: float          # proporsi durasi sinyal datar
    is_acceptable: bool            # lolos seluruh ambang?
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Ringkasan sebaris untuk dicetak / dimasukkan ke prompt."""
        status = "baik" if self.is_acceptable else "diragukan"
        return (f"kualitas {status} "
                f"(clipping {self.clipping_ratio:.1%}, "
                f"flat-line {self.flatline_ratio:.1%})")


@dataclass
class RRSeries:
    """
    Deret interval antar denyut — keluaran baku SEMUA cabang pra-pemrosesan.

    Inilah titik temu kedua modalitas: ECG menghasilkannya dari puncak R,
    PPG dari puncak sistolik. Setelah tahap ini, kode sesudahnya (fitur, RAG,
    validasi) tidak perlu lagi tahu asal sinyalnya — kecuali lewat atribut
    `modality` yang sengaja dibawa terus.
    """

    rr_ms: np.ndarray              # interval, milidetik
    t_sec: np.ndarray              # waktu tiap interval, detik
    modality: Modality
    subject: str
    phase: Phase
    quality: QualityReport
    is_outlier: np.ndarray         # penanda per denyut hasil koreksi ektopik

    def __post_init__(self) -> None:
        # Panjang ketiga array harus sama; kalau tidak, ada bug di hulu dan
        # lebih baik ketahuan sekarang daripada muncul sebagai fitur yang aneh.
        n = len(self.rr_ms)
        if not (len(self.t_sec) == len(self.is_outlier) == n):
            raise ValueError(
                f"Panjang array tidak konsisten: rr_ms={n}, "
                f"t_sec={len(self.t_sec)}, is_outlier={len(self.is_outlier)}"
            )

    @property
    def n_beats(self) -> int:
        return len(self.rr_ms)

    @property
    def duration_sec(self) -> float:
        return float(self.t_sec[-1] - self.t_sec[0]) if self.n_beats else 0.0

    @property
    def outlier_ratio(self) -> float:
        """Proporsi denyut yang ditandai artefak — ukuran kualitas deret."""
        return float(self.is_outlier.mean()) if self.n_beats else 1.0

    def describe(self) -> str:
        return (f"{self.subject}/{self.phase.value} [{self.modality.value}]: "
                f"{self.n_beats} denyut, {self.duration_sec:.0f} dtk, "
                f"outlier {self.outlier_ratio:.1%}, {self.quality.summary()}")
