# Handover — Lanjutan Sesi

Ditulis 13 Agustus 2026. Branch: `feat/train-dl`.
Buat dibaca di awal sesi baru, biar nggak ngulang dari nol.

---

## 1. Posisi sekarang

TA-nya punya **tiga pendekatan**, dan ketiganya sudah diukur:

| | macro-F1 | Diukur di | Perannya |
|---|---|---|---|
| **Aturan skor** | 0,828 dev · **0,839 tersegel** | 293 dev / 561 tersegel | **Ini yang dipakai produk** |
| 1D-CNN | **0,878** (adu setara) | 561 tersegel | Pembanding, nggak dipakai produk |
| RAG (label LLM) | **0,672** | 293 dev | Jangan dipakai buat label |

Keputusan arsitekturnya sudah bulat:

```
sinyal → fitur → ATURAN SKOR → label
                                 ↓
                    retrieval KB → RAG → narasi Indonesia
                                 ↓
                              guards → dashboard

           1D-CNN → dilaporkan sebagai pembanding
```

**LLM nggak pernah menentukan label** (K16). Sekarang ada angkanya: kalau LLM yang
mutusin, hasilnya 0,672 lawan 0,828. Dulu ini argumen, sekarang pengukuran.

Angka pendukung lain dari sesi ini:
- RAG kelebihan menuduh stres: 65 dari 152 segmen istirahat dibilang tertekan
- RAG menyerah ("uncertain") di 60 dari 293 segmen — cakupan 79,5%
- Faithfulness **95,2%** (14 angka karangan, 0 sitasi palsu)
- Keyakinan RAG **terkalibrasi**: akurasi 0,47 → 0,60 → 0,88 seiring naiknya confidence
- 1D-CNN menang Wilcoxon p = 0,031, tapi **gagal total di S2** (0,398) yang justru
  dibaca aturan hampir sempurna (0,920) — ini alasan utama aturan tetap dipakai

**325 tes hijau** (Python), **152 tes** frontend.

---

## 2. Infrastruktur yang hidup

**Vast.ai + Ollama.** Jalan, sudah diuji, dipakai buat evaluasi penuh.

Yang penting: **port dan token berganti tiap instance dinyalakan ulang.** Portal
Vast punya API yang bisa menemukan port Ollama sendiri:

```
GET  <INSTANCE_URL host>/capabilities/services      -> daftar layanan + port
GET  <INSTANCE_URL host>/get-direct-url/11434       -> alamat Ollama langsung
```

Kredensialnya **token yang ada di dalam `INSTANCE_URL`**, bukan API key OpenWebUI.
Port Ollama tetap dijaga Caddy milik portal, jadi aman.

`.env` yang benar:
```
LLM_PROVIDER=gemini              # bawaan; ganti per-run pakai env var
OPENWEBUI_BASE_URL=http://<host>:<port-ollama>
OPENWEBUI_API_KEY=<token dari INSTANCE_URL>
OLLAMA_MODEL=gpt-oss:20b
```

Model yang terpasang: `gpt-oss:20b` (13,8 GB, **dipilih**), `qwen3.5:35b` (23,9 GB,
2,6× lebih lambat), `deepseek-r1:32b` (19,9 GB, jalan tapi lambat),
`deepseek-r1:latest` (5,2 GB, **jangan** — paling lambat, melanggar K4).

GPU 32 GB. `gpt-oss:20b` ~9 detik per panggilan kalau model tetap di VRAM.

**Gemini masih dipakai buat embedding retrieval.** Jadi L8 baru termitigasi
separuh — tulis begitu apa adanya, jangan klaim sepenuhnya swa-inang.

---

## 3. Perintah yang sering dipakai

```bash
python scripts/check_ollama.py                    # cek instance hidup + digest model
python scripts/compare_llm.py --models gpt-oss:20b,qwen3.5:35b
python scripts/train_dl.py --matched              # adu setara DL lawan aturan
python scripts/analyse_baseline_duration.py       # berapa lama kalibrasi perlu
LLM_PROVIDER=ollama python scripts/run_evaluation.py --full
```

Tes frontend **harus dijalankan dari dalam `frontend/`**, bukan dari akar repo —
kalau nggak, `import.meta.glob` di `mocks.test.ts` kosong dan gagal palsu.

---

## 4. Yang belum dikerjakan

Nomor mengikuti daftar tugas sesi lama.

**Prioritas berikutnya — #6, ablasi U3.2 & U3.3.** Ini lubang terbesar: judul TA
menyebut RAG tapi belum ada satu bukti pun bahwa KB berkontribusi. Kodenya **belum
punya mode ablasi** (yang ada baru `pinned_chunk_id`), jadi perlu dibangun dulu:
mode tanpa chunk, mode chunk acak (ber-seed), plus flag di `run_evaluation.py`.
Rencananya diukur di dua sumbu — klasifikasi **dan** grounding (kalau dikasih chunk
acak, apakah model tetap pede mengutipnya?).

Sisanya:
- **#5** gold-standard mapping T3b.4 — kerangkanya ada di
  `docs/gold_standard_retrieval.md`, 24 kondisi masih kosong. **Ditunda dengan
  sadar**: harus ditulis buta sebelum lihat hasil retrieval, dan hasilnya sudah
  terlihat. Kalau nggak diisi, T5.5 dilaporkan sebagai pemeriksaan kualitatif,
  bukan Precision@k. Jendelanya terbuka lagi kalau KB diganti versi.
- **#7** praregistrasi DL sebelum menyentuh holdout lagi
- **#8** bedah S2 (aturan 0,920 vs CNN 0,398)
- ~~**#9** ablasi HR-saja~~ **SELESAI 25 Agt**: membuang RMSSD justru menaikkan hasil (tersegel 0,839 → 0,871; menolong 5 subjek, merugikan 0). T1/HW9 terbukti. Detail di BACKLOG U3.1b
- **#10** putuskan durasi kalibrasi (lihat §5)
- **#11** tiga gerbang mutu HW5 di React — logikanya sudah ada di
  `frontend/uji-protokol-hrv.logic.js`, tinggal dipakai ulang
- **#12** verifikasi 11 rujukan KB yang masih bertanda ⚠ — pekerjaan Salma
- **HW9** belum datang. Protokol tiga blok dan kriteria putusannya sudah terkunci.

---

## 5. Temuan yang belum ditindaklanjuti

**Baseline 2 menit terlalu pendek.** Diukur di WESAD
(`scripts/analyse_baseline_duration.py`): baseline 2 menit bisa meleset **43%**
(median), 102% terburuk, dan **15 dari 15 subjek** melampaui ambang sedang −20%.
Aturan berhenti otomatis nggak menolong — **0 dari 15** subjek stabil dalam 2 menit,
median baru stabil di 4 menit. Belum diputuskan mau diapakan.

**Guards nggak bisa menangkap K4** — sudah diperbaiki sesi ini (`find_k4_violations`),
tapi ketahuannya karena `deepseek-r1:latest` nulis "RMSSD, SDNN, dan pNN50" langsung
ke teks pengguna sementara guards lapor nol pelanggaran. `is_trustworthy` sengaja
**nggak** diubah maknanya; ada properti terpisah `is_user_safe`.

---

## 6. Jebakan yang sudah menggigit — jangan terulang

**`cfg.model` vs `interpreter.model_label`.** Muncul **empat kali** di tempat
berbeda: `pipeline.py`, `narrative.py`, `session_pipeline.py`, dan kunci cache di
`run_evaluation.py`. Yang terakhir paling berbahaya — kunci cache bertuliskan nama
model yang dikonfigurasi bikin run Ollama mengembalikan jawaban Gemini yang lama,
selesai mencurigakan cepat, dan angkanya bukan angka yang dikira. Kalau nambah
backend lagi, cari pola ini duluan.

**Tes yang nggak menggigit.** Kejadian tiga kali: tes ditulis, semuanya lulus, tapi
waktu perbaikannya sengaja dirusak tesnya tetap lulus. Sebabnya selalu sama — tesnya
memanggil helper-nya sendiri, bukan jalur yang sebenarnya, atau mengharapkan hasil
kosong yang juga dikembalikan kode yang dimatikan. **Selalu uji mutasi**: rusak
perbaikannya, pastikan tesnya gagal.

**Keluaran ke konsol Windows.** Beberapa skrip mati di `print` terakhir karena
codepage lama nggak bisa menulis karakter tipografis — sekali bikin run 45 menit
kehilangan angkanya. Pola yang dipakai: `sys.stdout.reconfigure(encoding="utf-8")`
di awal skrip.

**`| tail` bikin latar tanpa progres.** Perintah latar yang dipipa ke `tail` nggak
mengeluarkan apa pun sampai selesai. Pantau lewat berkas keluarannya langsung, atau
lewat cache yang bertambah.

**Tanda hubung tipografis.** Model menulis `KB‑PNN50‑01` pakai non-breaking hyphen
(U+2011), dan guard melaporkannya sebagai sitasi palsu padahal benar. Sudah
diperbaiki di `_canonical_id`; 8 pelanggaran palsu hilang, clean rate 92,5% → 95,2%.

---

## 7. Cara kerja yang diharapkan

- **Bahasa Indonesia yang natural**, bukan struktur kalimat Inggris yang diganti
  kata. Kalimat pendek. Hindari "melainkan/sedangkan/justru" bertumpuk.
- **Jangan pakai kode BACKLOG** (T7.4, K16) tanpa menjelaskan isinya — Salma nggak
  hafal.
- **Setiap perubahan bawa tesnya**, tanpa diminta, dan buktikan tesnya menggigit.
- **Verifikasi empiris**, jangan mengklaim dari penalaran. Jalankan, lihat angkanya.
- **Tanya dulu** kalau menyangkut pilihan bahasa/framework/tata letak.
- Kerjakan **bertahap**, jelaskan rencana sebelum perubahan besar.

---

## 8. Yang belum di-commit

```
M scripts/run_evaluation.py     # perbaikan encoding konsol
M src/hrv_rag/rag/guards.py     # normalisasi tanda hubung di _canonical_id
```

Berkas dokumen dari sesi ini: `docs/brief_pertemuan_hr.md`,
`docs/gold_standard_retrieval.md`, `docs/handover.md`.
