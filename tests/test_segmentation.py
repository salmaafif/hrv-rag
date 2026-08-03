"""
U1.4 & U1.5 — Uji segmentasi jendela geser dan gerbang mutu.

Jumlah jendela yang seharusnya dihasilkan bisa dihitung tangan:

    n = floor((durasi - 60) / 30) + 1

Contoh, dengan denyut tepat 1000 ms:
    181 denyut -> durasi 180 dtk -> floor(120/30) + 1 = 5 jendela
    121 denyut -> durasi 120 dtk -> floor( 60/30) + 1 = 3 jendela
     61 denyut -> durasi  60 dtk -> floor(  0/30) + 1 = 1 jendela
     45 denyut -> durasi  44 dtk -> lebih pendek dari jendela -> 0
"""

import numpy as np
import pytest

from hrv_rag.features.segmentation import segment_rr_series


@pytest.mark.parametrize("n_beats, expected", [
    (181, 5),
    (121, 3),
    (61, 1),
    (45, 0),
])
def test_jumlah_jendela_sesuai_rumus(make_series, n_beats, expected):
    hasil = segment_rr_series(make_series(n_beats=n_beats))
    assert hasil.n_kept == expected


def test_jendela_bergeser_30_detik(make_series):
    """
    Jendela ke-n harus mulai 30 detik setelah jendela sebelumnya, dan
    panjangnya tetap 60 detik. Inilah inti "overlap 30 detik".
    """
    hasil = segment_rr_series(make_series(n_beats=181))
    mulai = [s.start_sec for s in hasil.segments]
    assert np.allclose(np.diff(mulai), 30.0)
    for seg in hasil.segments:
        assert seg.end_sec - seg.start_sec == pytest.approx(60.0)


def test_jendela_bertetangga_berbagi_data(make_series):
    """
    Konsekuensi overlap yang harus disadari (BACKLOG L2): jendela
    bertetangga berbagi separuh datanya, jadi segmen TIDAK saling bebas.
    Uji ini mendokumentasikan sifat itu, bukan mengeluhkannya.
    """
    hasil = segment_rr_series(make_series(n_beats=181))
    a, b = hasil.segments[0], hasil.segments[1]
    assert a.end_sec > b.start_sec          # rentangnya tumpang tindih


def test_sisa_ekor_dibuang(make_series):
    """
    Durasi 175 dtk -> floor(115/30)+1 = 4 jendela penuh, sisa 25 detik
    di ekor dibuang. Segmen harus seragam 60 detik semua, karena fitur HRV
    sangat sensitif terhadap panjang jendela.
    """
    hasil = segment_rr_series(make_series(n_beats=176))
    assert hasil.n_kept == 4
    assert hasil.segments[-1].end_sec <= 175.0


# --------------------------------------------------------- gerbang mutu
def test_segmen_terlalu_berisik_dibuang(make_series):
    """
    U1.4 — segmen dengan outlier > 10% harus DIBUANG, bukan dipakai.

    Di sini 30% denyut ditandai outlier di seluruh deret, jadi semua jendela
    harus gugur dan tercatat pada penghitung `n_dropped_noisy`.
    """
    n = 181
    mask = np.zeros(n, dtype=bool)
    mask[::3] = True                        # ~33% outlier
    hasil = segment_rr_series(make_series(n_beats=n, outlier_mask=mask))
    assert hasil.n_kept == 0
    assert hasil.n_dropped_noisy == 5


def test_outlier_sedikit_tetap_lolos(make_series):
    """Outlier 5% masih di bawah ambang 10%, jendela tetap dipakai."""
    n = 181
    mask = np.zeros(n, dtype=bool)
    mask[::20] = True                       # ~5%
    hasil = segment_rr_series(make_series(n_beats=n, outlier_mask=mask))
    assert hasil.n_kept == 5
    assert hasil.n_dropped_noisy == 0


def test_denyut_terlalu_sedikit_dibuang(make_series):
    """
    Denyut 2500 ms (24 bpm) -> hanya 24 denyut per 60 detik, di bawah
    ambang 30. Jendela harus gugur karena fiturnya tidak dapat dipercaya.
    """
    hasil = segment_rr_series(make_series(n_beats=100, rr_value=2500.0))
    assert hasil.n_kept == 0
    assert hasil.n_dropped_short > 0


def test_ringkasan_menghitung_semua_jendela(make_series):
    """n_total harus mencakup yang dipakai maupun yang dibuang."""
    hasil = segment_rr_series(make_series(n_beats=181))
    assert hasil.n_total == hasil.n_kept + hasil.n_dropped_short + hasil.n_dropped_noisy


def test_deret_kosong_menghasilkan_daftar_kosong(make_series):
    hasil = segment_rr_series(make_series(n_beats=1))
    assert hasil.n_kept == 0
