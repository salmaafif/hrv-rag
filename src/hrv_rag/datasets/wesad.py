"""
wesad.py — Pemuat dataset WESAD.

Peran WESAD di TA ini (CLAUDE.md): jangkar utama. TSST adalah stresor
sosial-evaluatif yang paling mirip wawancara kerja, dan WESAD satu-satunya
dataset yang menyediakan ECG dan PPG dari SUBJEK YANG SAMA — dasar
perbandingan modalitas berpasangan (ICC, Bland-Altman) di Tahap 6.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from ..config.settings import DATA_RAW, WESAD_FALLBACK
from ..core.types import Modality, Phase
from .base import BaseDatasetLoader


class WESADLoader(BaseDatasetLoader):
    """
    Pemuat satu subjek WESAD.

    Pemetaan label -> fase:
        label 1 (baseline) -> Phase.CALIBRATION  -> jadi baseline personal
        label 2 (TSST)     -> Phase.QUESTION     -> jadi kondisi tertekan
        label 3 (amusement)-> DIKECUALIKAN

    Amusement dikecualikan karena itu arousal POSITIF, bukan tekanan.
    Memasukkannya akan mencampur dua hal berbeda ke dalam satu skala dan
    membuat label "tinggi" kehilangan makna. (Keputusan K7: tidak dipakai
    sama sekali, termasuk sebagai kontrol negatif.)
    """

    name = "WESAD"

    # Kode label mentah di berkas .pkl
    _LABEL_BASELINE = 1
    _LABEL_STRESS = 2

    _PHASE_TO_LABEL = {
        Phase.CALIBRATION: _LABEL_BASELINE,
        Phase.QUESTION: _LABEL_STRESS,
    }

    # Frekuensi sampling menurut spesifikasi WESAD.
    _FS = {
        Modality.ECG: 700,   # RespiBAN, sabuk dada
        Modality.PPG: 64,    # Empatica E4, pergelangan (kanal BVP)
    }

    _SIGNAL_KEY = {
        Modality.ECG: ("chest", "ECG"),
        Modality.PPG: ("wrist", "BVP"),
    }

    def __init__(self, subject: str) -> None:
        self.subject = subject
        self._path = self._locate(subject)
        self._data: dict | None = None       # dimuat malas (lazy)

    # ------------------------------------------------------------- lokasi
    @staticmethod
    def _locate(subject: str) -> Path:
        """
        Cari berkas SX.pkl. Urutan: data/raw dalam repo dulu, baru lokasi
        cadangan di Documents/WESAD.
        """
        candidates = [
            DATA_RAW / "wesad" / subject / f"{subject}.pkl",
            DATA_RAW / "wesad" / f"{subject}.pkl",
            WESAD_FALLBACK / subject / f"{subject}.pkl",
        ]
        for path in candidates:
            if path.exists():
                return path
        raise FileNotFoundError(
            f"Berkas {subject}.pkl tidak ditemukan. Dicari di:\n  "
            + "\n  ".join(str(c) for c in candidates)
        )

    # -------------------------------------------------------------- muat
    @property
    def data(self) -> dict:
        """
        Isi berkas .pkl, dimuat sekali lalu disimpan (lazy loading).

        Satu berkas WESAD berukuran ratusan MB, jadi jangan dimuat ulang
        tiap kali sinyal diminta.

        encoding='latin1' WAJIB: berkas ini di-pickle dengan Python 2.
        """
        if self._data is None:
            with open(self._path, "rb") as f:
                self._data = pickle.load(f, encoding="latin1")
        return self._data

    # ------------------------------------------------------- kontrak base
    @property
    def subjects(self) -> tuple[str, ...]:
        """Seluruh subjek WESAD. Perhatikan: S1 dan S12 memang tidak ada."""
        return tuple(f"S{i}" for i in range(2, 18) if i != 12)

    @property
    def available_modalities(self) -> tuple[Modality, ...]:
        return (Modality.ECG, Modality.PPG)

    def sampling_rate(self, modality: Modality) -> int:
        return self._FS[modality]

    def load_phase_signal(self, subject: str, phase: Phase,
                          modality: Modality) -> np.ndarray:
        """
        Ambil sinyal satu fase sebagai array 1-D.

        Catatan penting soal PPG: array label mengikuti laju cacah sinyal
        dada (700 Hz), sedangkan BVP direkam 64 Hz. Maka indeks label harus
        DISKALAKAN dulu ke laju BVP — kalau tidak, potongan yang terambil
        akan meleset jauh.
        """
        if phase not in self._PHASE_TO_LABEL:
            raise ValueError(
                f"WESAD tidak menyediakan fase {phase.value}. "
                f"Tersedia: {[p.value for p in self._PHASE_TO_LABEL]}"
            )

        group, key = self._SIGNAL_KEY[modality]
        signal = np.asarray(self.data["signal"][group][key]).reshape(-1)
        labels = np.asarray(self.data["label"]).reshape(-1)

        # Rentang menyambung terpanjang, dihitung pada laju label (700 Hz).
        mask = labels == self._PHASE_TO_LABEL[phase]
        start, end = self.longest_contiguous_run(mask)

        # Skalakan ke laju sinyal yang diminta.
        scale = signal.size / labels.size
        start = int(round(start * scale))
        end = int(round(end * scale))

        return signal[start:end]
