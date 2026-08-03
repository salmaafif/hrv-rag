"""
U1.2 — Uji domain frekuensi dengan sinyal buatan berfrekuensi diketahui.

Gagasannya: kalau deret RR sengaja dibuat bergoyang pada 0,25 Hz, maka daya
spektrumnya HARUS muncul di pita HF (0,15-0,40 Hz), bukan di LF. Begitu pula
sebaliknya untuk 0,10 Hz yang jatuh di pita LF (0,04-0,15 Hz).

Uji ini membuktikan kebenaran kode tanpa membandingkan ke pustaka lain —
kebenarannya berasal dari fisika sinyal yang kita kendalikan sendiri.

Kedua metode (Welch dan Lomb-Scargle) diuji dengan kriteria sama, karena
keduanya harus sepakat pada hal sedasar ini. Kalau salah satu gagal di sini,
perbandingan K2 tidak ada artinya.
"""

import numpy as np
import pytest

from conftest import synth_modulated_rr
from hrv_rag.features.frequency_domain import (frequency_features,
                                               lombscargle_bands, welch_bands)


@pytest.fixture(scope="module")
def rr_hf():
    """Deret RR bergoyang di 0,25 Hz — jantung pita HF."""
    return synth_modulated_rr(freq_hz=0.25)


@pytest.fixture(scope="module")
def rr_lf():
    """Deret RR bergoyang di 0,10 Hz — jantung pita LF."""
    return synth_modulated_rr(freq_hz=0.10)


# --------------------------------------------------------------- Welch
def test_welch_menempatkan_025hz_di_pita_hf(rr_hf):
    hasil = welch_bands(rr_hf)
    assert hasil["hf_welch"] > hasil["lf_welch"]
    assert hasil["lf_hf_welch"] < 1.0


def test_welch_menempatkan_010hz_di_pita_lf(rr_lf):
    hasil = welch_bands(rr_lf)
    assert hasil["lf_welch"] > hasil["hf_welch"]
    assert hasil["lf_hf_welch"] > 1.0


# -------------------------------------------------------- Lomb-Scargle
def test_lombscargle_menempatkan_025hz_di_pita_hf(rr_hf):
    hasil = lombscargle_bands(rr_hf)
    assert hasil["hf_ls"] > hasil["lf_ls"]
    assert hasil["lf_hf_ls"] < 1.0


def test_lombscargle_menempatkan_010hz_di_pita_lf(rr_lf):
    hasil = lombscargle_bands(rr_lf)
    assert hasil["lf_ls"] > hasil["hf_ls"]
    assert hasil["lf_hf_ls"] > 1.0


# -------------------------------------------------------- kedua metode
def test_kedua_metode_sepakat_soal_arah(rr_hf, rr_lf):
    """
    Boleh berbeda besaran (terukur ~37% pada data WESAD), tapi TIDAK boleh
    berbeda arah. Kalau satu bilang HF dominan dan satunya bilang LF,
    ada yang rusak.
    """
    for rr in (rr_hf, rr_lf):
        hasil = frequency_features(rr)
        welch_hf_dominan = hasil["lf_hf_welch"] < 1.0
        ls_hf_dominan = hasil["lf_hf_ls"] < 1.0
        assert welch_hf_dominan == ls_hf_dominan


def test_segmen_terlalu_pendek_menghasilkan_nan():
    """
    Deret sangat pendek tidak menghasilkan spektrum bermakna.

    Yang dikembalikan HARUS NaN, bukan 0. Nilai 0 akan terbaca sebagai
    "tidak ada daya LF" — sebuah pengukuran — padahal kenyataannya
    "tidak dapat diukur". Membedakan keduanya penting agar segmen buruk
    tidak diam-diam ikut dihitung dalam metrik.
    """
    hasil = frequency_features(np.full(5, 800.0))
    assert all(np.isnan(v) for v in hasil.values())


def test_deret_datar_tidak_membuat_program_gagal():
    """Deret tanpa variasi sama sekali: tidak boleh melempar exception."""
    hasil = frequency_features(np.full(60, 800.0))
    assert set(hasil) == {"lf_welch", "hf_welch", "lf_hf_welch",
                          "lf_ls", "hf_ls", "lf_hf_ls"}
