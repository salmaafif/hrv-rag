"""
base.py — Kontrak bersama semua loader dataset.

Kenapa ada kelas abstrak di sini? Karena proyek ini memakai tiga dataset
dengan struktur berkas dan struktur label yang sama sekali berbeda, tetapi
kode sesudahnya (pra-pemrosesan, fitur, RAG) harus bisa memperlakukan
ketiganya seragam.

Dengan kontrak ini, menambah SWELL-KW atau UBFC-Phys nanti = menulis satu
kelas turunan baru, TANPA menyentuh kode mana pun yang sudah jalan.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..core.types import Modality, Phase


class BaseDatasetLoader(ABC):
    """
    Antarmuka baku pemuat dataset.

    Turunan wajib menjawab tiga pertanyaan:
      1. Siapa saja subjeknya?                       -> subjects
      2. Modalitas apa yang tersedia?                -> available_modalities
      3. Bagaimana mengambil sinyal satu fase?       -> load_phase_signal
    """

    #: Nama dataset, dipakai untuk penamaan berkas keluaran dan pelaporan
    #: metrik per dataset (CLAUDE.md melarang menggabungkan antar dataset).
    name: str = "base"

    # ---------------------------------------------------------------- wajib
    @property
    @abstractmethod
    def subjects(self) -> tuple[str, ...]:
        """Daftar ID subjek yang tersedia."""

    @property
    @abstractmethod
    def available_modalities(self) -> tuple[Modality, ...]:
        """Modalitas yang disediakan dataset ini."""

    @abstractmethod
    def sampling_rate(self, modality: Modality) -> int:
        """Frekuensi sampling (Hz) untuk modalitas tertentu."""

    @abstractmethod
    def load_phase_signal(self, subject: str, phase: Phase,
                          modality: Modality) -> np.ndarray:
        """
        Ambil potongan sinyal mentah satu fase, satu subjek.

        Turunan bertanggung jawab memetakan label dataset ke `Phase`.
        """

    # ------------------------------------------------------------- bersama
    @staticmethod
    def longest_contiguous_run(mask: np.ndarray) -> tuple[int, int]:
        """
        Cari rentang True terpanjang yang menyambung pada `mask`.

        Kenapa perlu? Kalau sinyal diambil dengan `sinyal[mask]` biasa,
        potongan-potongan waktu yang terpisah akan tersambung begitu saja.
        Titik sambungannya menciptakan lompatan tajam yang akan terbaca
        sebagai puncak R palsu, lalu muncul sebagai interval RR yang salah.
        Maka diambil satu rentang menyambung terpanjang saja.

        Return: (indeks_awal, indeks_akhir) dengan akhir bersifat eksklusif.
        """
        if not mask.any():
            raise ValueError("Mask kosong — fase yang diminta tidak ada.")

        # Selisih mask sebagai int menandai tepi naik (+1) dan tepi turun (-1).
        edges = np.diff(mask.astype(np.int8))
        starts = np.flatnonzero(edges == 1) + 1
        ends = np.flatnonzero(edges == -1) + 1

        if mask[0]:                       # sudah True sejak sampel pertama
            starts = np.r_[0, starts]
        if mask[-1]:                      # masih True sampai sampel terakhir
            ends = np.r_[ends, mask.size]

        longest = int(np.argmax(ends - starts))
        return int(starts[longest]), int(ends[longest])
