"""
U1.1 — Uji fitur domain waktu terhadap hitungan tangan.

Deret uji utama: RR = [800, 810, 790, 800] ms.

Hitungan manualnya:
    meanRR  = (800+810+790+800)/4 = 800 ms
    meanHR  = 60000/800 = 75 bpm
    selisih = [+10, -20, +10]
    RMSSD   = sqrt((100+400+100)/3) = sqrt(200) = 14,1421 ms
    SDNN    = sqrt((0+100+100+0)/3) = sqrt(66,667) = 8,1650 ms   (ddof=1)
    pNN50   = tidak ada selisih > 50 ms -> 0%
"""

import numpy as np
import pytest

from hrv_rag.features.time_domain import (mean_hr, mean_rr, pnn50, rmssd,
                                          sdnn, time_domain_features)

RR = np.array([800.0, 810.0, 790.0, 800.0])


def test_mean_rr():
    assert mean_rr(RR) == pytest.approx(800.0)


def test_mean_hr():
    """meanHR harus 60000/meanRR, bukan rata-rata detak sesaat."""
    assert mean_hr(RR) == pytest.approx(75.0)


def test_rmssd():
    assert rmssd(RR) == pytest.approx(np.sqrt(200.0), rel=1e-9)


def test_sdnn_memakai_ddof_1():
    """
    SDNN memakai pembagi n-1, bukan n.

    Kalau suatu saat ddof berubah jadi 0, nilainya jadi sqrt(50)=7,071 dan
    uji ini gagal — itulah gunanya: mengunci pilihan yang sudah diputuskan.
    """
    assert sdnn(RR) == pytest.approx(np.sqrt(200.0 / 3.0), rel=1e-9)
    assert sdnn(RR) != pytest.approx(np.sqrt(50.0))


def test_pnn50_nol_bila_selisih_kecil():
    assert pnn50(RR) == pytest.approx(0.0)


def test_pnn50_seratus_bila_semua_selisih_besar():
    """RR = [800, 900, 800] -> selisih [100, 100], keduanya > 50 ms."""
    assert pnn50(np.array([800.0, 900.0, 800.0])) == pytest.approx(100.0)


def test_pnn50_ambang_tepat_50_tidak_dihitung():
    """
    Ambangnya "lebih dari 50 ms", jadi selisih tepat 50 ms TIDAK dihitung.
    Detail kecil, tapi harus konsisten agar angka bisa direproduksi.
    """
    assert pnn50(np.array([800.0, 850.0, 800.0])) == pytest.approx(0.0)


def test_rmssd_peka_urutan_sdnn_tidak():
    """
    Pembeda mendasar kedua fitur ini.

    SDNN hanya melihat sebaran nilai, jadi mengacak urutan tidak mengubahnya.
    RMSSD melihat selisih antar denyut BERURUTAN, jadi urutan sangat penting.
    Inilah alasan RMSSD mencerminkan perubahan cepat (aktivitas vagal).
    """
    diacak = np.array([790.0, 800.0, 800.0, 810.0])
    assert sdnn(diacak) == pytest.approx(sdnn(RR))
    assert rmssd(diacak) != pytest.approx(rmssd(RR))


def test_seluruh_fitur_lengkap_dan_terbatas():
    hasil = time_domain_features(RR)
    assert set(hasil) == {"mean_rr", "mean_hr", "sdnn", "rmssd", "pnn50"}
    assert all(np.isfinite(v) for v in hasil.values())
