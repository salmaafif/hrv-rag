# Peta Pekerjaan — per Domain

**Interpretasi Tingkat Tekanan dari HRV dengan RAG**
Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Modul untuk platform latihan wawancara kerja KARIRLINK

Disusun 20 Agustus 2026, **dari isi repo yang sebenarnya** — bukan dari `BACKLOG.md`.
Pemeriksaan langsung ke `src/`, `backend/`, `frontend/`, `scripts/`, `tests/`, dan riwayat
git menemukan banyak baris `BACKLOG.md` bertanda `belum` yang ternyata sudah selesai.

## Kenapa berkas ini ada, dan bedanya dengan yang lain

`BACKLOG.md` melacak pekerjaan menurut **urutan pengerjaan** (T0 → T9, U1 → U4). Urutan itu
berguna waktu mengerjakan, tapi menyulitkan waktu ingin tahu "bagian frontend-ku sudah sampai
mana". Berkas ini menyusun ulang isi yang sama menurut **domain**, supaya satu bagian bisa
dilihat utuh tanpa membaca seluruh logbook.

| Dokumen | Menjawab |
|---|---|
| `BACKLOG.md` | apa yang dikerjakan, urutannya, statusnya |
| `development_journey.md` | kenapa keputusannya diambil |
| `handover.md` | posisi terakhir, untuk melanjutkan sesi |
| `AKUISISI_HRV_WEB_BLUETOOTH.md` | perangkat keras & akuisisi |
| `ARSITEKTUR_KARIRLINK_HRV.md` | bentuk produk & gerbang mutu |
| **berkas ini** | **sudah sampai mana, per domain** |

**Tanda:** `✓` selesai · `○` belum · `~` sebagian · `!` bermasalah atau perlu keputusan

Kode `A`/`G` merujuk `ARSITEKTUR_KARIRLINK_HRV.md`; kode `K`/`T`/`U`/`L`/`D` merujuk
`BACKLOG.md`; `HW`/`§` merujuk `AKUISISI_HRV_WEB_BLUETOOTH.md`.

---

## 1. Frontend

```
FRONTEND
├── A. Halaman uji mandiri (perkakas, bukan produk)
│   ├── ✓ uji-sensor-hrv.html — gerbang RR, deteksi sintetis, resolusi jam
│   ├── ✓ uji-protokol-hrv.html — 3 blok, 2 slot alat, putusan terkunci
│   ├── ✓ uji-protokol-hrv.logic.js — semua aritmetika, dipakai bersama
│   └── ✓ uji-protokol-hrv.logic.test.js — + fixture dari pipeline Python
│
├── B. Kerangka aplikasi React
│   ├── ✓ AppLayout, StageRouter, routes.tsx, ErrorScreen
│   ├── ✓ stageContext.ts, modes.ts (V1 / V2 / V3)
│   ├── ✓ useDevMode — panel pengembang, pemisah K4
│   └── ✓ NavigateKeepingSearch + useNavigateKeepingSearch
│
├── C. Lapisan perangkat (Bluetooth)
│   ├── ✓ useDeviceConnection + useDeviceConnection.test
│   ├── ✓ heartRateProtocol.ts — parsing 0x2A37 + tesnya
│   ├── ✓ types/device.ts + device.test
│   ├── ✓ DevicePanel
│   └── ○ Tiga gerbang mutu HW5 di React
│         logikanya sudah ada di uji-protokol-hrv.logic.js, tinggal dipakai ulang
│
├── D. Alur sesi
│   ├── ✓ useSessionState + tesnya
│   ├── ✓ questionTiming.ts + tesnya
│   ├── ✓ StartPage, SessionPage, ProcessingPage, UploadPage
│   └── ✓ StepRail, ModeSelect, RecordingUpload
│
├── E. Lapisan API klien
│   ├── ✓ client.ts, httpClient.ts, errors.ts, dummy.ts
│   ├── ✓ types/api.ts — kontrak, snake_case dipertahankan
│   └── ✓ mocks/ — questionBank, session, timeline, rule, recording, devices
│
├── F. Layar hasil  ← SEDANG DIKERJAKAN
│   ├── ✓ SessionResult, QuestionResultCard, RecoveryBars, StressTimeline
│   ├── ✓ format.ts — NOT_MEASURED, null ≠ nol, dikunci format.test.ts
│   ├── ✓ sessionInsights.ts — semua angka relatif sesi sendiri (Aturan Wajib #2)
│   ├── ! A11 buang radar → plot kuadran (reaksi × pemulihan)
│   ├── ! A10 beri label "Ketahanan", naikkan posisinya
│   ├── ! A12 hapus badge Rendah/Sedang/Tinggi → deskripsi perilaku
│   ├── ! A13 kalimat reappraisal naik ke paling atas
│   ├── ! A14 baris rekonsiliasi ("kalau terasa tidak cocok…")
│   ├── ! A15 satu pertanyaan balik ke kandidat
│   ├── ! A16 pernyataan ruang lingkup (1 dari 5 dimensi MASI)
│   ├── ! Sumbu masih bahasa Inggris (Calm/Recovery/Endurance) — melanggar K4
│   ├── ! Komentar kepala ResponseRadar.tsx menulis "four-axis", sumbunya tiga
│   └── ! "Yang paling bikin tegang" tampil dua kali (kartu atas & kartu pola)
│
└── G. Rilis
    ├── ✓ 152 tes hijau (jalankan dari dalam frontend/, bukan akar repo)
    └── ○ Deploy — WAJIB HTTPS, tanpa itu Web Bluetooth mati
```

---

## 2. Backend / API

```
BACKEND
├── ✓ backend/hrv_api/app.py, deps.py, responses.py, schemas.py
├── ✓ routes/health.py, session.py, timeline.py
├── ✓ services/analysis.py, narrative.py
├── ✓ Kunci API di server, tidak pernah di React
├── ✓ offset_sec untuk penjajaran waktu sesi & timeline
├── ✓ tests/test_api.py
│
├── ! A6 pisahkan lapisan pengguna/teknis di TINGKAT RESPONS
│      Sekarang K4 hanya ditegakkan di SessionResult.tsx. Tim web KARIRLINK akan
│      menulis ulang frontend; begitu berkas itu diganti, jaminannya hilang tanpa
│      satu pun tes merah. Murah sekarang karena API belum diserahkan.
├── ○ A5 field `tier` di respons (T0 / T1 / T2)
├── ○ A7 dokumen "mana yang dijanjikan stabil, mana yang tidak"
├── ○ Versi prompt + versi aturan skor ikut di `meta`
├── ○ Verifikasi pintu masuk interval RR sudah jalan penuh (frontend_plan §5)
└── ○ Deploy + CORS produksi
```

---

## 3. AI

### 3.1 Pra-pemrosesan

```
├── ✓ preprocessing/ecg.py — sinyal mentah → deret RR bersih
├── ✓ preprocessing/ppg.py — cabang BVP
├── ✓ preprocessing/intervals.py — pintu masuk RR langsung (Bluetooth/CSV)
├── ✓ preprocessing/base.py
└── ✓ Koreksi ektopik — bug 59,5% → 1,5% sudah dibetulkan (§4.1)
```

### 3.2 Ekstraksi fitur

```
├── ✓ segmentation.py — jendela 60 dtk, overlap 30 dtk
├── ✓ time_domain.py — RMSSD, SDNN, pNN50, meanRR
├── ✓ frequency_domain.py — Welch + Lomb-Scargle berdampingan (K2)
├── ✓ baseline.py — acuan per orang (Aturan Wajib #2)
├── ✓ dynamics.py — reaktivitas, pemulihan, kuadran ketahanan
├── ✓ question.py — pengelompokan segmen per pertanyaan
└── ✓ extractor.py
```

### 3.3 Aturan skor — yang dipakai produk (K16)

```
├── ✓ features/stress_level.py — dikalibrasi lalu dibekukan
├── ✓ scripts/calibrate_rule.py
├── ✓ Gerbang mutu baseline (is_stable + evidence)
├── ✓ macro-F1 0,828 dev · 0,839 tersegel
└── ○ #9 ABLASI HR-SAJA
      Menentukan apakah tingkat produk T1 (PPG) jujur. Murah, tidak butuh LLM,
      dan satu-satunya percobaan yang menentukan nasib perangkat yang sudah dibeli.
```

### 3.4 RAG

```
├── Basis pengetahuan
│   ├── ✓ kb_v2.0 — 23 chunk
│   ├── ✓ scripts/build_kb_index.py
│   └── ! #12 sebelas sitasi masih bertanda ⚠, belum diverifikasi
│
├── Retrieval
│   ├── ✓ retrieval.py — cosine manual, tanpa vector store (K3 / K13)
│   ├── ✓ Penyematan KB-INTERP-01 — perbaikan T4.7
│   ├── ✓ segment_seed berbasis blake2b (hash() Python bergaram per proses)
│   └── ✓ query_builder.py — termasuk deteksi pola terbalik S6/S10
│
├── Prompt & LLM
│   ├── ✓ prompt.py + prompts/ berversi sebagai berkas, bukan string
│   ├── ✓ llm.py — Gemini + Ollama (gpt-oss:20b)
│   ├── ✓ rate_limit.py
│   ├── ○ Kalibrasi keyakinan → prompt v2
│   └── ! Embedding MASIH Gemini — L8 baru termitigasi separuh, jangan
│         diklaim swa-inang penuh di laporan
│
├── Pengaman
│   ├── ✓ guards.py — angka karangan + rujukan palsu
│   ├── ✓ find_k4_violations + tests/test_k4_guard.py
│   └── ✓ Normalisasi tanda hubung tipografis (8 pelanggaran palsu hilang)
│
└── Pipeline
    ├── ✓ pipeline.py, session_pipeline.py, narrative.py
    └── ✓ Faithfulness 95,2% · nol sitasi palsu
```

### 3.5 Pembanding deep learning

```
├── ✓ hrv_dl/dataset.py, models.py, train.py
├── ✓ Adu setara (--matched) + langkah anti-overfitting
├── ✓ macro-F1 0,878 · menang Wilcoxon p = 0,031
├── ✓ K17 — tidak dipakai produk, hanya dilaporkan sebagai pembanding
├── ○ #8 bedah S2 — aturan 0,920 vs CNN 0,398
└── ○ #7 praregistrasi sebelum menyentuh holdout lagi
```

### 3.6 Evaluasi

```
├── ✓ evaluation/ — metrics, labels, rag_metrics, rule_baseline, modality, cache
├── ✓ scripts/run_evaluation.py, run_holdout.py
├── ✓ Hasil tersegel: accuracy 0,852 · macro-F1 0,839 · Cohen's κ 0,678
├── ✓ Selang kepercayaan pada metrik
├── ✓ Mode ablasi DIBANGUN — SEMANTIC / RANDOM / NONE + tests/test_ablation.py
├── ! U3.2 & U3.3 ablasinya BELUM DIJALANKAN  ← LUBANG TERBESAR
│     Judul TA menyebut RAG, tetapi belum ada satu angka pun yang membuktikan
│     knowledge base berkontribusi. Kodenya sudah siap; tinggal dijalankan.
├── ○ U3.4 sapuan k · U3.5 sapuan temperature · U3.6 ablasi info modalitas
├── ○ T3b.4 gold-standard mapping — 24 kondisi kosong, ditunda dengan sadar
├── ○ T5.5 Precision@k / Recall@k / MRR (butuh T3b.4)
├── ○ U4.2 segel prompt & KB · U4.3 tetapkan jumlah run konsistensi
└── ✓ 325 tes Python hijau
```

---

## 4. Hardware & Akuisisi

```
HARDWARE
├── ✓ Riset tujuh perangkat + tabel perbandingan
├── ✓ Proposal pengajuan dana; Coospo HW9 dibeli
│
├── ✓ G1 GERBANG PERANGKAT — LULUS
│   ├── ✓ Field RR ada; sumber RR asli, bukan 60000/bpm
│   ├── ✓ Jam alat 128,00 Hz, kisi RR 7,8125 ms
│   ├── ✓ Harga kuantisasi terhitung — 0,16 ms pada RMSSD istirahat
│   └── ✓ Outlier 4,5% / 4,3% — setara mutu ECG dada di WESAD
│
├── ✓ Enam cacat perkakas ditemukan lewat uji ini, semuanya diperbaiki
│   ├── ✓ Detektor RR sintetis salah kaidah (menghitung nilai berbeda)
│   ├── ✓ Pembulatan 1 desimal di ekspor halaman sensor
│   ├── ✓ Math.round() sebelum uji kisi di halaman protokol
│   ├── ✓ Label 'pra' dipakai untuk pra DAN pasca protokol
│   ├── ✓ Cakupan waktu tidak pernah dilaporkan
│   └── ✓ Kartu Field RR memantulkan paket terakhir, bukan riwayat
│
├── ! G2 PROTOKOL — belum lolos
│   ├── ! Stresor tidak menggigit — HR hanya +1,5%; butuh yang lebih menuntut
│   ├── ! L22 baseline melayang — RMSSD naik 26,5% sepanjang blok istirahat
│   │      Gerbang kestabilan JUSTRU lebih buruk daripada durasi tetap: melayang
│   │      pelan tampak stabil di jendela pendek, dan semua varian yang diuji
│   │      menyala di 120 dtk lalu mengunci nilai 28,5% terlalu rendah.
│   │      Arah yang disarankan: blok 6–7 menit, baseline dari 2–3 jendela
│   │      TERAKHIR saja, kestabilan dipakai sebagai penolakan bukan pemicu.
│   ├── ○ Uji rumus L22 pada 15 subjek WESAD sebelum dikunci
│   └── ○ Ulangi protokol dengan pemasangan LENGAN ATAS (§6.2)
│
├── ○ G3 pilot 1–2 subjek, dianalisis sampai tuntas sebelum lanjut
├── ○ Chest strap H808S sebagai slot pembanding B
├── ○ HW-Q1 aktifkan billing Gemini
└── ○ HW-Q4 teks lengkap versi IJSPP Protzen dkk.
```

---

## 5. Data & Protokol Penelitian

```
DATA
├── ✓ WESAD — 5 subjek pengembangan / 10 tersegel, per subjek (K10)
├── ✓ Cabang PPG WESAD wrist BVP — HR sepakat, variabilitas tidak (§4.13)
├── ~ SWELL-KW — loader + tes + skrip ada, evaluasinya belum dijalankan
├── ✗ UBFC-Phys — blokir, dataset belum tersedia
├── ○ Pengambilan data subjek nyata  ← LANGKAH TERMAHAL, belum terjadi
└── ○ Persetujuan/etik subjek, bila kampus mensyaratkan
```

---

## 6. Dokumentasi & Laporan

```
DOKUMEN
├── ✓ development_journey.md — penalaran & temuan empiris
├── ✓ AKUISISI_HRV_WEB_BLUETOOTH.md — perangkat, §3.3, §3.4, L13–L22
├── ✓ frontend_plan.md — kontrak API
├── ✓ handover.md — posisi terakhir
├── ✓ ARSITEKTUR_KARIRLINK_HRV.md — A1–A16, G1–G6
├── ✓ brief_pertemuan_hr.md
├── ~ gold_standard_retrieval.md — kerangka ada, isinya kosong
├── ! BACKLOG.md tidak sinkron dengan kode
├── ! D1.3 pipeline_RAG_HRV.png TIDAK ADA padahal dirujuk RAG_HRV_Design.md:15
├── ! requirements.txt belum mengunci versi
│      Kalau neurokit2 diperbarui dan deteksi puncak R-nya berubah, seluruh angka
│      di laporan bergeser tanpa satu pun pesan kesalahan. Pekerjaan lima menit.
├── ○ README.md (D1.1)
├── ○ D1.4 diagram alir pra-pemrosesan per modalitas
├── ○ D1.5 catatan tiap parameter numerik + alasannya
├── ○ D1.6 kamus data kolom CSV keluaran
├── ○ D2.2 catatan perubahan prompt · D2.3 catatan perubahan KB
├── ○ D2.4 dokumentasi gold-standard mapping
├── ○ D2.5 log eksperimen (versi KB/prompt/model, k, temperature, timestamp)
└── ○ D3.1 pemetaan ke bab laporan · D3.2 bab keterbatasan · D3.3 jawaban sidang
```

---

## Urutan yang disarankan

Diurut menurut **biaya kalau ditunda**, bukan menurut besar pekerjaannya.

**Minggu ini — yang tidak bisa diperbaiki belakangan**

1. Putuskan L22 baseline, dan uji rumusnya di 15 subjek WESAD lebih dulu
2. Jalankan ablasi U3.2 & U3.3 — kodenya sudah ada, dan ini lubang terbesar di klaim TA
3. Kunci versi pustaka di `requirements.txt`

**Sebelum menyentuh subjek**

4. Ulang protokol: lengan atas, stresor lebih menuntut, baseline hasil keputusan (1)
5. Ablasi HR-saja (#9) — menentukan apakah tingkat T1 layak diklaim
6. Pilot 1–2 subjek, analisis sampai tuntas

**Boleh berjalan paralel**

7. Perbaikan layar hasil A8–A16
8. Pemisahan lapisan di kontrak API (A6) — sebelum tim web menulis baris pertama
9. Verifikasi 11 sitasi KB (#12)

**Menjelang akhir**

10. Sisa dokumentasi, sinkronkan `BACKLOG.md`, buat gambar pipeline yang rujukannya rusak

---

## Dua hal yang paling perlu diwaspadai

**Judul TA menyebut RAG, tetapi belum ada satu angka pun yang membuktikan knowledge base
berkontribusi.** Mode ablasi sudah dibangun dan sudah punya tesnya; yang kurang hanya
menjalankannya. Ini pertanyaan yang paling mungkin muncul di sidang dan paling murah dijawab
sekarang.

**`requirements.txt` tanpa kunci versi adalah risiko reproduksibilitas terbesar yang tersisa.**
Kegagalannya senyap: tidak ada pesan kesalahan, hanya angka yang berbeda dari yang tertulis
di laporan.
