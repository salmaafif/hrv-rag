"""
frequency_domain.py — Fitur HRV domain frekuensi, DUA metode berdampingan.

Masalah dasarnya: analisis spektrum klasik mensyaratkan sampel berjarak
tetap, sedangkan deret RR justru tidak — jarak antar sampelnya adalah RR itu
sendiri (800 ms, lalu 750 ms, lalu 820 ms).

Ada dua jalan keluar, dan keputusan K2 memakai keduanya lalu membandingkan:

  (a) Welch setelah interpolasi ke 4 Hz
      Deret RR "diluruskan" dulu jadi sampel tiap 0,25 detik memakai
      interpolasi cubic-spline. Cara paling lazim dan paling mudah disitasi.
      Kelemahan: interpolasi menebak nilai di antara denyut, dan tebakan itu
      menyumbang energi yang sebenarnya tidak ada di data.

  (b) Lomb-Scargle langsung pada deret tak seragam
      Tidak menebak apa pun. Kelemahan: lebih jarang dipakai di literatur
      HRV sehingga pembandingnya sedikit.

Kalau keduanya sepakat, itu bukti fiturnya kokoh. Kalau berbeda jauh, itu
temuan yang layak dibahas di sidang.

PERINGATAN yang berlaku untuk KEDUA metode: pada segmen 60 detik, pita LF
(0,04-0,15 Hz) kurang stabil karena satu siklus LF terlama saja memakan 25
detik — hanya muat dua kali dalam jendela. Perlakukan LF/HF sebagai
pendukung, bukan penentu.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import lombscargle, welch

from ..config.settings import FrequencyConfig, settings

#: Nama fitur yang dihasilkan modul ini.
FREQ_FEATURES = ("lf_welch", "hf_welch", "lf_hf_welch",
                 "lf_ls", "hf_ls", "lf_hf_ls")

#: Denyut minimum agar spektrum masih masuk akal dihitung.
_MIN_BEATS = 20


def _beat_times(rr_ms: np.ndarray) -> np.ndarray:
    """
    Waktu kumulatif tiap denyut (detik), dipakai sebagai sumbu-x.

    Deret RR adalah selisih waktu, jadi waktu kejadiannya = jumlah kumulatif.
    """
    return np.cumsum(rr_ms) / 1000.0


def _band_power(freq: np.ndarray, psd: np.ndarray,
                band: tuple[float, float]) -> float:
    """
    Daya pada satu pita = luas di bawah kurva PSD pada rentang itu.

    Dihitung dengan aturan trapesium. Batas bawah inklusif, batas atas
    eksklusif, supaya pita LF dan HF tidak berbagi titik di 0,15 Hz.
    """
    lo, hi = band
    mask = (freq >= lo) & (freq < hi)
    if mask.sum() < 2:
        return float("nan")
    return float(np.trapezoid(psd[mask], freq[mask]))


def welch_bands(rr_ms: np.ndarray,
                cfg: FrequencyConfig | None = None) -> dict[str, float]:
    """
    Metode (a): interpolasi ke 4 Hz, lalu periodogram Welch.

    Kenapa 4 Hz? Pita tertinggi yang diminati adalah HF sampai 0,4 Hz.
    Kaidah Nyquist menuntut minimal 0,8 Hz; 4 Hz memberi kelonggaran besar
    tanpa memboroskan perhitungan, dan sudah jadi kelaziman di literatur HRV.

    Kenapa cubic-spline, bukan interpolasi linear? Sinyal HRV bervariasi
    mulus. Interpolasi linear menciptakan patahan tajam di tiap denyut, dan
    patahan itu menyumbang energi palsu di frekuensi tinggi — persis pita
    HF yang mau diukur.

    Catatan: `nperseg` diambil sepanjang data (satu jendela). Membagi 60
    detik menjadi beberapa sub-jendela memang menurunkan ragam, tapi
    sekaligus memperburuk resolusi frekuensi sampai pita LF tak lagi
    terwakili. Untuk segmen sependek ini, resolusi lebih berharga.
    """
    cfg = cfg or settings.frequency
    if rr_ms.size < _MIN_BEATS:
        return {"lf_welch": np.nan, "hf_welch": np.nan, "lf_hf_welch": np.nan}

    t = _beat_times(rr_ms)

    # Grid waktu seragam sepanjang rentang data.
    n_samples = int((t[-1] - t[0]) * cfg.resample_hz)
    if n_samples < 8:
        return {"lf_welch": np.nan, "hf_welch": np.nan, "lf_hf_welch": np.nan}
    t_uniform = np.linspace(t[0], t[-1], n_samples)

    rr_uniform = CubicSpline(t, rr_ms)(t_uniform)

    # detrend="linear" membuang tren lurus (mis. RR memanjang perlahan
    # sepanjang segmen). Tanpa ini, tren tersebut muncul sebagai energi
    # semu di frekuensi sangat rendah dan mencemari pita LF.
    freq, psd = welch(
        rr_uniform, fs=cfg.resample_hz,
        nperseg=len(rr_uniform), detrend="linear",
    )

    lf = _band_power(freq, psd, cfg.lf_band)
    hf = _band_power(freq, psd, cfg.hf_band)
    return {
        "lf_welch": lf,
        "hf_welch": hf,
        "lf_hf_welch": lf / hf if hf and hf > 0 else np.nan,
    }


def lombscargle_bands(rr_ms: np.ndarray,
                      cfg: FrequencyConfig | None = None) -> dict[str, float]:
    """
    Metode (b): periodogram Lomb-Scargle, langsung pada deret tak seragam.

    Lomb-Scargle mencocokkan gelombang sinus-cosinus ke data pada tiap
    frekuensi uji, tanpa peduli sampelnya berjarak tetap atau tidak. Itulah
    sebabnya interpolasi tidak diperlukan.

    Soal satuan: keluaran mentah `scipy.signal.lombscargle` tidak berada pada
    skala ms^2/Hz seperti Welch. Di sini dipakai penskalaan Parseval —
    seluruh spektrum diskalakan agar total dayanya sama dengan ragam deret
    RR. Dengan begitu daya LF dan HF kedua metode bisa dibandingkan langsung.
    Rasio LF/HF sendiri tidak terpengaruh penskalaan apa pun.
    """
    cfg = cfg or settings.frequency
    nan = {"lf_ls": np.nan, "hf_ls": np.nan, "lf_hf_ls": np.nan}
    if rr_ms.size < _MIN_BEATS:
        return nan

    t = _beat_times(rr_ms)
    x = rr_ms - np.mean(rr_ms)          # buang komponen DC
    if np.allclose(x, 0):
        return nan

    # Grid frekuensi rapat sepanjang pita yang diminati.
    freq = np.linspace(cfg.lf_band[0], cfg.hf_band[1], 512)
    pgram = lombscargle(t, x, 2.0 * np.pi * freq, precenter=True)

    # Penskalaan Parseval: total luas kurva dibuat sama dengan ragam sinyal.
    area = np.trapezoid(pgram, freq)
    if area <= 0:
        return nan
    psd = pgram * (np.var(x, ddof=1) / area)

    lf = _band_power(freq, psd, cfg.lf_band)
    hf = _band_power(freq, psd, cfg.hf_band)
    return {
        "lf_ls": lf,
        "hf_ls": hf,
        "lf_hf_ls": lf / hf if hf and hf > 0 else np.nan,
    }


def frequency_features(rr_ms: np.ndarray,
                       cfg: FrequencyConfig | None = None) -> dict[str, float]:
    """Hitung kedua metode sekaligus untuk satu segmen."""
    return {**welch_bands(rr_ms, cfg), **lombscargle_bands(rr_ms, cfg)}
