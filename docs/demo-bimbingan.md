# Runbook Demo Bimbingan — Backend Modul HRV

Disusun 28 Agustus 2026. **Seluruh langkah di sini sudah dijalankan dan
terbukti bekerja di laptop ini pada tanggal itu** — bukan rencana.

Dua babak: (1) modul HRV hidup menjawab HTTP dengan data manusia sungguhan,
(2) integrasi KARIRLINK di tingkat kode + tes. Frontend karirlink sedang
di-hold (menunggu push teman ke branch `dev`), jadi demo ini sengaja tidak
bergantung padanya.

---

## Babak 1 — Modul HRV menjawab permintaan nyata (±5 menit)

### Nyalakan servisnya (Terminal 1, biarkan hidup)

```bash
HRV_API_KEYS=kunci-lokal HRV_CORS_ORIGINS=http://localhost:5173 python -m uvicorn hrv_api.app:app --app-dir backend --port 8000
```

Dari akar repo `hrv-rag`. Tunggu `Uvicorn running on http://0.0.0.0:8000`.

### Tiga tembakan berurutan (Terminal 2)

**1. Servis hidup:**

```bash
curl -s http://127.0.0.1:8000/health
```

**2. Keamanannya menolak, bukan mengizinkan** — tanpa kunci → 401
(tunjukkan ini DULUAN; penguji suka melihat sistem yang tahu menolak):

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://127.0.0.1:8000/api/v1/analyze/session -H "Content-Type: application/json" -d "{}"
```

**3. Putar ulang sesi pilot manusia sungguhan** — 581 interval RR dari
armband HW9, 6 pertanyaan, direkam 26 Agustus dengan persetujuan:

```bash
python scripts/demo_replay_session.py
```

Keluarannya (sudah diverifikasi):

```
Label sesi: tier=T1, baseline stable=True, evidence=minimal
  Q2: low      recovery=belum terukur
  Q3: low      recovery=belum terukur
  Q4: low      recovery=belum terukur
Paling menegangkan: pertanyaan 3
Provenance: kb=kb_v2.0 prompt=HRV_session_narrative rule=K16-2026-08-03
            model=gemini-2.5-flash trustworthy=True
Narasi    : Secara keseluruhan, Anda menunjukkan ketenangan yang baik...
```

### Kalimat yang menyertai tiap baris keluaran

- **Label per pertanyaan** — dihitung aturan deterministik dari detak jantung,
  BUKAN oleh LLM. Jalankan skrip dua kali: labelnya identik (sudah dibuktikan
  28 Agt, dua run berturut-turut sama persis).
- **`recovery=belum terukur`** — jujur, bukan bug: sesi pilot itu tidak punya
  jeda antar-pertanyaan. `null` dirender "belum terukur", tidak pernah 0%.
- **Tidak ada RMSSD/angka teknis di respons** — API menahannya secara bawaan;
  aturan tampilan ditegakkan dari sisi yang aman.
- **Provenance** — tiap jawaban membawa versi KB, prompt, aturan, dan model:
  hasil bisa direproduksi dan diaudit.
- **`trustworthy=True`** — guard otomatis memeriksa tiap angka di narasi
  tertelusur ke prompt dan tiap sitasi benar terambil.
- **Label sesi ini cocok dengan laporan diri** — pilot 1 melapor "tenang",
  sistem menilai `low` semua: SEPAKAT (tercatat di arsip).

### Cadangan bila kuota Gemini habis saat demo

Jangan panik — justru jadi bahan: label TETAP keluar (aturan luring),
hanya narasi kosong dan `trustworthy` menandainya. Itu degradasi anggun yang
memang dirancang, dan kini terlihat hidup. Ceritakan apa adanya.

### Opsional: tampilan visual (kalau waktu cukup)

Frontend demo modul (bukan karirlink): `npm run dev --prefix frontend`
→ buka `http://localhost:5173?dev=1` (simulator WESAD 10× cepat, tanpa
sensor) atau tanpa `?dev=1` dengan HW9 sungguhan. Layar hasil: dashboard,
radar Calm/Recovery/Resilience, grafik detak per pertanyaan.

---

## Babak 2 — Integrasi KARIRLINK sudah tersambung di kode (±5 menit)

> **Pembaruan 28 Agustus 2026:** ketiga `.env` karirlink kini TERPASANG di
> laptop ini (dari salinan Tegar; semuanya gitignored), venv AI Gateway sudah
> dibuat, dan **kedua servis terbukti menyala**: AI Gateway `/health` sehat
> (model terkonfigurasi), backend NestJS "successfully started" dan menjawab
> 401 tanpa token. Jadi Babak 2 kini BISA live penuh — lihat "Stack penuh"
> di bawah. Cadangan paling aman tetap tes + walkthrough di bawah ini.

### Jalankan tesnya live

```bash
cd "C:\Users\Salma Afifa Azis\Documents\karirlink\karirlink\apps\backend"
npm test -- src/modules/integration src/modules/interview
```

Hasil terverifikasi: **8 suite, 132 tes, semua lolos.** Sebagian teruji
mutasi (kode dirusak sengaja → tes gagal → dikembalikan).

### Peta cerita integrasinya (untuk walkthrough singkat)

```
browser kandidat ──POST /interview-sessions/:id/heart-rate──► NestJS
    (cek kepemilikan sesi; 404 untuk bukan-pemilik)
        └► HrvModuleService ──HTTP + X-API-Key──► modul HRV (babak 1!)
        └► ExternalSignalService ──► baris external_signals (payload utuh)
```

| Lapisan | Berkas (apps/backend/src/modules/…) | Peran |
|---|---|---|
| Endpoint | `interview/heart-rate.controller.ts` + `.service.ts` | terima data denyut, jaga kepemilikan, degradasi anggun |
| Klien keluar | `integration/hrv-module.service.ts` | panggil modul HRV; `include_technical` dikunci false |
| Penyimpan | `integration/external-signal.service.ts` | satu baris `heart_rate` per sesi, payload buram |

Tiga aturan produk yang tertanam (siap dijawab kalau ditanya):
label dari **aturan**, bukan LLM; `heart_rate` **tidak** masuk jalur evaluasi
KSAO dan tidak tampil ke perekrut; angka teknis tidak pernah sampai kandidat.

### Stack penuh (opsional — kalau mau demo alur login sungguhan)

Empat terminal, urut dari yang paling dalam. **AWAS PORT: AI Gateway di 8000,
modul HRV di 8010** — jangan tertukar; `HRV_API_URL` di backend `.env` sudah
menunjuk 8010.

```bash
# 1 — AI Gateway (dari apps/ai-gateway):     .venv\Scripts\python.exe main.py
# 2 — Backend    (dari apps/backend):        npm start        (TANPA --watch untuk demo)
# 3 — Modul HRV  (dari akar hrv-rag):
HRV_API_KEYS=kunci-lokal python -m uvicorn hrv_api.app:app --app-dir backend --port 8010
# 4 — Web        (dari apps/web):            npm run dev
```

Lalu buka `http://localhost:3000`, login sebagai kandidat
(`kandidat@karirlink.dev`; kata sandinya di `apps/backend/.env`,
`SEED_CANDIDATE_PASSWORD` — ketik sendiri, jangan disalin ke dokumen mana pun),
jalani satu sesi. Catatan jujur untuk sesi live:

- Tiap pertanyaan + penilaian memakai kuota Gemini tim (via kunci di
  `.env` gateway); `EVALUATION_SYNC_FALLBACK=true` sedang menyala, jadi
  penilaian berjalan sinkron tanpa Redis — kandidat menunggu Gemini selesai.
- Alur sensor HR end-to-end (gerbang → sesi → baris `external_signals`)
  butuh frontend yang sedang DI-HOLD menunggu merge branch `dev` teman —
  jangan demokan bagian itu live dulu; pakai Babak 1 + tes untuk cerita HR.
- Nest start pertama butuh ±2 menit compile. Nyalakan SEMUA servis sebelum
  bimbingan mulai, jangan di depan dosbim.

### Artefak pendukung yang bisa dibuka

- `docs/openapi-hrv.json` (hrv-rag) — spec dibangkitkan dari kode.
- `docs/module-design/rancangan-rag-hrv.md` (karirlink) — kontrak §4 + tiga
  keputusan bersama §5 + koreksi bertanggal jalur panggil (27 Agt).
- `BACKLOG_INTEGRASI.md` (hrv-rag) — status tiap blok, apa yang selesai dan
  apa yang jujur belum.

---

## Angka yang perlu di luar kepala

| Klaim | Angka |
|---|---|
| Aturan HR-saja (kondisi armband, dipakai produk) | macro-F1 **0,871** [0,808–0,925] |
| Aturan RMSSD+HR | 0,839 [0,773–0,897] |
| 1D-CNN (pembanding riset, tidak dipakai) | 0,878 |
| LLM sebagai penentu label (diukur, DITOLAK) | 0,672 |
| Faithfulness narasi | 95,2%, nol sitasi palsu |
| Detak jantung HW9 vs ECG | ICC +0,986 |
| Tes otomatis | 397 Python · 270 frontend/backend karirlink |

## Yang jujur BELUM (sebut sendiri sebelum ditanya)

- Belum satu pun sesi wawancara KARIRLINK nyata dianalisis — semua angka
  validasi dari WESAD (TSST di lab); pilot manusia baru 3 sesi lewat demo
  frontend modul.
- Angka acuan dari simulasi armband; uji HW9 sungguhan sampai gerbang
  protokol lulus masih prasyarat.
- Frontend karirlink menunggu sinkronisasi branch `dev` (modul FER teman).
- Kuota produksi menunggu kunci Gemini tim (agenda rapat Tegar).

## Jebakan hari-H

- Konsol Windows + narasi ber-karakter non-ASCII → skrip demo sudah
  `reconfigure(encoding="utf-8")`, aman.
- Kuota gratis 20 panggilan/hari — setiap replay memakai 1 panggilan narasi.
  Latihan seperlunya; label tidak pernah ikut mati.
- Jangan jalankan dua uvicorn di port sama; `Ctrl+C` yang lama dulu.
