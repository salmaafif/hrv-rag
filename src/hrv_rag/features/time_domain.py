"""
time_domain.py — Fitur HRV domain waktu.

Semua fungsi di sini murni: masuk array, keluar angka, tidak menyimpan apa
pun. Bentuk seperti ini paling mudah diuji (BACKLOG U1) karena hasilnya bisa
dibandingkan dengan hitungan tangan.

Menurut knowledge base, pada segmen 60 detik fitur domain waktu — terutama
RMSSD — jauh lebih andal daripada fitur domain frekuensi. Karena itu fitur
di berkas inilah yang diprioritaskan saat menafsirkan.
"""

from __future__ import annotations

import numpy as np

#: Nama fitur yang dihasilkan modul ini, berurutan.
TIME_FEATURES = ("mean_rr", "mean_hr", "sdnn", "rmssd", "pnn50")


def mean_rr(rr_ms: np.ndarray) -> float:
    """
    Rata-rata interval RR (ms).

    Mengecil berarti jantung berdetak lebih cepat — indikasi arousal.
    """
    return float(np.mean(rr_ms))


def mean_hr(rr_ms: np.ndarray) -> float:
    """
    Detak jantung rata-rata (bpm).

    Dihitung dari meanRR, bukan dari rata-rata detak sesaat. Perlu hati-hati:
    60000/mean(RR) TIDAK sama dengan mean(60000/RR) karena pembagian bersifat
    tak linear. Yang dipakai di literatur HRV adalah bentuk pertama.
    """
    return 60000.0 / mean_rr(rr_ms)


def sdnn(rr_ms: np.ndarray) -> float:
    """
    Simpangan baku seluruh interval RR (ms) — variabilitas total.

    Dipakai ddof=1 (pembagi n-1) karena segmen ini SAMPEL dari proses yang
    lebih panjang, bukan seluruh populasi. Pada 60 detik dengan ~70 denyut
    selisihnya kecil, tapi pilihan ini harus konsisten dan bisa dijelaskan.

    SDNN dipengaruhi simpatis maupun parasimpatis, dan cenderung menurun
    saat tertekan.
    """
    return float(np.std(rr_ms, ddof=1))


def rmssd(rr_ms: np.ndarray) -> float:
    """
    Akar rata-rata kuadrat selisih RR berurutan (ms).

    Karena dihitung dari SELISIH antar denyut bertetangga, RMSSD menangkap
    perubahan cepat — yaitu pengaruh saraf vagus, yang bekerja jauh lebih
    gesit daripada simpatis. Inilah alasan RMSSD tetap andal pada rekaman
    pendek, dan kenapa ia jadi fitur utama sistem ini.

    RMSSD menurun saat tekanan meningkat.
    """
    diff = np.diff(rr_ms)
    return float(np.sqrt(np.mean(diff ** 2)))


def pnn50(rr_ms: np.ndarray) -> float:
    """
    Persentase pasangan RR berurutan yang berbeda lebih dari 50 ms.

    Seperti RMSSD, mencerminkan aktivitas vagal — tapi berupa cacahan, bukan
    besaran. Akibatnya pNN50 lebih kasar: pada orang dengan HRV rendah,
    nilainya bisa menyentuh 0% dan berhenti membedakan apa pun (efek lantai).
    Karena itu dilaporkan sebagai pelengkap RMSSD, bukan pengganti.
    """
    diff = np.abs(np.diff(rr_ms))
    return float(np.mean(diff > 50.0) * 100.0)


def time_domain_features(rr_ms: np.ndarray) -> dict[str, float]:
    """Hitung seluruh fitur domain waktu sekaligus untuk satu segmen."""
    return {
        "mean_rr": mean_rr(rr_ms),
        "mean_hr": mean_hr(rr_ms),
        "sdnn": sdnn(rr_ms),
        "rmssd": rmssd(rr_ms),
        "pnn50": pnn50(rr_ms),
    }
