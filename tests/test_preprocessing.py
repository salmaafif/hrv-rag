"""
U1.3 — Uji koreksi ektopik dengan artefak yang sengaja disisipkan.

Karena kita sendiri yang menyisipkan denyut bermasalah, kita tahu persis
denyut ke berapa yang seharusnya tertandai. Itu yang membuat uji ini bisa
membuktikan kebenaran, bukan sekadar kewajaran.

Uji ini juga mengunci temuan Tahap 1: percobaan membandingkan RR terhadap
"interval terakhir yang diterima" membuat penolakan merembet sampai 59,5%.
Uji `test_penandaan_tidak_merembet` akan gagal kalau bug itu kembali.
"""

import numpy as np
import pytest

from hrv_rag.preprocessing.ecg import ECGPreprocessor


@pytest.fixture
def pre():
    """Pra-pemroses ECG; hanya koreksi ektopik yang diuji di sini."""
    return ECGPreprocessor(sampling_rate=700)


def test_deret_normal_tidak_ditandai(pre):
    """Deret stabil 800 ms tidak boleh menghasilkan satu pun outlier."""
    rr = np.full(50, 800.0)
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.sum() == 0


def test_variasi_wajar_tidak_ditandai(pre):
    """
    HRV normal berubah bertahap dan TIDAK boleh dianggap artefak.
    Variasi +-5% masih jauh di bawah ambang 20%.
    """
    rng = np.random.default_rng(42)
    rr = 800.0 + rng.normal(0, 20, size=200)      # simpangan ~2,5%
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.sum() == 0


def test_denyut_ektopik_tertandai(pre):
    """
    Sisipkan satu denyut ektopik: 800 -> 400 -> 800.

    Denyut ke-10 (400 ms) menyimpang 50% dari sebelumnya, dan denyut ke-11
    menyimpang 100% dari 400 ms. Keduanya HARUS tertandai — memang begitu
    perilaku yang diinginkan, karena satu denyut ektopik lazimnya merusak
    dua interval (memendek, lalu memanjang sebagai kompensasi).
    """
    rr = np.full(30, 800.0)
    rr[10] = 400.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier[10]
    assert outlier[11]


def test_nilai_ektopik_diperbaiki_mendekati_tetangga(pre):
    """Setelah interpolasi, nilai yang tadinya 400 ms harus kembali ~800."""
    rr = np.full(30, 800.0)
    rr[10] = 400.0
    corrected, _ = pre.correct_ectopic(rr)
    assert corrected[10] == pytest.approx(800.0, abs=1.0)


def test_batas_fisiologis_bawah(pre):
    """RR 250 ms (240 bpm) di luar batas 0,3 dtk — mustahil secara fisiologis."""
    rr = np.full(30, 800.0)
    rr[5] = 250.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier[5]


def test_batas_fisiologis_atas(pre):
    """RR 2500 ms (24 bpm) di luar batas 2,0 dtk."""
    rr = np.full(30, 800.0)
    rr[5] = 2500.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier[5]


def test_penandaan_tidak_merembet(pre):
    """
    UJI REGRESI untuk bug Tahap 1.

    Deret yang menanjak perlahan (tiap denyut +2%, masih wajar) dengan satu
    artefak di tengah. Yang tertandai harus SEDIKIT — hanya di sekitar
    artefak. Versi buggy dulu menandai lebih dari separuh deret karena nilai
    acuannya membeku.
    """
    rr = 700.0 * (1.02 ** np.arange(40))     # menanjak 2% per denyut
    rr[20] = 300.0                            # artefak tunggal
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.mean() < 0.20, (
        f"terlalu banyak tertandai ({outlier.mean():.1%}) — "
        f"perembetan mungkin kembali"
    )


def test_perbandingan_memakai_nilai_asli(pre):
    """
    Penandaan harus dihitung dari array ASLI, bukan dari nilai yang sudah
    dikoreksi. Kalau tidak, keputusan denyut ke-i bergantung pada hasil
    koreksi denyut sebelumnya — dan itu pintu masuk perembetan.

    Dua artefak berjauhan: jumlah yang tertandai harus tetap kecil.
    """
    rr = np.full(60, 800.0)
    rr[10] = 400.0
    rr[40] = 1300.0
    _, outlier = pre.correct_ectopic(rr)
    assert outlier.sum() <= 4


def test_deret_kosong_tidak_membuat_gagal(pre):
    corrected, outlier = pre.correct_ectopic(np.array([]))
    assert corrected.size == 0 and outlier.size == 0
