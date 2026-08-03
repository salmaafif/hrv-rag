"""
dynamics.py — Pemulihan, ketahanan, dan urutan pemicu sepanjang sesi.

Beda dengan modul fitur lain: di sini yang dilihat bukan satu segmen,
melainkan HUBUNGAN antar segmen sepanjang waktu.

Rancangan menempatkan pemulihan dan indeks ketahanan pada kolom "Kode
(formula)", jadi keduanya memang dihitung deterministik di sini — berbeda
dengan label tingkat tekanan yang tetap jadi wewenang LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from ..config.settings import DynamicsConfig, settings


class ResilienceQuadrant(str, Enum):
    """
    Empat kemungkinan gabungan reaktivitas dan pemulihan.

    Sengaja BUKAN skor 0-100. Angka seperti "ketahanan 72" hanya bermakna
    bila ada pembanding, dan pembanding itu mengharuskan perbandingan antar
    orang — persis yang dilarang Aturan Wajib #2. Kuadran menyampaikan
    informasi yang sama tanpa berpura-pura presisi.
    """

    HIGH = "ketahanan tinggi"          # reaktivitas kecil, pemulihan cepat
    HELD_IN = "tenang tapi tertahan"   # reaktivitas kecil, pemulihan lambat
    FLEXIBLE = "reaktif tapi lentur"   # reaktivitas besar, pemulihan cepat
    LOW = "ketahanan rendah"           # reaktivitas besar, pemulihan lambat


@dataclass(frozen=True)
class RecoveryResult:
    """Hasil perhitungan pemulihan satu pertanyaan."""

    percent: float | None      # None = tidak dapat dihitung
    reason: str = ""           # penjelasan bila None

    @property
    def is_computable(self) -> bool:
        return self.percent is not None


def recovery_percent(baseline: float, stressed: float, recovered: float,
                     cfg: DynamicsConfig | None = None) -> RecoveryResult:
    """
    Berapa persen simpangan yang sudah dipulihkan pada segmen jeda.

        pemulihan = (nilai_tertekan - nilai_jeda) / (nilai_tertekan - baseline) x 100

    Membacanya:
        100%  = kembali penuh ke baseline
        > 100% = melampaui baseline (kompensasi berlebih)
        0%    = tidak bergerak sama sekali
        < 0%  = justru makin menjauh dari baseline

    Contoh nyata dengan angka S2 — baseline RMSSD 56,8 ms turun ke 31,7 ms
    saat tertekan (simpangan 25,1 ms). Bila saat jeda naik ke 45,0 ms, maka
    yang sudah dipulihkan 13,3 dari 25,1, yaitu 53%.

    PENGAMAN. Bila pertanyaannya nyaris tidak memicu apa-apa, penyebut
    (nilai_tertekan - baseline) mendekati nol dan hasil pembagiannya meledak
    menjadi angka tak bermakna. Karena itu perhitungan hanya dilakukan bila
    simpangannya minimal `min_deviation_ratio` dari baseline. Bila tidak,
    hasilnya dinyatakan TIDAK DAPAT DIHITUNG — bukan diisi nol, sebab nol
    berarti "tidak pulih sama sekali", klaim yang sama sekali berbeda.
    """
    cfg = cfg or settings.dynamics

    if any(v is None or np.isnan(v) for v in (baseline, stressed, recovered)):
        return RecoveryResult(None, "ada nilai yang kosong")
    if baseline == 0:
        return RecoveryResult(None, "baseline nol")

    deviation = stressed - baseline
    if abs(deviation) / abs(baseline) < cfg.min_deviation_ratio:
        return RecoveryResult(
            None,
            f"reaksi terlalu kecil ({abs(deviation) / abs(baseline):.1%} "
            f"< {cfg.min_deviation_ratio:.0%})",
        )

    return RecoveryResult(float((stressed - recovered) / deviation * 100.0))


def resilience_quadrant(reactivity_pct: float, recovery_pct: float | None,
                        cfg: DynamicsConfig | None = None
                        ) -> ResilienceQuadrant | None:
    """
    Tempatkan satu sesi ke kuadran ketahanan.

    Memakai NILAI MUTLAK reaktivitas, karena yang dinilai adalah besar
    goncangannya — arah naik/turun sudah ditentukan jenis fiturnya (RMSSD
    turun saat tertekan, LF/HF naik).

    Mengembalikan None bila pemulihan tidak dapat dihitung: tanpa salah satu
    sumbu, kuadrannya tidak bisa ditentukan, dan menebak sumbu yang hilang
    akan membuat kesimpulan seolah lebih pasti daripada datanya.
    """
    cfg = cfg or settings.dynamics
    if recovery_pct is None or np.isnan(reactivity_pct):
        return None

    strong = abs(reactivity_pct) >= cfg.reactivity_threshold_pct
    fast = recovery_pct >= cfg.recovery_threshold_pct

    if strong and fast:
        return ResilienceQuadrant.FLEXIBLE
    if strong and not fast:
        return ResilienceQuadrant.LOW
    if not strong and fast:
        return ResilienceQuadrant.HIGH
    return ResilienceQuadrant.HELD_IN


def rank_by_reactivity(features: pd.DataFrame,
                       cfg: DynamicsConfig | None = None) -> pd.DataFrame:
    """
    Urutkan segmen dari yang paling memicu ke yang paling tidak.

    Inilah dasar "dinamika per pertanyaan": pertanyaan mana yang paling
    mengguncang, pada orang yang sama. Perbandingannya di dalam sesi orang
    itu sendiri, jadi tidak ada perbandingan antar individu.

    Seluruhnya deterministik — dihitung kode, bukan LLM. Artinya urutan ini
    tidak berubah walau model bahasanya diganti.
    """
    cfg = cfg or settings.dynamics
    col = f"delta_pct_{cfg.primary_feature}"
    if col not in features.columns:
        raise KeyError(f"Kolom {col} tidak ada — reaktivitas belum dihitung.")

    ranked = features.copy()
    # RMSSD MENURUN saat tertekan, jadi yang paling memicu adalah delta
    # paling negatif. Diurutkan menaik supaya baris pertama = paling memicu.
    ranked = ranked.sort_values(col, ascending=True)
    ranked["peringkat_pemicu"] = range(1, len(ranked) + 1)
    return ranked
