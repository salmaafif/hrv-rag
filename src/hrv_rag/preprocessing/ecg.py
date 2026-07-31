"""
ecg.py — Cabang pra-pemrosesan ECG (modalitas acuan / gold standard).

Yang khas ECG dan TIDAK berlaku untuk PPG:
  - Pita 0,5-40 Hz, karena kompleks QRS punya komponen tajam sampai ~40 Hz
  - Notch 50 Hz, karena elektroda ECG menangkap interferensi jala-jala
  - Deteksi puncak R (bukan puncak sistolik), bentuknya sempit dan tinggi
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch

import neurokit2 as nk

from ..config.settings import ECGFilterConfig, QualityConfig, settings
from ..core.types import Modality
from .base import BasePreprocessor


class ECGPreprocessor(BasePreprocessor):
    """Sinyal ECG mentah -> deret RR bersih."""

    modality = Modality.ECG

    def __init__(self, sampling_rate: int,
                 filter_cfg: ECGFilterConfig | None = None,
                 quality: QualityConfig | None = None) -> None:
        super().__init__(sampling_rate, quality)
        self.filter_cfg = filter_cfg or settings.ecg_filter

    def filter_signal(self, raw: np.ndarray) -> np.ndarray:
        """
        Bandpass Butterworth orde 2 (0,5-40 Hz) + notch 50 Hz.

        Kenapa filtfilt, bukan lfilter? filtfilt menyaring maju lalu mundur,
        sehingga pergeseran fasenya saling meniadakan. Ini bukan detail
        kosmetik: filter biasa menggeser posisi puncak R beberapa milidetik,
        dan karena RMSSD dihitung dari selisih antar interval, pergeseran
        sekecil itu langsung mencemari fitur utama sistem ini.
        """
        cfg = self.filter_cfg
        nyq = 0.5 * self.fs

        b, a = butter(
            cfg.order,
            [cfg.lowcut_hz / nyq, cfg.highcut_hz / nyq],
            btype="band",
        )
        filtered = filtfilt(b, a, raw)

        b_notch, a_notch = iirnotch(cfg.notch_hz, cfg.notch_q, self.fs)
        return filtfilt(b_notch, a_notch, filtered)

    def detect_peaks(self, filtered: np.ndarray) -> np.ndarray:
        """
        Deteksi puncak R memakai NeuroKit2 (varian Pan-Tompkins).

        Dipakai pustaka mapan, bukan implementasi sendiri, karena deteksi
        QRS adalah masalah yang sudah lama terpecahkan dan tervalidasi luas.
        Nilai tambah TA ini ada di tahap RAG, bukan di menulis ulang detektor.
        """
        _, info = nk.ecg_peaks(filtered, sampling_rate=self.fs)
        return np.asarray(info["ECG_R_Peaks"])
