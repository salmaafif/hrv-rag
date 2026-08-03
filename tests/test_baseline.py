"""
U1.6 — Uji baseline personal dan reaktivitas.

Uji terpenting di berkas ini: segmen yang nilainya sama persis dengan
baseline HARUS menghasilkan reaktivitas 0%. Kalau tidak, seluruh angka
reaktivitas di proyek ini bergeser secara sistematis.
"""

import numpy as np
import pandas as pd
import pytest

from hrv_rag.features.baseline import BaselineProfile


@pytest.fixture
def kalibrasi() -> pd.DataFrame:
    """
    Tabel fitur kalibrasi buatan dengan median yang mudah dihitung.

    RMSSD = [40, 45, 50, 55, 60] -> median 50 (nilai tengah)
    """
    return pd.DataFrame({
        "rmssd": [40.0, 45.0, 50.0, 55.0, 60.0],
        "sdnn": [50.0, 55.0, 60.0, 65.0, 70.0],
        "mean_hr": [70.0, 70.0, 70.0, 70.0, 70.0],
    })


def test_baseline_memakai_median(kalibrasi):
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    assert profil.values["rmssd"] == pytest.approx(50.0)


def test_median_tahan_terhadap_pencilan(kalibrasi):
    """
    Alasan memilih median, bukan rata-rata.

    Satu segmen berisik dengan RMSSD 500 ms menggeser rata-rata dari 50 ke
    125 — melenceng 150%. Median hanya bergeser dari 50 ke 52,5, yaitu 5%.
    Karena semua angka reaktivitas dibagi dengan acuan ini, kestabilannya
    menentukan kestabilan seluruh hasil.

    Nilai 52,5 muncul karena dengan enam data, median adalah rata-rata dua
    nilai tengah: (50 + 55) / 2.
    """
    kotor = pd.concat([kalibrasi, pd.DataFrame({"rmssd": [500.0]})],
                      ignore_index=True)
    profil = BaselineProfile.from_segments("UJI", kotor)
    assert profil.values["rmssd"] == pytest.approx(52.5)
    assert kotor["rmssd"].mean() == pytest.approx(125.0)   # rata-rata rusak


def test_reaktivitas_nol_bila_sama_dengan_baseline(kalibrasi):
    """PEMERIKSAAN KEWARASAN UTAMA — nilai identik harus menghasilkan 0%."""
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    hasil = profil.reactivity({"rmssd": 50.0, "sdnn": 60.0, "mean_hr": 70.0})
    assert hasil["delta_pct_rmssd"] == pytest.approx(0.0)
    assert hasil["delta_pct_sdnn"] == pytest.approx(0.0)


def test_reaktivitas_turun_bernilai_negatif(kalibrasi):
    """RMSSD 25 terhadap acuan 50 = turun 50%."""
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    hasil = profil.reactivity({"rmssd": 25.0})
    assert hasil["delta_pct_rmssd"] == pytest.approx(-50.0)


def test_reaktivitas_naik_bernilai_positif(kalibrasi):
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    hasil = profil.reactivity({"rmssd": 75.0})
    assert hasil["delta_pct_rmssd"] == pytest.approx(50.0)


def test_reaktivitas_tidak_menggabungkan_fitur(kalibrasi):
    """
    Kode HANYA menghasilkan reaktivitas per fitur — tidak ada kolom skor
    gabungan. Penggabungan adalah tugas LLM berbekal knowledge base; kalau
    kode yang menggabungkan, LLM tinggal membaca ambang dan pendekatan RAG
    kehilangan alasan keberadaannya.
    """
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    hasil = profil.reactivity({"rmssd": 25.0, "sdnn": 30.0, "mean_hr": 90.0})
    assert all(k.startswith("delta_pct_") for k in hasil)


def test_kalibrasi_kosong_ditolak():
    """
    Tanpa segmen kalibrasi, baseline tidak dapat dibentuk dan seluruh
    reaktivitas kehilangan makna. Lebih baik gagal terang-terangan daripada
    diam-diam memakai angka asal.
    """
    with pytest.raises(ValueError, match="baseline tidak dapat dibentuk"):
        BaselineProfile.from_segments("UJI", pd.DataFrame())


def test_sebaran_menandai_baseline_goyah(kalibrasi):
    """
    IQR relatif dipakai sebagai peringatan. Pada data WESAD nyata, S10
    menghasilkan 52% — jauh di atas subjek lain (14-17%) — dan subjek itu
    pula yang kemudian berpola terbalik.
    """
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    # RMSSD [40..60]: kuartil 45 dan 55 -> IQR 10, acuan 50 -> 20%
    assert profil.relative_spread("rmssd") == pytest.approx(0.20)


def test_fitur_nan_tidak_membuat_gagal(kalibrasi):
    profil = BaselineProfile.from_segments("UJI", kalibrasi)
    hasil = profil.reactivity({"rmssd": np.nan})
    assert np.isnan(hasil["delta_pct_rmssd"])
