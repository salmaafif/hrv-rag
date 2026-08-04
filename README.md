# HRV-RAG — Interpretasi Tingkat Tekanan dari HRV

Tugas Akhir Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Modul untuk platform latihan wawancara kerja KARIRLINK

Sistem menilai tingkat tekanan dari HRV **tanpa melatih model machine learning**.
Fitur dihitung deterministik oleh Python, lalu ditafsirkan LLM (Gemini) yang dibekali
knowledge base lewat pendekatan RAG.

Dokumen lain: [`.claude/CLAUDE.md`](.claude/CLAUDE.md) berisi aturan desain,
[`BACKLOG.md`](BACKLOG.md) berisi status pekerjaan, dan
[`docs/development_journey.md`](docs/development_journey.md) berisi alasan tiap
keputusan beserta temuan empirisnya.

---

## Persiapan

```bash
pip install -r requirements.txt
```

Buat berkas `.env` di akar repo:

```
GEMINI_API_KEY=isi_kunci_di_sini
```

Dataset WESAD dicari otomatis di dua tempat: `data/raw/wesad/` di dalam repo, lalu
`Documents/WESAD/` sebagai cadangan. Tidak perlu dipindah.

---

## Urutan Menjalankan

Jalankan dari akar repo. Kolom API menandai skrip yang memakai kuota Gemini —
tier gratis hanya **20 panggilan per hari**.

| # | Perintah | API | Menghasilkan |
|---|---|---|---|
| 1 | `python -m pytest tests/ -q` | — | 62 uji, memastikan hitungan benar |
| 2 | `python scripts/run_preprocessing.py` | — | cek sinyal → deret RR |
| 3 | `python scripts/run_features.py` | — | `outputs/features_wesad_ecg_dev.csv` |
| 4 | `python scripts/build_kb_index.py` | ~6 | `data/processed/kb_index/` |
| 5 | `python scripts/run_assessment.py` | 3 | demo 3 segmen, dua lapis keluaran |
| 6 | `python scripts/run_evaluation.py --n 20` | 20 | metrik klasifikasi + faithfulness |
| 7 | `python scripts/run_ppg.py` | — | perbandingan modalitas ECG vs PPG |
| 8 | `python scripts/run_session.py` | — | laporan per sesi: reaktivitas, arousal, pemulihan, ketahanan |

**Ketergantungan yang penting:**

- Langkah 3 **wajib** sebelum 5 dan 6 — keduanya membaca CSV fitur.
- Langkah 4 **wajib** sebelum 5 dan 6 — keduanya butuh indeks knowledge base.
- Langkah 2 dan 7 berdiri sendiri, hanya perlu dataset WESAD.
- Langkah 4 **wajib diulang** setiap kali isi `knowledge_base/knowledge_base_HRV.md`
  diubah. Kalau tidak, sistem mencari pada pengetahuan lama sementara laporan
  menyebut versi baru — dan hasilnya tidak dapat direproduksi.

**Jalur tanpa API sama sekali** (berguna saat kuota habis):

```bash
python -m pytest tests/ -q                      # 75 uji
python scripts/run_preprocessing.py             # sinyal -> deret RR
python scripts/run_features.py                  # fitur HRV + reaktivitas
python scripts/run_session.py                   # laporan per sesi
python scripts/run_evaluation.py --rules-only   # metrik pembanding tanpa LLM
python scripts/run_ppg.py                       # ECG vs PPG
```

Kelimanya mencakup seluruh jalur deterministik sistem — semua angka yang tidak
bergantung pada LLM bisa diperiksa lewat perintah di atas.

---

## Pilihan Perintah

```bash
python scripts/run_preprocessing.py S2 S3      # subjek tertentu
python scripts/run_features.py S2
python scripts/build_kb_index.py --search-only # uji kueri tanpa membangun ulang
python scripts/run_assessment.py --consistency # segmen sama 3x (T5.4)
python scripts/run_evaluation.py --full        # semua 293 segmen, butuh ~15 hari
python scripts/run_evaluation.py --pinned      # chunk rubrik disematkan (T4.7)
python scripts/run_ppg.py S2 S6
python scripts/run_session.py S14           # satu subjek saja
```

Tanpa argumen subjek, skrip memakai **lima subjek pengembangan** (S2, S6, S10, S14,
S17). Sepuluh subjek uji sengaja disegel sampai prompt dan knowledge base dibekukan —
menyetel prompt sambil melihat hasil tetap merupakan bentuk fitting, meski tidak ada
model yang dilatih.

---

## Soal Kuota

Tier gratis Gemini membatasi 20 permintaan per hari untuk `gemini-2.5-flash`.
Evaluasi penuh 293 segmen karena itu butuh sekitar 15 hari.

`run_evaluation.py` menyimpan tiap hasil ke `outputs/assessment_cache.jsonl` begitu
selesai. Jalankan lagi keesokan harinya dan skrip melanjutkan dari tempatnya berhenti,
tanpa mengulang panggilan yang sudah terpakai.

Kunci cache mencakup versi KB, nama prompt, model, temperature, dan status penyematan
chunk. Mengubah salah satunya membuat hasil lama tidak sebanding, sehingga tidak akan
dipakai ulang secara diam-diam.

---

## Struktur

```
knowledge_base/    23 chunk ber-ID tetap (kb_v2.0), versi lama di versions/
prompts/           prompt berversi — bagian dari sistem, bukan dokumentasi
src/hrv_rag/       config · core · datasets · preprocessing · features · rag · evaluation
scripts/           skrip yang dijalankan manual
tests/             62 uji, memakai masukan yang jawabannya sudah diketahui
outputs/           hasil (tidak di-commit)
docs/              catatan perjalanan & diagram
archive/           kode lama, disimpan untuk perbandingan
```

Dua sumbu abstraksi: **modalitas** (`ECGPreprocessor`, `PPGPreprocessor`) dan
**dataset** (`WESADLoader`, menyusul `SWELLLoader`, `UBFCLoader`). Selebihnya fungsi
biasa.
