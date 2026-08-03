"""
segmentation.py — Membagi deret RR menjadi segmen analisis 60 detik.

Segmentasi memakai JENDELA GESER: panjang 60 detik, bergeser 30 detik.
Jendela ke-1 mencakup detik 0-60, jendela ke-2 detik 30-90, dan seterusnya.

Kenapa bergeser, bukan berurutan? Kalau segmennya berurutan (0-60, 60-120),
lonjakan tekanan yang terjadi di detik 45-105 akan terbelah dua dan tidak ada
satu pun segmen yang menangkapnya utuh. Jendela geser menggandakan resolusi
waktu menjadi 30 detik tanpa memperpendek jendela analisis.

KONSEKUENSI yang harus disebut saat melaporkan metrik: jendela bertetangga
berbagi separuh datanya, jadi segmen TIDAK saling bebas (BACKLOG L2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config.settings import SegmentationConfig, QualityConfig, settings
from ..core.types import RRSeries


@dataclass(frozen=True)
class Segment:
    """Satu jendela analisis beserta jejak asal-usulnya."""

    index: int                 # nomor urut jendela (mulai 1)
    start_sec: float           # batas awal jendela, relatif awal fase
    end_sec: float
    rr_ms: np.ndarray          # interval di dalam jendela
    outlier_ratio: float       # proporsi denyut hasil interpolasi

    @property
    def n_beats(self) -> int:
        return int(self.rr_ms.size)


@dataclass
class SegmentationResult:
    """Hasil segmentasi + catatan berapa jendela dibuang dan kenapa."""

    segments: list[Segment]
    n_dropped_short: int = 0       # denyut terlalu sedikit
    n_dropped_noisy: int = 0       # outlier melebihi ambang

    @property
    def n_kept(self) -> int:
        return len(self.segments)

    @property
    def n_total(self) -> int:
        return self.n_kept + self.n_dropped_short + self.n_dropped_noisy

    def summary(self) -> str:
        return (f"{self.n_kept}/{self.n_total} jendela dipakai "
                f"(dibuang: {self.n_dropped_short} kurang denyut, "
                f"{self.n_dropped_noisy} terlalu berisik)")


def segment_rr_series(
    series: RRSeries,
    seg_cfg: SegmentationConfig | None = None,
    qual_cfg: QualityConfig | None = None,
) -> SegmentationResult:
    """
    Potong satu `RRSeries` menjadi daftar `Segment` yang lolos mutu.

    Pembagian dilakukan berdasarkan WAKTU, bukan jumlah denyut, supaya tiap
    jendela benar-benar mewakili 60 detik rekaman. Kalau dibagi per jumlah
    denyut, orang dengan detak cepat akan mendapat jendela yang lebih pendek
    — dan fitur HRV sangat sensitif terhadap panjang jendela.

    Dua gerbang mutu diterapkan di sini:
      1. Jendela dengan denyut < `min_beats` dibuang (gagal deteksi).
      2. Jendela dengan outlier > `max_outlier_ratio` dibuang (T1.6).
         Menghitung RMSSD dari deret yang separuhnya hasil interpolasi
         berarti mengukur tebakan, bukan mengukur jantung.
    """
    seg_cfg = seg_cfg or settings.segmentation
    qual_cfg = qual_cfg or settings.quality

    result = SegmentationResult(segments=[])
    if series.n_beats == 0:
        return result

    t0 = float(series.t_sec[0])
    duration = float(series.t_sec[-1]) - t0
    if duration < seg_cfg.length_sec:
        return result

    # Jumlah jendela penuh yang muat. Sisa di ekor yang kurang dari 60 detik
    # sengaja dibuang agar semua segmen berdurasi setara.
    n_windows = int((duration - seg_cfg.length_sec) // seg_cfg.hop_sec) + 1

    kept: list[Segment] = []
    for i in range(n_windows):
        start = t0 + i * seg_cfg.hop_sec
        end = start + seg_cfg.length_sec

        window = (series.t_sec >= start) & (series.t_sec < end)
        rr = series.rr_ms[window]
        outliers = series.is_outlier[window]

        if rr.size < seg_cfg.min_beats:
            result.n_dropped_short += 1
            continue

        ratio = float(outliers.mean())
        if ratio > qual_cfg.max_outlier_ratio:
            result.n_dropped_noisy += 1
            continue

        kept.append(Segment(
            index=len(kept) + 1,
            start_sec=start - t0,
            end_sec=end - t0,
            rr_ms=rr,
            outlier_ratio=ratio,
        ))

    result.segments = kept
    return result
