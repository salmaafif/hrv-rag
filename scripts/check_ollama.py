"""
check_ollama.py — verify a self-hosted model before trusting a batch run to it.

    python scripts/check_ollama.py

Run this every time the Vast.ai instance is restarted. It exists because the ways
a self-hosted backend goes wrong are mostly QUIET: the run completes, the JSON
parses, the report reads well, and the answer was produced without ever seeing the
retrieved knowledge. Four things are checked, in the order they fail:

1. **Reachable and authenticated.** A stopped instance and a wrong API key look
   nothing alike in their error messages, so both are reported plainly.
2. **The model is actually there.** Ollama serves whatever it has; a mistyped tag
   is a 404 here rather than a result that names a model which never ran.
3. **The schema is enforced.** Ollama below 0.5 accepts `format` and ignores it,
   answering in prose. Everything downstream then depends on parsing luck.
4. **The context window fits a real prompt.** This is the dangerous one. A prompt
   longer than `num_ctx` is truncated, not refused — and the retrieved chunks sit
   in the middle of the prompt, so they are what falls off the end. The system
   would keep producing confident, well-formed answers while having quietly
   stopped being a RAG system.

The timing at the end is not decoration: it decides whether the ablations are a
coffee break or an overnight job.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# The Windows console defaults to a legacy codepage, which turns the dashes and
# accented characters in this report into mojibake. Since the whole point of the
# script is to be READ, the stream is switched to UTF-8 first.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hrv_rag.config.settings import settings                    # noqa: E402
from hrv_rag.core.schemas import LLMResponse                     # noqa: E402
from hrv_rag.rag.llm import OllamaInterpreter                    # noqa: E402
from hrv_rag.rag.retrieval import KBIndex                        # noqa: E402

#: Rough characters-per-token for English prose. Deliberately optimistic: a low
#: divisor UNDERSTATES the token count, so a prompt this estimate calls safe could
#: still be too long. It is a smoke alarm, not a token counter.
CHARS_PER_TOKEN = 3.5


def main() -> int:
    print("\n=== Memeriksa model swa-inang (Ollama via OpenWebUI) ===\n")

    try:
        interpreter = OllamaInterpreter()
    except RuntimeError as exc:
        print(f"  GAGAL sebelum menghubungi server:\n    {exc}\n")
        return 1

    print(f"  Alamat  : {interpreter.base_url}")
    print(f"  Model   : {interpreter.model}")
    print("  Menghubungi server (panggilan pertama memuat bobot ke VRAM — "
          "bisa beberapa menit)...\n")

    started = time.monotonic()
    try:
        report = interpreter.check()
    except Exception as exc:                                     # noqa: BLE001
        print(f"  GAGAL: {type(exc).__name__}: {str(exc)[:300]}\n")
        print("  Yang biasanya menyebabkan ini:")
        print("    - instance Vast.ai sedang mati, atau alamatnya berubah "
              "setelah dinyalakan ulang")
        print("    - OPENWEBUI_API_KEY salah atau sudah dicabut")
        print("    - modelnya belum di-pull di instance itu\n")
        return 1
    elapsed = time.monotonic() - started

    print(f"  Terhubung, skema JSON dipatuhi  ({elapsed:.1f} dtk)")
    print(f"  Digest  : {report['digest']}")
    print(f"  Dicatat sebagai: {report['model_label']}")
    print(f"  seed={report['seed']}  num_ctx={report['num_ctx']}\n")

    # --- does a real prompt fit in the context window? ---
    print("=== Apakah prompt sungguhan muat di jendela konteks? ===\n")
    try:
        index = KBIndex.load()
        chunk_chars = sum(len(c.text) for c in index.chunks)
        top_k = min(settings.rag.top_k, len(index.chunks))
        largest = sorted((len(c.text) for c in index.chunks), reverse=True)[:top_k]
        # Prompt template plus the feature block; measured generously.
        overhead_chars = 4000
        worst_chars = sum(largest) + overhead_chars
        worst_tokens = int(worst_chars / CHARS_PER_TOKEN)

        print(f"  KB          : {len(index.chunks)} chunk, {chunk_chars:,} karakter")
        print(f"  Prompt terburuk: ~{worst_chars:,} karakter "
              f"(~{worst_tokens:,} token, k={top_k})")
        print(f"  num_ctx     : {report['num_ctx']:,} token")

        if worst_tokens > report["num_ctx"] * 0.8:
            print("\n  PERINGATAN: prompt terpanjang memakai lebih dari 80% "
                  "jendela konteks.")
            print("  Naikkan OllamaConfig.num_ctx. Kalau terlampaui, prompt "
                  "DIPOTONG tanpa pesan galat —")
            print("  dan yang terpotong adalah chunk pengetahuan di tengah "
                  "prompt, bukan instruksinya.\n")
        else:
            headroom = report["num_ctx"] / max(worst_tokens, 1)
            print(f"  Lapang — jendela konteks {headroom:.1f}x prompt "
                  f"terpanjang.\n")
    except FileNotFoundError:
        print("  (indeks KB belum dibangun; lewati pemeriksaan ini)\n")

    # --- how fast, in the shape the pipeline actually uses? ---
    print("=== Kecepatan pada bentuk jawaban yang sebenarnya ===\n")
    prompt = (
        "You are assessing physiological stress from HRV features.\n"
        "CONTEXT:\n[KB-RMSSD-01] RMSSD reflects vagal activity and falls "
        "under acute stress.\n"
        "MEASUREMENTS: RMSSD 31.7 ms, 24% below the personal baseline. "
        "Mean HR 88 bpm, 12% above baseline. Modality: PPG.\n"
        "Return the required JSON. Indonesian for the user-facing fields."
    )
    started = time.monotonic()
    try:
        response = interpreter.interpret_as(prompt, LLMResponse, temperature=0.0)
    except Exception as exc:                                     # noqa: BLE001
        print(f"  GAGAL menghasilkan jawaban berskema penuh: "
              f"{type(exc).__name__}: {str(exc)[:300]}\n")
        return 1
    elapsed = time.monotonic() - started

    print(f"  Satu panggilan: {elapsed:.1f} dtk")
    print(f"  level={response.stress_level.value}  "
          f"confidence={response.confidence}")
    print(f"  Bahasa Indonesia: {response.user_summary[:90]}...\n")

    print(f"  Perkiraan: 100 panggilan ~ {elapsed * 100 / 60:.0f} menit, "
          f"500 panggilan ~ {elapsed * 500 / 3600:.1f} jam\n")

    print("  Periksa sendiri kalimat Indonesia di atas. Model kecil sering "
          "lolos skema tapi")
    print("  menulis Indonesia yang kaku — pemakai KARIRLINK yang membacanya, "
          "bukan penguji.\n")

    print("Siap. Jalankan dengan:  LLM_PROVIDER=ollama python scripts/...\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
