"""
base.py — Kontrak bersama cabang pra-pemrosesan ECG dan PPG.

CLAUDE.md mewajibkan kedua modalitas ditulis di berkas terpisah, bukan satu
berkas dengan percabangan `if`. Alasannya nyata: pita filter, algoritma
deteksi puncak, dan kebutuhan pembuangan artefak gerakan memang berbeda.

Namun ada bagian yang IDENTIK untuk keduanya — koreksi ektopik dan
pemeriksaan kualitas bekerja pada deret interval, bukan pada bentuk
gelombang. Bagian itu ditaruh di sini agar tidak ditulis dua kali dan
tidak berisiko menyimpang satu sama lain.

Pembagian tanggung jawab:
    kelas induk  : quality check, koreksi ektopik, perakitan RRSeries
    kelas anak   : filter dan deteksi puncak khas modalitasnya
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..config.settings import QualityConfig, settings
from ..core.types import Modality, Phase, QualityReport, RRSeries


class BasePreprocessor(ABC):
    """Kerangka pra-pemrosesan: sinyal mentah -> RRSeries bersih."""

    modality: Modality

    def __init__(self, sampling_rate: int,
                 quality: QualityConfig | None = None) -> None:
        self.fs = sampling_rate
        self.quality_cfg = quality or settings.quality

    # =================================================== wajib diisi anak
    @abstractmethod
    def filter_signal(self, raw: np.ndarray) -> np.ndarray:
        """Bersihkan sinyal sesuai karakter modalitasnya."""

    @abstractmethod
    def detect_peaks(self, filtered: np.ndarray) -> np.ndarray:
        """Kembalikan indeks sampel tiap puncak denyut."""

    # ========================================================== alur utama
    def run(self, raw: np.ndarray, subject: str, phase: Phase) -> RRSeries:
        """
        Jalankan seluruh rantai pra-pemrosesan.

        Urutannya tetap untuk kedua modalitas:
            quality check -> filter -> deteksi puncak -> deret interval
            -> koreksi ektopik
        """
        report = self.check_quality(raw)
        filtered = self.filter_signal(raw)
        peaks = self.detect_peaks(filtered)
        rr_ms, t_sec = self.peaks_to_intervals(peaks)
        rr_ms, is_outlier = self.correct_ectopic(rr_ms)

        return RRSeries(
            rr_ms=rr_ms, t_sec=t_sec, modality=self.modality,
            subject=subject, phase=phase, quality=report,
            is_outlier=is_outlier,
        )

    # ==================================================== langkah bersama
    def check_quality(self, raw: np.ndarray) -> QualityReport:
        """
        Pemeriksaan kualitas pada sinyal MENTAH, sebelum difilter.

        Harus dilakukan sebelum filter, karena filter justru menyamarkan
        kerusakan: sinyal yang datar akibat elektroda lepas akan tampak
        "wajar" setelah dibandpass, padahal tidak mengandung informasi.

        Dua cacat yang dideteksi:
        1. Clipping — sampel menempel di batas jangkauan ADC. Puncak yang
           terpotong menggeser posisi puncak dan merusak interval.
        2. Flat-line — jendela tanpa variasi sama sekali; menandakan
           elektroda/sensor lepas.
        """
        notes: list[str] = []

        # --- clipping: proporsi sampel di nilai ekstrem ---
        lo, hi = float(np.min(raw)), float(np.max(raw))
        span = hi - lo
        if span == 0:
            return QualityReport(0.0, 1.0, False, ["sinyal konstan total"])
        # Toleransi 0,1% dari rentang, mengantisipasi derau kuantisasi.
        tol = 0.001 * span
        clipping_ratio = float(
            np.mean((raw >= hi - tol) | (raw <= lo + tol))
        )

        # --- flat-line: jendela berturut-turut tanpa variasi ---
        win = max(1, int(self.quality_cfg.flatline_window_sec * self.fs))
        n_win = raw.size // win
        if n_win > 0:
            blocks = raw[: n_win * win].reshape(n_win, win)
            flat_blocks = np.std(blocks, axis=1) < (1e-6 * span)
            flatline_ratio = float(flat_blocks.mean())
        else:
            flatline_ratio = 0.0

        if clipping_ratio > self.quality_cfg.max_clipping_ratio:
            notes.append(f"clipping {clipping_ratio:.1%} melebihi ambang")
        if flatline_ratio > self.quality_cfg.max_flatline_ratio:
            notes.append(f"flat-line {flatline_ratio:.1%} melebihi ambang")

        return QualityReport(
            clipping_ratio=clipping_ratio,
            flatline_ratio=flatline_ratio,
            is_acceptable=not notes,
            notes=notes,
        )

    def peaks_to_intervals(self, peaks: np.ndarray
                           ) -> tuple[np.ndarray, np.ndarray]:
        """
        Ubah indeks puncak menjadi deret interval (ms) beserta waktunya.

        Waktu tiap interval ditempatkan pada puncak KEDUA dari tiap pasangan,
        karena interval itu baru selesai terukur di titik tersebut. Ini yang
        dipakai sebagai acuan saat segmentasi.
        """
        if peaks.size < 2:
            return np.array([]), np.array([])
        rr_ms = np.diff(peaks) / self.fs * 1000.0
        t_sec = peaks[1:] / self.fs
        return rr_ms, t_sec

    def correct_ectopic(self, rr_ms: np.ndarray
                        ) -> tuple[np.ndarray, np.ndarray]:
        """
        Tandai dan perbaiki denyut ektopik / salah-deteksi.

        Dua kriteria sesuai CLAUDE.md:
        1. Di luar batas fisiologis 0,3-2,0 detik (200 bpm sampai 30 bpm).
        2. Berselisih lebih dari 20% terhadap interval sebelumnya.

        Kriteria kedua dihitung terhadap interval TEPAT SEBELUMNYA, dan
        seluruh perbandingan memakai nilai ASLI (belum terkoreksi). Dua hal
        ini penting:

        - Memakai nilai asli membuat penandaan tidak merembet: keputusan
          untuk denyut ke-i tidak bergantung pada hasil koreksi denyut
          sebelumnya.
        - Satu denyut ektopik lazimnya menghasilkan dua interval menyimpang
          (satu memendek, lalu satu memanjang sebagai kompensasi). Kriteria
          ini menandai keduanya, dan itu memang perilaku yang diinginkan.

        Catatan: versi awal kode ini membandingkan terhadap "interval
        terakhir yang diterima" dengan maksud mencegah perembetan. Cara itu
        keliru — nilai acuannya bisa membeku dan menolak denyut secara
        beruntun (terukur 59,5% pada S2 kondisi tertekan, padahal kriteria
        harfiah hanya 1,5%).

        Nilai yang ditandai diganti lewat interpolasi linear dari denyut
        valid di sekitarnya. Interpolasi dipilih daripada penghapusan agar
        sumbu waktu tetap utuh — menghapus denyut akan memendekkan segmen
        secara diam-diam.
        """
        n = rr_ms.size
        if n == 0:
            return rr_ms, np.zeros(0, dtype=bool)

        cfg = self.quality_cfg
        rr = rr_ms.astype(float).copy()
        is_outlier = np.zeros(n, dtype=bool)

        # --- Kriteria 1: batas fisiologis ---
        lo_ms, hi_ms = cfg.rr_min_sec * 1000.0, cfg.rr_max_sec * 1000.0
        is_outlier |= (rr < lo_ms) | (rr > hi_ms)

        # --- Kriteria 2: lompatan >20% terhadap interval sebelumnya ---
        # Dihitung sekaligus pada array asli, bukan dalam loop, agar tidak
        # ada nilai terkoreksi yang ikut jadi pembanding.
        rel_diff = np.abs(np.diff(rr_ms)) / rr_ms[:-1]
        is_outlier[1:] |= rel_diff > cfg.max_rel_diff

        # --- Perbaikan lewat interpolasi ---
        n_bad = int(is_outlier.sum())
        if 0 < n_bad < n:
            idx = np.arange(n)
            rr[is_outlier] = np.interp(
                idx[is_outlier], idx[~is_outlier], rr[~is_outlier]
            )

        return rr, is_outlier
