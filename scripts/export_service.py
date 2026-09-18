"""
export_service.py — export the runnable HRV service into another directory.

WHY THIS EXISTS. The KARIRLINK monorepo needs the HRV service to run on every
teammate's machine (`apps/hrv-service`), the same way the face-expression
module lives in `apps/fer-service`. But this repository stays the research
home: the thesis pipeline, datasets, evaluation, and documentation do not
belong in the team repo, and the validated code must never be edited there —
a fork that drifts would silently detach the product from the numbers the
thesis reports.

So the copy is produced by THIS script, never by hand:

    python scripts/export_service.py "C:\\path\\to\\karirlink\\apps\\hrv-service"

Re-running it re-syncs the copy and stamps PROVENANCE.md with the source
commit. The rule for teammates is written into the exported README: edit in
hrv-rag, re-export — never edit the copy.

WHAT IS EXPORTED (and what deliberately is not):
  - src/hrv_rag/          the science library, byte-for-byte
  - backend/hrv_api/      the FastAPI surface
  - knowledge_base/, prompts/, data/processed/kb_index/
    (the KB index ships with the copy — 23x3072 floats, ~280 KB — so the
    service works without a Gemini key ever building an index)
  - pyproject.toml        so `pip install -e .` works identically
  - a service-only requirements.txt: scikit-learn / matplotlib / seaborn are
    evaluation-and-plots only and verified unimported on the service path
  - NOT exported: datasets, outputs, tests, docs, BACKLOG — research material;
    tests keep living (and running) here.

The directory layout is preserved exactly because `config/settings.py`
resolves KB/prompt/index paths as `parents[3]` of its own file — same shape,
zero code changes.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Everything the running service needs, relative to both roots.
TREES = [
    "src/hrv_rag",
    "backend/hrv_api",
    "knowledge_base",
    "prompts",
    "data/processed/kb_index",
]
FILES = ["pyproject.toml"]

#: Runtime dependencies only. Version pins copied from requirements.txt — the
#: pins ARE the claim (neurokit2 changes peak detection between minors).
REQUIREMENTS = """\
# requirements.txt — layanan HRV (hasil ekspor; JANGAN disunting di sini).
# Subset runtime dari requirements.txt hrv-rag: paket evaluasi & plot
# (scikit-learn, matplotlib, seaborn) tidak dibutuhkan layanan dan tidak
# diimpor di jalur layanan (diverifikasi grep saat ekspor dirancang).
neurokit2==0.2.13
numpy==2.2.6
scipy==1.15.3
pandas==2.3.3
google-genai==1.74.0
python-dotenv==1.2.2
httpx==0.28.1
fastapi==0.141.1
uvicorn==0.46.0
"""

ENV_EXAMPLE = """\
# Salin menjadi `.env` di folder ini, lalu isi.

# Kunci yang WAJIB dikirim pemanggil lewat header X-API-Key. Samakan dengan
# HRV_API_KEY di apps/backend/.env. Tanpa variabel ini layanan MENOLAK SEMUA.
HRV_API_KEYS=kunci-lokal

# Kunci Gemini — OPSIONAL. Tanpa kunci, label tekanan tetap keluar (dihitung
# aturan deterministik, luring); yang kosong hanya narasinya, dan
# meta.trustworthy menandainya. Jangan pernah commit nilai aslinya.
# GEMINI_API_KEY=

# Arsip sesi berizin — dua kunci: pengguna mencentang persetujuan DAN operator
# mengisi folder ini. Kunci operator ini SENGAJA dinyalakan di contoh sejak
# 1 Sep 2026: sesi yang GAGAL dianalisis pun ikut tersimpan (routes/session.py
# mengarsip di cabang except), dan tiga sesi uji nyata sudah hilang justru
# karena baris ini masih dikomentari. Menyalakannya sendirian tidak menyimpan
# apa pun — tanpa persetujuan pemanggil, archive_session() tetap mengembalikan
# None. Kosongkan bila memang tidak ingin mengarsip.
HRV_ARCHIVE_DIR=outputs/session_archive
"""

GITIGNORE = """\
.venv/
.env
__pycache__/
outputs/
*.egg-info/
"""

README = """\
# hrv-service — layanan analisis detak jantung (modul Stress Detection)

**SALINAN HASIL EKSPOR — jangan menyunting kode di folder ini.**
Sumbernya repo riset `hrv-rag` (Salma). Perubahan dibuat DI SANA lalu
diekspor ulang: `python scripts/export_service.py <path folder ini>`.
Alasannya bukan kerapian: angka validasi tugas akhir (macro-F1 0,871 pada
10 subjek tersegel) diukur pada kode ini persis — salinan yang disunting
diam-diam akan melepaskan produk dari angka yang dilaporkannya.
Commit sumber tercatat di `PROVENANCE.md`.

## Menjalankan

```powershell
python -m venv .venv
.\\.venv\\Scripts\\pip install -r requirements.txt
.\\.venv\\Scripts\\pip install -e .
copy .env.example .env   # lalu isi HRV_API_KEYS
.\\.venv\\Scripts\\python -m uvicorn hrv_api.app:app --app-dir backend --port 8010
```

Cek: `curl http://127.0.0.1:8010/health` → `{"status":"ok"}`.
Backend NestJS menunjuk ke sini lewat `HRV_API_URL` + `HRV_API_KEY` di
`apps/backend/.env` (port 8010 — 8000 milik AI Gateway).

## Yang perlu diketahui pemakai

- **Tanpa kunci Gemini layanan tetap berguna**: label tekanan per pertanyaan
  dihitung aturan deterministik (luring, identik tiap dijalankan); hanya
  narasi Bahasa Indonesia yang butuh Gemini, dan ketiadaannya ditandai jujur
  di `meta.trustworthy`.
- Kontrak masuk/keluar: `POST /api/v1/analyze/session` — lihat
  `docs/module-design/rancangan-rag-hrv.md` §4 di repo ini.
- Angka teknis (RMSSD dll.) ditahan secara bawaan dan tidak untuk kandidat.
- Tes perangkat lunak modul ini (397 tes) hidup dan dijalankan di repo
  sumbernya, bukan di salinan ini.
"""


def copy_tree(rel: str, target: Path) -> None:
    src = REPO / rel
    if not src.exists():
        raise SystemExit(
            f"{rel} tidak ada di sumber — untuk kb_index, bangun dulu lewat "
            f"scripts/build_kb_index.py"
        )
    dst = target / rel
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )


#: Not part of the export: someone else's virtual environment, their secrets, and
#: build leftovers. PROVENANCE.md is excluded from COMPARISON only — it carries a
#: timestamp, so it differs on every export by construction, and it is checked
#: separately in `check()`.
IGNORED_DIRS = {"__pycache__", ".venv", ".git"}
IGNORED_NAMES = {".env", "PROVENANCE.md"}


def _fingerprint(root: Path) -> dict[str, str]:
    """Every exported file under `root`, as relative path -> sha256 of its bytes."""
    prints: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if set(parts) & IGNORED_DIRS or path.name in IGNORED_NAMES:
            continue
        if path.suffix == ".pyc" or any(p.endswith(".egg-info") for p in parts):
            continue
        prints["/".join(parts)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return prints


def check(target: Path) -> int:
    """
    Prove the copy at `target` is still what this repository would export.

    WHY THIS EXISTS. The rule is that `apps/hrv-service` is generated, never typed
    into. A rule nobody can test is a rule that gets broken quietly: the copy has
    drifted before, and the drift is invisible — the service keeps running, and it
    keeps running code that no longer matches the numbers the thesis reports.

    So: export to a temporary folder, compare file by file, and exit non-zero on
    any difference. One command before a demo closes the whole class of problem.
    """
    if not target.is_dir():
        print(f"Tidak ada folder salinan di {target}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "hrv-service"
        export(fresh, announce=False)
        here, there = _fingerprint(fresh), _fingerprint(target)

    missing = sorted(set(here) - set(there))
    extra = sorted(set(there) - set(here))
    changed = sorted(f for f in set(here) & set(there) if here[f] != there[f])

    for label, files in (("hilang dari salinan", missing),
                         ("ada di salinan tapi bukan hasil ekspor", extra),
                         ("isinya berbeda", changed)):
        for name in files:
            print(f"{label}: {name}")

    if missing or extra or changed:
        print(f"\n{len(missing) + len(extra) + len(changed)} berkas berbeda. "
              "Sunting di hrv-rag lalu ekspor ulang; jangan menyunting salinannya.",
              file=sys.stderr)
        return 1

    # Identical content still leaves one question: exported from WHICH commit.
    stamped = ""
    provenance = target / "PROVENANCE.md"
    if provenance.exists():
        for line in provenance.read_text(encoding="utf-8").splitlines():
            if line.startswith("- Commit"):
                stamped = line.split("`")[1] if "`" in line else ""
    if stamped and stamped != head_commit():
        print(f"Isi salinan sama persis, tetapi dicap dari commit {stamped[:7]} "
              f"sedangkan HEAD sekarang {head_commit()[:7]}.")
        print("Itu wajar bila sejak ekspor tidak ada perubahan pada kode layanan.")
    else:
        print(f"Salinan di {target} sama persis dengan hasil ekspor dari repo ini.")
    return 0


def head_commit() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def export(target: Path, announce: bool = True) -> None:
    target.mkdir(parents=True, exist_ok=True)

    for rel in TREES:
        copy_tree(rel, target)
    for rel in FILES:
        shutil.copy2(REPO / rel, target / rel)

    (target / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (target / ".env.example").write_text(ENV_EXAMPLE, encoding="utf-8")
    (target / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (target / "README.md").write_text(README, encoding="utf-8")

    commit = head_commit()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (target / "PROVENANCE.md").write_text(
        "# Asal salinan ini\n\n"
        f"- Repo sumber : hrv-rag (repo riset TA Salma Afifa Azis)\n"
        f"- Commit      : `{commit}`\n"
        f"- Diekspor    : {stamp}\n"
        f"- Perintah    : `python scripts/export_service.py <folder ini>`\n\n"
        "Jangan menyunting kode di folder ini — sunting di hrv-rag lalu "
        "ekspor ulang. `README.md` menjelaskan alasannya.\n",
        encoding="utf-8",
    )

    if announce:
        print(f"Layanan diekspor ke {target}")
        print(f"Sumber: {commit}")


def main(argv: list[str] | None = None) -> int:
    """
    Export, or prove the existing copy still matches.

    Argument parsing is argparse rather than `sys.argv[1]` on purpose: the hand
    rolled version took ANY first argument as the destination folder, so a
    mistyped flag exported the whole service into a directory named `--help`.
    """
    parser = argparse.ArgumentParser(
        description="Ekspor layanan HRV ke folder lain, atau periksa salinannya.")
    parser.add_argument("target", type=Path, help="folder tujuan (apps/hrv-service)")
    parser.add_argument(
        "--check", action="store_true",
        help="jangan menulis apa pun; bandingkan salinan di folder itu dengan "
             "hasil ekspor sekarang, dan keluar dengan kode galat bila berbeda")
    args = parser.parse_args(argv)

    target = args.target.resolve()
    if args.check:
        return check(target)
    export(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
