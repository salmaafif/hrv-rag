"""
conftest.py — Penyiapan bersama seluruh uji.

Berisi jalur impor dan beberapa pabrik data buatan. Prinsip pengujian di
proyek ini: **uji dengan masukan yang jawabannya sudah diketahui lebih
dulu**, bukan dengan data WESAD. Kalau diuji memakai data nyata, kita hanya
bisa melihat "hasilnya masuk akal" — bukan membuktikan hitungannya benar.

Ini penting karena Aturan Wajib #1 menempatkan KODE sebagai sumber kebenaran
angka. Kalau kodenya salah hitung, seluruh klaim TA ikut runtuh dan LLM
tidak bisa disalahkan.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_rag.core.types import (Modality, Phase,  # noqa: E402
                                QualityReport, RRSeries)


@pytest.fixture
def clean_quality() -> QualityReport:
    """Laporan mutu yang lolos, untuk uji yang tidak menyoal mutu sinyal."""
    return QualityReport(clipping_ratio=0.0, flatline_ratio=0.0,
                         is_acceptable=True)


@pytest.fixture
def make_series(clean_quality):
    """
    Pabrik `RRSeries` buatan.

    Secara bawaan menghasilkan denyut tepat 1000 ms, sehingga waktu tiap
    denyut jatuh persis di detik bulat — memudahkan menghitung jumlah
    segmen yang seharusnya dihasilkan.
    """
    def _make(n_beats: int = 181, rr_value: float = 1000.0,
              outlier_mask: np.ndarray | None = None,
              phase: Phase = Phase.CALIBRATION) -> RRSeries:
        rr = np.full(n_beats, rr_value, dtype=float)
        t = np.cumsum(rr) / 1000.0
        mask = (outlier_mask if outlier_mask is not None
                else np.zeros(n_beats, dtype=bool))
        return RRSeries(rr_ms=rr, t_sec=t, modality=Modality.ECG,
                        subject="UJI", phase=phase,
                        quality=clean_quality, is_outlier=mask)
    return _make


def synth_modulated_rr(freq_hz: float, duration_sec: float = 120.0,
                       mean_rr: float = 800.0, amplitude: float = 50.0
                       ) -> np.ndarray:
    """
    Bangun deret RR yang termodulasi sinus pada frekuensi tertentu.

    Dipakai menguji analisis spektrum: kalau deret RR bergoyang pada 0,25 Hz,
    daya spektrumnya HARUS muncul di pita HF (0,15-0,40 Hz). Ini cara
    membuktikan kode frekuensi benar tanpa perlu membandingkan ke pustaka lain.

    Waktu tiap denyut dibangun bertahap karena panjang RR itu sendirilah yang
    menentukan kapan denyut berikutnya terjadi.
    """
    t, values = 0.0, []
    while t < duration_sec:
        rr = mean_rr + amplitude * np.sin(2.0 * np.pi * freq_hz * t)
        values.append(rr)
        t += rr / 1000.0
    return np.asarray(values)
