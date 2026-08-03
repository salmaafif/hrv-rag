"""
run_features.py — Jalankan Tahap 2 pada subjek pengembangan WESAD.

Menghasilkan satu CSV berisi fitur per segmen beserta reaktivitasnya, lalu
mencetak ringkasan untuk pemeriksaan cepat.

Cara pakai:
    python scripts/run_features.py            # 5 subjek pengembangan
    python scripts/run_features.py S2
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings        # noqa: E402
from hrv_rag.core.types import Modality, Phase                   # noqa: E402
from hrv_rag.datasets.wesad import WESADLoader                   # noqa: E402
from hrv_rag.features.baseline import BaselineProfile            # noqa: E402
from hrv_rag.features.extractor import (extract_features,        # noqa: E402
                                        to_display_columns)
from hrv_rag.preprocessing.ecg import ECGPreprocessor            # noqa: E402


def process_subject(subject: str) -> pd.DataFrame:
    """Satu subjek: sinyal -> fitur -> reaktivitas terhadap baseline sendiri."""
    loader = WESADLoader(subject)
    pre = ECGPreprocessor(sampling_rate=loader.sampling_rate(Modality.ECG))

    print(f"\n--- {subject} ---")
    tables = {}
    for phase in (Phase.CALIBRATION, Phase.QUESTION):
        raw = loader.load_phase_signal(subject, phase, Modality.ECG)
        series = pre.run(raw, subject=subject, phase=phase)
        df, seg_result = extract_features(series)
        tables[phase] = df
        print(f"  {phase.value:12s}: {seg_result.summary()}")

    # Baseline dibentuk HANYA dari fase kalibrasi subjek ini sendiri.
    baseline = BaselineProfile.from_segments(subject, tables[Phase.CALIBRATION])
    print(f"  {baseline.describe()}")

    # Reaktivitas dihitung untuk semua fase, termasuk kalibrasi itu sendiri
    # — segmen kalibrasi seharusnya mendekati 0%, dan itu berguna sebagai
    # pemeriksaan kewarasan.
    combined = pd.concat(tables.values(), ignore_index=True)
    reactivity = pd.DataFrame(
        [baseline.reactivity(row) for row in combined.to_dict("records")]
    )
    return pd.concat([combined, reactivity], axis=1)


def main(subjects: list[str]) -> None:
    if not subjects:
        subjects = list(settings.split.dev_subjects)
        print(f"Subjek pengembangan: {', '.join(subjects)}")
        print("(10 subjek uji disegel — BACKLOG U4.1)")

    all_rows = [process_subject(s) for s in subjects]
    data = pd.concat(all_rows, ignore_index=True)

    # --- Ringkasan reaktivitas per fase ---
    # Dipakai MEDIAN, bukan rata-rata. Persentase perubahan tidak simetris:
    # penurunan mentok di -100% sedangkan kenaikan tak terbatas (teramati
    # sampai +442% pada S10). Rata-rata karenanya tertarik ke atas oleh ekor
    # kanan dan bisa membalik kesimpulan — pada data ini, rata-rata pNN50
    # tampak +61,8% padahal median-nya -61,2%.
    cols = ["delta_pct_rmssd", "delta_pct_pnn50", "delta_pct_hf_welch",
            "delta_pct_lf_hf_welch", "delta_pct_mean_hr"]
    cols = [c for c in cols if c in data.columns]
    print("\n=== Median reaktivitas per fase (%) ===")
    print(data.groupby("fase")[cols].median().round(1).to_string())

    # --- Arah respons per subjek ---
    # Diperiksa per orang, bukan digabung, karena satu subjek yang berpola
    # terbalik bisa tersamarkan di angka gabungan.
    print("\n=== Arah respons per subjek (median, fase pertanyaan) ===")
    q = data[data["fase"] == "pertanyaan"]
    per_subject = q.groupby("subjek")[cols].median().round(1)
    # Pola baku saat tertekan: RMSSD turun DAN detak jantung naik.
    per_subject["pola"] = [
        "sesuai teori" if r["delta_pct_rmssd"] < 0 and r["delta_pct_mean_hr"] > 0
        else "TERBALIK" if r["delta_pct_rmssd"] > 0 and r["delta_pct_mean_hr"] > 0
        else "campuran"
        for _, r in per_subject.iterrows()
    ]
    print(per_subject.to_string())

    # --- Perbandingan dua metode PSD (T2.12) ---
    print("\n=== Welch vs Lomb-Scargle: LF/HF ===")
    both = data[["lf_hf_welch", "lf_hf_ls"]].dropna()
    if not both.empty:
        corr = both["lf_hf_welch"].corr(both["lf_hf_ls"])
        rel = ((both["lf_hf_ls"] - both["lf_hf_welch"]).abs()
               / both["lf_hf_welch"]).median()
        print(f"  korelasi Pearson : {corr:.3f}")
        print(f"  selisih relatif median : {rel:.1%}")
        print(f"  rerata Welch {both['lf_hf_welch'].mean():.2f} | "
              f"rerata Lomb-Scargle {both['lf_hf_ls'].mean():.2f}")

    path = OUTPUTS_DIR / "fitur_wesad_ecg_dev.csv"
    to_display_columns(data).to_csv(path, index=False)
    print(f"\nCSV: {path}")
    print(f"Total segmen: {len(data)}")


if __name__ == "__main__":
    main(sys.argv[1:])
