"""
Uji rumus pemulihan dan kuadran ketahanan.

Ini bagian terpenting dari U1. Pemulihan dan ketahanan TIDAK BISA diuji
memakai WESAD karena WESAD tidak punya fase jeda — hanya baseline dan TSST.
Jadi satu-satunya cara memastikan rumusnya benar sebelum dipakai pada data
sesi nyata adalah menguji dengan angka yang jawabannya sudah diketahui.

Contoh acuan memakai angka S2 yang sebenarnya:
    baseline RMSSD  = 56,8 ms
    saat tertekan   = 31,7 ms   -> simpangan 25,1 ms
    saat jeda       = 45,0 ms   -> pulih 13,3 dari 25,1 = 52,99%
"""

import numpy as np
import pytest

from hrv_rag.features.dynamics import (ResilienceQuadrant, recovery_percent,
                                       resilience_quadrant)


# ------------------------------------------------------------- pemulihan
def test_pemulihan_contoh_s2():
    """Contoh acuan yang dipakai di dokumentasi harus benar-benar keluar 53%."""
    hasil = recovery_percent(baseline=56.8, stressed=31.7, recovered=45.0)
    assert hasil.is_computable
    assert hasil.percent == pytest.approx(52.99, abs=0.01)


def test_pemulihan_penuh_seratus_persen():
    """Kembali tepat ke baseline = 100% pulih."""
    hasil = recovery_percent(baseline=50.0, stressed=30.0, recovered=50.0)
    assert hasil.percent == pytest.approx(100.0)


def test_tanpa_pemulihan_nol_persen():
    """Tidak bergerak sama sekali dari kondisi tertekan = 0%."""
    hasil = recovery_percent(baseline=50.0, stressed=30.0, recovered=30.0)
    assert hasil.percent == pytest.approx(0.0)


def test_pemulihan_berlebih_di_atas_seratus():
    """Melampaui baseline (kompensasi berlebih) boleh melebihi 100%."""
    hasil = recovery_percent(baseline=50.0, stressed=30.0, recovered=60.0)
    assert hasil.percent > 100.0


def test_makin_memburuk_bernilai_negatif():
    """Menjauh dari baseline saat jeda = pemulihan negatif."""
    hasil = recovery_percent(baseline=50.0, stressed=30.0, recovered=20.0)
    assert hasil.percent < 0.0


def test_arah_naik_juga_bekerja():
    """
    Rumusnya harus bekerja untuk fitur yang NAIK saat tertekan, seperti
    LF/HF dan detak jantung — bukan hanya yang turun seperti RMSSD.
    """
    hasil = recovery_percent(baseline=2.0, stressed=4.0, recovered=3.0)
    assert hasil.percent == pytest.approx(50.0)


# -------------------------------------------------------------- pengaman
def test_reaksi_terlalu_kecil_tidak_dihitung():
    """
    PENGAMAN UTAMA. Simpangan hanya 4% (50 -> 48), di bawah ambang 10%.

    Tanpa pengaman ini, pembagian dengan penyebut mungil menghasilkan angka
    liar. Yang benar adalah menyatakan TIDAK DAPAT DIHITUNG.
    """
    hasil = recovery_percent(baseline=50.0, stressed=48.0, recovered=49.0)
    assert not hasil.is_computable
    assert "terlalu kecil" in hasil.reason


def test_tidak_dapat_dihitung_bukan_nol():
    """
    Perbedaan yang menentukan: None berarti "tidak diketahui", sedangkan 0
    berarti "tidak pulih sama sekali". Keduanya klaim yang sangat berbeda,
    dan mencampurnya akan memalsukan kesimpulan tentang pengguna.
    """
    hasil = recovery_percent(baseline=50.0, stressed=48.0, recovered=49.0)
    assert hasil.percent is None
    assert hasil.percent != 0


def test_nilai_kosong_ditangani():
    hasil = recovery_percent(baseline=np.nan, stressed=30.0, recovered=40.0)
    assert not hasil.is_computable


def test_baseline_nol_ditangani():
    hasil = recovery_percent(baseline=0.0, stressed=30.0, recovered=40.0)
    assert not hasil.is_computable


# ------------------------------------------------------------- ketahanan
@pytest.mark.parametrize("reaktivitas, pemulihan, diharapkan", [
    (-10.0, 80.0, ResilienceQuadrant.HIGH),       # kecil + cepat
    (-10.0, 20.0, ResilienceQuadrant.HELD_IN),    # kecil + lambat
    (-40.0, 80.0, ResilienceQuadrant.FLEXIBLE),   # besar + cepat
    (-40.0, 20.0, ResilienceQuadrant.LOW),        # besar + lambat
])
def test_empat_kuadran(reaktivitas, pemulihan, diharapkan):
    assert resilience_quadrant(reaktivitas, pemulihan) is diharapkan


def test_reaktivitas_dinilai_dari_nilai_mutlak():
    """
    Yang dinilai besar goncangannya, bukan arahnya. RMSSD turun 40% dan
    LF/HF naik 40% sama-sama tergolong reaktivitas besar.
    """
    turun = resilience_quadrant(-40.0, 80.0)
    naik = resilience_quadrant(+40.0, 80.0)
    assert turun is naik is ResilienceQuadrant.FLEXIBLE


def test_tanpa_pemulihan_kuadran_tidak_ditentukan():
    """
    Kalau salah satu sumbu hilang, kuadrannya TIDAK boleh ditebak.
    Menebak akan membuat kesimpulan tampak lebih pasti daripada datanya.
    """
    assert resilience_quadrant(-40.0, None) is None
