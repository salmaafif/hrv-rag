"""
train_dl.py — the deep-learning comparator, run under Leave-One-Subject-Out.

    python scripts/train_dl.py                # LOSO + the permutation control
    python scripts/train_dl.py --no-permute   # skip the control (not advised)
    python scripts/train_dl.py --rebuild      # ignore the cached tensors

TWO RUNS, NOT ONE. The real labels tell you how well the model does; the shuffled
labels tell you whether that number can be believed. With the association between
sequence and label destroyed, an honest pipeline scores at chance. Anything higher
is leakage — and no amount of careful reasoning about the splits would reveal it,
because leakage looks exactly like success.

The pooled metrics come from `hrv_rag.evaluation.metrics.evaluate_classification`,
the same function that scored the frozen rule. Two branches computing their
headline figures with different code could not be compared at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from hrv_dl.dataset import SequenceDataset, build_subjects        # noqa: E402
from hrv_dl.models import CNN1D                                    # noqa: E402
from hrv_dl.train import (TrainConfig, check_no_leakage,           # noqa: E402
                          permute_labels, run_loso)
from hrv_rag.config.settings import OUTPUTS_DIR, settings          # noqa: E402

CACHE = OUTPUTS_DIR / "dl_sequences_wesad_ecg.npz"

#: The bar the comparator has to clear, from BACKLOG U3.1 and T5.2. Printed
#: alongside so the comparison is on screen rather than left to memory.
RULE_BASELINE = {
    "aturan RMSSD-saja (293 segmen dev)": 0.742,
    "aturan RMSSD-atau-HR (293 segmen dev)": 0.828,
    "aturan beku, holdout 10 subjek tersegel": 0.839,
}


def load_dataset(rebuild: bool) -> SequenceDataset:
    """Build once, reuse afterwards — the signal pipeline is the slow part."""
    if CACHE.exists() and not rebuild:
        z = np.load(CACHE, allow_pickle=True)
        print(f"Memakai tensor tersimpan: {CACHE.name}\n")
        return SequenceDataset(
            x=z["x"], mask=z["mask"], y=z["y"], subjects=z["subjects"],
            phases=z["phases"], n_beats=z["n_beats"], normalised=bool(z["normalised"]),
        )

    print("Membangun deret dari sinyal WESAD (sekali saja)...\n")
    subjects = list(settings.split.dev_subjects) + list(settings.split.test_subjects)
    data = build_subjects(sorted(subjects), normalise=True, verbose=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        CACHE, x=data.x, mask=data.mask, y=data.y, subjects=data.subjects,
        phases=data.phases, n_beats=data.n_beats, normalised=data.normalised,
    )
    print(f"\nDisimpan ke {CACHE.name}\n")
    return data


def main() -> int:
    rebuild = "--rebuild" in sys.argv
    permute = "--no-permute" not in sys.argv

    data = load_dataset(rebuild)
    cfg = TrainConfig()

    print("=" * 72)
    print("DATA")
    print("=" * 72)
    print(f"  {data.summary()}")
    print(f"  model: 1D-CNN, {CNN1D().n_parameters():,} parameter")
    print(f"  rasio parameter terhadap segmen: "
          f"{CNN1D().n_parameters() / len(data):,.0f} : 1")
    print(f"  seed {cfg.seed}, dropout {cfg.dropout}, "
          f"weight decay {cfg.weight_decay}, patience {cfg.patience}\n")

    # Cheap, and it fails loudly before an hour of training rather than after.
    check_no_leakage(data, cfg)
    print("  Pemeriksaan kebocoran subjek: LOLOS "
          "(uji, validasi, dan latih saling lepas di setiap fold)\n")

    print("=" * 72)
    print("LOSO — LABEL SEBENARNYA")
    print("=" * 72)
    real = run_loso(data, cfg, verbose=True)
    print(f"\n{real.summary()}\n")

    print("  F1 per kelas:", {k: round(v, 3) for k, v in real.report.per_class_f1.items()})
    print("  confusion   :", real.report.confusion, f"({real.report.labels_order})\n")

    print("  Pembanding yang harus dilampaui — macro-F1:")
    for name, score in RULE_BASELINE.items():
        delta = real.report.macro_f1 - score
        verdict = "di atas" if delta > 0 else "di bawah"
        print(f"    {name:<44} {score:.3f}   ({verdict} {abs(delta):.3f})")
    print()

    if not permute:
        print("  Uji permutasi DILEWATI. Angka di atas belum terverifikasi.\n")
        return 0

    print("=" * 72)
    print("KONTROL — LABEL DIACAK")
    print("=" * 72)
    print("  Kaitan sekuens-label sudah dihancurkan. Pipeline yang jujur")
    print("  seharusnya turun ke sekitar tebakan acak di sini.\n")
    shuffled = run_loso(permute_labels(data, seed=cfg.seed), cfg,
                        label_permuted=True, verbose=True)
    print(f"\n{shuffled.summary()}\n")

    print("=" * 72)
    print("PUTUSAN")
    print("=" * 72)
    gap = real.report.macro_f1 - shuffled.report.macro_f1
    print(f"  macro-F1 sebenarnya {real.report.macro_f1:.3f}  vs  "
          f"acak {shuffled.report.macro_f1:.3f}   selisih {gap:+.3f}")
    if shuffled.report.macro_f1 > 0.60:
        print("\n  PERINGATAN: label acak pun terpelajari. Ada yang bocor —")
        print("  jangan laporkan angka apa pun sebelum sebabnya ditemukan.")
    elif gap < 0.05:
        print("\n  Model tidak belajar lebih banyak daripada dari label acak.")
        print("  Itu hasil yang sah dan patut dilaporkan, bukan bug yang harus ditambal.")
    else:
        print("\n  Label acak tidak terpelajari, label sebenarnya terpelajari.")
        print("  Angkanya bisa dipercaya sejauh yang bisa dijamin pembagian data.")
    print(f"\n  Rata-rata selisih latih-validasi: {real.mean_overfit_gap:+.3f}")
    print("  (mendekati nol = model belajar sedikit; sangat besar = menghafal)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
