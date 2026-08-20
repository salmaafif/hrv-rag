"""
compare_llm.py — the same segment, the same prompt, several models. Read and judge.

    python scripts/compare_llm.py                       # Gemini vs the local model
    python scripts/compare_llm.py --models gpt-oss:20b,qwen3.5:35b
    python scripts/compare_llm.py --segment 12 --no-gemini

WHY THIS EXISTS. Comparing backends by running each on whatever prompt was handy
proves nothing: a difference in the answers might be a difference in the models,
or it might be a difference in what they were asked. Everything upstream of the
model is therefore computed ONCE — the same segment, the same retrieval, the same
assembled prompt — and only the model varies. That is the only arrangement in
which the outputs can be set beside each other and mean something.

TWO KINDS OF VERDICT, AND ONLY ONE OF THEM IS MINE TO GIVE.

  Measurable, and checked here:
    - did it obey the JSON schema at all
    - did the guards catch invented numbers or fabricated citations
    - did it cite chunks that were actually retrieved
    - did its label agree with the frozen scoring rule
    - how long it took

  NOT measurable, and printed for you to read:
    - whether the Indonesian is natural enough for a KARIRLINK user
    - whether it respects K4 — no feature names, no numbers, no clinical jargon

The second list is the one that decides this, and no script can score it. The
whole output is printed rather than summarised so the judging is done on the text
a user would actually see.

Every raw response is written to `outputs/llm_comparison/` (BACKLOG U4.5), so a
claim made about a model later can be checked against what it really said.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings        # noqa: E402
from hrv_rag.features.extractor import load_features             # noqa: E402
from hrv_rag.features.stress_level import classify               # noqa: E402
from hrv_rag.rag.llm import GeminiInterpreter, OllamaInterpreter  # noqa: E402
from hrv_rag.rag.pipeline import AssessmentPipeline              # noqa: E402
from hrv_rag.rag.retrieval import KBIndex                        # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
from run_assessment import row_to_input                          # noqa: E402

FEATURES_CSV = OUTPUTS_DIR / "features_wesad_ecg_dev.csv"
OUT_DIR = OUTPUTS_DIR / "llm_comparison"


def pick_segment(index: int | None) -> pd.Series:
    """
    One stressed segment, so there is something for the model to interpret.

    A resting segment would have every model saying "nothing much happened",
    which distinguishes them not at all.
    """
    data = load_features(FEATURES_CSV)
    stressed = data[data.phase == "question"].reset_index(drop=True)
    if stressed.empty:
        raise SystemExit(f"{FEATURES_CSV.name} holds no question-phase segment.")
    return stressed.iloc[(index if index is not None else 0) % len(stressed)]


def run_one(label: str, interpreter, index: KBIndex, data) -> dict:
    """Assess the segment with one backend and collect everything comparable."""
    pipeline = AssessmentPipeline(index=index, interpreter=interpreter)
    started = time.monotonic()
    try:
        assessment = pipeline.assess(data)
    except Exception as exc:                                     # noqa: BLE001
        return {"label": label, "error": f"{type(exc).__name__}: {exc}"}
    elapsed = time.monotonic() - started

    response = assessment.response
    return {
        "label": label,
        "model": assessment.model,
        "seconds": round(elapsed, 1),
        "level": response.stress_level.value,
        "confidence": response.confidence,
        "references": response.references,
        "retrieved": assessment.retrieved_ids,
        "invented_numbers": assessment.invented_numbers,
        "unknown_references": assessment.unknown_references,
        "user_summary": response.user_summary,
        "user_recommendation": response.user_recommendation,
        "reasoning": response.reasoning,
        "uncertainty_notes": response.uncertainty_notes,
    }


def main() -> int:
    args = sys.argv[1:]
    segment = None
    models = ["gpt-oss:20b"]
    use_gemini = "--no-gemini" not in args

    for i, a in enumerate(args):
        if a == "--segment" and i + 1 < len(args):
            segment = int(args[i + 1])
        if a == "--models" and i + 1 < len(args):
            models = [m.strip() for m in args[i + 1].split(",") if m.strip()]

    row = pick_segment(segment)
    data = row_to_input(row)
    index = KBIndex.load()

    reactivity = {k: v for k, v in data.reactivity.items()}
    verdict = classify(reactivity, settings.stress_rule)

    print("\n" + "=" * 74)
    print("SEGMEN YANG DINILAI — sama persis untuk semua model")
    print("=" * 74)
    print(f"  subjek {data.session_id}  fase {data.phase.value}  "
          f"segmen {data.segment_index}  modalitas {data.modality.value}")
    print(f"  RMSSD {data.features.get('rmssd', float('nan')):.1f} ms   "
          f"HR {data.features.get('mean_hr', float('nan')):.1f} bpm")
    print(f"  reaktivitas RMSSD {reactivity.get('delta_pct_rmssd', float('nan')):+.1f}%   "
          f"HR {reactivity.get('delta_pct_mean_hr', float('nan')):+.1f}%")
    print(f"\n  ATURAN SKOR (yang menentukan label sungguhan): "
          f"{verdict.level.value.upper()}")
    print("  LLM tidak menyentuh label ini — ia hanya menarasikan. Kolom 'level'")
    print("  di bawah adalah tebakan model, dipakai hanya untuk melihat apakah ia")
    print("  sejalan dengan pengukuran.\n")

    runs = []
    if use_gemini:
        print("  menjalankan Gemini...")
        runs.append(run_one("Gemini", GeminiInterpreter(), index, data))
    for tag in models:
        print(f"  menjalankan {tag}...")
        try:
            runs.append(run_one(tag, OllamaInterpreter(model=tag), index, data))
        except Exception as exc:                                 # noqa: BLE001
            runs.append({"label": tag, "error": f"{type(exc).__name__}: {exc}"})

    print("\n" + "=" * 74)
    print("YANG BISA DIUKUR")
    print("=" * 74)
    print(f"  {'model':<16}{'dtk':>6}{'level':>10}{'yakin':>7}"
          f"{'angka karangan':>16}{'rujukan palsu':>15}")
    print("  " + "-" * 70)
    for r in runs:
        if "error" in r:
            print(f"  {r['label']:<16}  GAGAL: {r['error'][:46]}")
            continue
        agree = "=" if r["level"] == verdict.level.value else "≠"
        print(f"  {r['label']:<16}{r['seconds']:>6.1f}{r['level']:>9}{agree}"
              f"{r['confidence']:>7.2f}{len(r['invented_numbers']):>16}"
              f"{len(r['unknown_references']):>15}")
    print("\n  'angka karangan' dan 'rujukan palsu' berasal dari rag/guards.py.")
    print("  Selain nol berarti model mengarang sesuatu yang tidak ada di prompt.")

    print("\n" + "=" * 74)
    print("YANG HARUS KAMU BACA SENDIRI")
    print("=" * 74)
    print("  K4: pengguna tidak boleh melihat nama fitur, angka, atau istilah klinis.")
    print("  Tidak ada skrip yang bisa menilai ini. Baca, lalu putuskan.\n")
    for r in runs:
        if "error" in r:
            continue
        print("  " + "─" * 70)
        print(f"  {r['label']}   ({r['model']})")
        print("  " + "─" * 70)
        print(f"  RINGKASAN : {r['user_summary']}")
        print(f"  SARAN     : {r['user_recommendation']}")
        print(f"  rujukan   : {r['references']}  (terambil: {r['retrieved']})")
        if r["invented_numbers"]:
            print(f"  ANGKA KARANGAN: {r['invented_numbers']}")
        if r["unknown_references"]:
            print(f"  RUJUKAN PALSU : {r['unknown_references']}")
        print()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUT_DIR / f"compare-{data.session_id}-seg{data.segment_index}-{stamp}.json"
    path.write_text(json.dumps({
        "segment": {"subject": data.session_id, "phase": data.phase.value,
                    "segment": data.segment_index,
                    "features": data.features, "reactivity": reactivity},
        "rule_label": verdict.level.value,
        "runs": runs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Keluaran mentah disimpan: {path.relative_to(REPO)}")
    print("  (U4.5 — supaya klaim tentang sebuah model bisa dicek ulang nanti)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
