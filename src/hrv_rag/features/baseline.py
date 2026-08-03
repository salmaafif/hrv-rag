"""
baseline.py — Acuan personal tiap subjek dan perhitungan reaktivitas.

Ini penerapan langsung Aturan Wajib #2: yang bermakna bukan "RMSSD = 22 ms",
melainkan "RMSSD 35% DI BAWAH baseline orang ini". Nilai HRV terlalu
individual — dipengaruhi usia, jenis kelamin, ritme pernapasan, postur, dan
kafein — sehingga ambang absolut lintas orang bisa menyesatkan.

Satu-satunya kelas di paket `features` ada di sini, dan itu disengaja
(keputusan K12): `BaselineProfile` MENYIMPAN acuan satu subjek lalu dipakai
berulang untuk banyak segmen. Modul lain di paket ini cukup berupa fungsi
murni karena tidak menyimpan keadaan apa pun.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .frequency_domain import FREQ_FEATURES
from .time_domain import TIME_FEATURES

#: Fitur yang dibandingkan terhadap baseline.
COMPARED_FEATURES: tuple[str, ...] = TIME_FEATURES + FREQ_FEATURES


@dataclass
class BaselineProfile:
    """
    Acuan HRV satu subjek, diringkas dari fase kalibrasi.

    Atribut:
        subject   : ID subjek
        values    : nilai acuan per fitur
        spread    : jarak antar-kuartil (IQR) per fitur — ukuran seberapa
                    stabil acuannya; IQR besar berarti baseline goyah dan
                    reaktivitas yang dihitung darinya kurang bisa dipercaya
        n_segments: jumlah segmen kalibrasi yang membentuk acuan ini
    """

    subject: str
    values: dict[str, float]
    spread: dict[str, float] = field(default_factory=dict)
    n_segments: int = 0

    # ------------------------------------------------------------- pembuat
    @classmethod
    def from_segments(cls, subject: str,
                      calibration_features: pd.DataFrame) -> "BaselineProfile":
        """
        Bangun acuan dari tabel fitur segmen fase kalibrasi.

        Dipakai MEDIAN, bukan rata-rata. Alasannya: satu segmen yang
        sinyalnya agak berisik bisa menggeser rata-rata cukup jauh, sedangkan
        median hampir tidak bergeming. Karena seluruh angka reaktivitas
        dibagi dengan acuan ini, kestabilannya menentukan kestabilan semua
        angka sesudahnya.
        """
        if calibration_features.empty:
            raise ValueError(
                f"{subject}: tidak ada segmen kalibrasi yang lolos mutu, "
                f"baseline tidak dapat dibentuk."
            )

        values, spread = {}, {}
        for feat in COMPARED_FEATURES:
            if feat not in calibration_features.columns:
                continue
            col = calibration_features[feat].dropna()
            if col.empty:
                continue
            values[feat] = float(col.median())
            spread[feat] = float(col.quantile(0.75) - col.quantile(0.25))

        return cls(subject=subject, values=values, spread=spread,
                   n_segments=len(calibration_features))

    # ---------------------------------------------------------- pemakaian
    def reactivity(self, features: dict[str, float]) -> dict[str, float]:
        """
        Perubahan relatif satu segmen terhadap acuan, dalam persen.

            reaktivitas = (nilai_segmen - nilai_acuan) / nilai_acuan x 100

        Negatif berarti di bawah baseline, positif di atas baseline.

        PENTING — kode berhenti di sini. Tidak ada penggabungan menjadi satu
        "skor tekanan", karena memadukan kelima angka ini justru tugas LLM
        yang berbekal knowledge base. Kalau kode yang menggabungkan, LLM
        tinggal membaca ambang dan seluruh pendekatan RAG kehilangan
        alasan keberadaannya.
        """
        out: dict[str, float] = {}
        for feat, ref in self.values.items():
            if feat not in features:
                continue
            value = features[feat]
            if ref in (0, None) or np.isnan(ref) or np.isnan(value):
                out[f"delta_pct_{feat}"] = np.nan
            else:
                out[f"delta_pct_{feat}"] = (value - ref) / ref * 100.0
        return out

    def relative_spread(self, feature: str) -> float:
        """
        IQR dibagi nilai acuan — seberapa goyah baseline untuk fitur ini.

        Dipakai sebagai peringatan: kalau nilainya besar, reaktivitas yang
        dihitung dari acuan tersebut perlu ditafsirkan lebih hati-hati.
        """
        ref = self.values.get(feature)
        iqr = self.spread.get(feature)
        if not ref or iqr is None or ref == 0:
            return float("nan")
        return iqr / abs(ref)

    def describe(self) -> str:
        rmssd = self.values.get("rmssd", float("nan"))
        return (f"baseline {self.subject}: {self.n_segments} segmen, "
                f"RMSSD acuan {rmssd:.1f} ms "
                f"(IQR relatif {self.relative_spread('rmssd'):.0%})")
