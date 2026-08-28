# BACKLOG INTEGRASI — Modul HRV → KARIRLINK

Tugas Akhir Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Dibuat: 27 Agustus 2026 · Branch: `feat/integration`

> **Beda dengan `BACKLOG.md`.** `BACKLOG.md` melacak **riset** (pipeline, dataset,
> validasi — T0–T11). Berkas ini melacak **integrasi ke web KARIRLINK**: memasang
> modul yang sudah jadi ke produk. Riset intinya selesai dan terkunci; yang di sini
> adalah pekerjaan menyambungkannya.
>
> Sumber isi: `docs/handover.md` §4, dan `rancangan-rag-hrv.md` (§4 kontrak, §5
> keputusan bersama) di repo karirlink. Kalau dua berkas itu berubah, sinkronkan
> yang ini.

Status: `belum` · `jalan` · `selesai` · `blokir`

Repo web KARIRLINK: `C:\Users\Salma Afifa Azis\Documents\karirlink\karirlink`
(sudah masuk `additionalDirectories`).

---

## Peta cepat — 5 langkah menuju "terintegrasi"

Urut, sesuai `handover.md` §4. Detail tiap langkah di bawah.

| # | Langkah | Status |
|---|---|---|
| A | Commit semua perubahan hrv-rag | selesai |
| B | Rapat kontrak dengan Tegar (3 keputusan + kunci Gemini) | belum |
| C | Satu sesi pilot bersih (recovery & ketahanan terisi pertama kali) | belum |
| D | Deploy staging (cold start scipy/neurokit2 nyata) | belum |
| E | Port akuisisi Bluetooth ke Next.js + jalur tulis `ExternalSignal` | jalan |

Prasyarat dari sisi TA yang **menghalangi** integrasi (bukan seluruh sisa TA)
ada di blok F.

**Keputusan 28 Agt — layanan di-vendor ke monorepo (`apps/hrv-service`).**
Sebelumnya modul hanya hidup di laptop Salma, jadi rekan tim yang meng-clone
karirlink selamanya kena degradasi anggun. Mengikuti preseden `fer-service`:
salinan layanan (subset: `hrv_api`, `hrv_rag`, KB+prompts+indeks, pyproject)
kini ikut monorepo — dibuat HANYA lewat `scripts/export_service.py` di repo
ini, dengan `PROVENANCE.md` mencap commit sumber. Aturannya keras: sunting di
hrv-rag, ekspor ulang — salinan tidak pernah disunting, supaya produk tidak
lepas dari kode yang angka validasinya diukur. Terverifikasi: venv segar dari
salinan mem-boot dan memutar ulang sesi arsip dengan label identik; tanpa
kunci Gemini label tetap keluar dan `trustworthy=false` menandai narasinya.

---

## Blok A — Commit perubahan hrv-rag  ✅ SELESAI

Saat `handover.md` ditulis (26 Agt) ada ~28 berkas belum di-commit di branch
`feat/train-dl`. Kini branch `feat/integration`, pohon git **bersih**, dan commit
terakhir persis pekerjaan yang disebut handover.

| ID | Tugas | Status |
|---|---|---|
| A1 | Commit signal fitness + arsip sesi + watchdog + layar hasil | selesai |
| A2 | `docs/openapi-hrv.json` (spec dibangkitkan dari kode) sebagai artefak serah terima | selesai |

---

## Blok B — Rapat kontrak dengan Tegar  ⬜ BELUM

Ini **keputusan lintas-tim, bukan koding.** API tidak bisa memaksakan sebagian
aturan ini; harus disepakati lalu ditegakkan di sisi web KARIRLINK. Agenda persis
= §5 `rancangan-rag-hrv.md`. Tiga keputusan pertama menunggu persetujuan bersama.

| ID | Tugas | Status |
|---|---|---|
| B1 | **Field `hrv_score` di kontrak `ExternalSignal` tidak akan pernah diisi.** Modul sengaja tidak menghasilkan skor HRV tunggal — angka seperti "72" hanya bermakna lewat perbandingan antar orang, dan seluruh desain menghindari itu. Usul: `stress_level` diisi label sesi dari aturan (`low/moderate/high`), `hrv_score` **dihapus** dari kontrak atau dibiarkan `null` dengan catatan. Perlu putusan Tegar | belum |
| B2 | **`heart_rate` tidak boleh dibaca jalur evaluasi KSAO.** Jalur baca `ExternalSignal` yang ada (evaluation processor, untuk `face_expression`) **tidak boleh ditiru** untuk sinyal ini. Keluaran modul = indikasi tekanan untuk kandidat sendiri, tidak pernah tampil ke perekrut. Dasarnya bukan cuma etika: korelasi sinyal fisiologis dengan penilaian pewawancara terukur lemah (−0,07 s.d. −0,28). Perlu ditegakkan di kode karirlink | belum |
| B3 | **Aturan tampilan mengikat di frontend KARIRLINK** (API tak bisa memaksa): (a) kandidat tak pernah lihat nama fitur / angka HRV / skor mentah; (b) `recovery_pct: null` = "belum terukur", **bukan** 0%; (c) bahasa perilaku bukan label sifat ("butuh waktu lebih lama untuk kembali tenang", bukan "regulasi emosi rendah"); (d) `tier` menentukan panel yang dirender — T1 (armband) tanpa kuadran ketahanan | belum |
| B4 | **Konfirmasi kunci Gemini tim** (`GEMINI_API_KEY_KARIRLINK` di `.env`) boleh dipakai modul ini. Ini jawaban penghalang kuota produksi — tier gratis 20 panggilan/hari tak cukup. ⚠ **Jebakan:** kunci ini sempat jadi duplikat nama `GEMINI_API_KEY`; python-dotenv memakai baris **terakhir** saat nama sama, tanpa peringatan. Pastikan namanya unik | belum |

---

## Blok C — Satu sesi pilot bersih  ⬜ BELUM

Tiga sesi pilot manusia sudah dilakukan (arsip `outputs/session_archive/`), tapi
**belum ada satu pun yang bersih** — recovery & kuadran ketahanan belum pernah
terisi karena protokolnya belum lengkap.

| ID | Tugas | Status |
|---|---|---|
| C1 | **Protokol bersih:** prelude **2 menit diam** (dua menit terakhirnya benar-benar diam — pelajaran sesi 2, baseline tercemar main HP → HR 95 → gerbang menyala benar) + 6 pertanyaan + **jeda 15–20 dtk sebelum "Lanjut"**. Jeda inilah yang mengisi kolom recovery & kuadran ketahanan untuk pertama kali | belum |
| C2 | Mode pengembang **MATI** (`dev=1` → data tiruan, tidak tersimpan). Centang persetujuan arsip. Sensor tersambung 2 menit sebelum mulai | belum |
| C3 | Analisis sampai tuntas dari sensor → layar. Catat label laporan-diri di dalam arsipnya (seperti sesi 1–3) | belum |

**Cara menjalankan** (dari `handover.md` §5):
```bash
HRV_API_KEYS=kunci-lokal HRV_CORS_ORIGINS=http://localhost:5173 HRV_ARCHIVE_DIR=outputs/session_archive python -m uvicorn hrv_api.app:app --app-dir backend --port 8000
```
Frontend: `npm run dev --prefix frontend`.

---

## Blok D — Deploy staging  ⬜ BELUM

Modul masih di laptop. Perlu dijalankan di server supaya cold start
scipy/neurokit2 (impor berat, first-request lambat) terukur nyata sebelum
disambung ke alur wawancara.

| ID | Tugas | Status |
|---|---|---|
| D1 | Deploy layanan FastAPI modul ke staging; ukur waktu cold start impor scipy/neurokit2 | belum |
| D2 | Verifikasi kontrak keamanan tetap berlaku di staging: tanpa `X-API-Key` menolak semua, CORS dari daftar origin (bukan `*`), angka teknis ditahan default | belum |

---

## Blok E — Port akuisisi + jalur tulis `ExternalSignal`  🟡 JALAN

Pekerjaan integrasi terbesar. Sebagian di repo karirlink (Next.js), bukan hrv-rag.
Kontrak keluaran = §4.2 `rancangan-rag-hrv.md`.

**Pemecahan slice (hasil inspeksi 27 Agt).** Blok ini dipecah jadi potongan
atomic yang bisa dites & di-commit sendiri, urut dari paling independen:

| ID | Tugas | Status |
|---|---|---|
| E3a | **Writer `ExternalSignal` — SELESAI 27 Agt.** `ExternalSignalService.recordHeartRate()` di `apps/backend/src/modules/integration/` (repo karirlink): tulis **satu baris** `signalType` dari kontrak (bukan literal), payload `SessionResponse` disimpan **buram**. `create` bukan `upsert` (tak ada indeks unik). Hanya menulis — jalur baca KSAO sengaja tak ditiru (B2). Commit `627f5900` di branch `feat/hrv`. **Belum ada pemanggil** | selesai |
| E3b-1 | **Klien keluar `HrvModuleService` — SELESAI 27 Agt.** Panggilan server-ke-server ke modul HRV (`POST /api/v1/analyze/session`), meniru `AiGatewayService`: base URL/kunci/timeout dari env (`HRV_API_URL`/`HRV_API_KEY`/`HRV_API_TIMEOUT_MS`), terjemah request camel→snake, respons dikembalikan **buram**. `include_technical` dikunci `false`. Commit `3654f752` di branch `feat/hrv`. **Belum ada pemanggil** | selesai |
| E3b-2 | **Endpoint ingest — SELESAI 27 Agt** (`POST /interview-sessions/:id/heart-rate`): `HeartRateController` + `HeartRateService` + `SubmitHeartRateDto`, cek kepemilikan sesi (404 untuk bukan-pemilik) → `HrvModuleService.analyzeSession` → `ExternalSignalService.recordHeartRate`, degradasi anggun (kontrak §4.3: modul mati → `stored:false`, alur kandidat tak digagalkan). `session_id` diambil dari URL (uuid buram). Commit `638158a7` di branch `feat/hrv`. **TUNTAS PENUH 28 Agt:** sesi wawancara nyata pertama (`0e468b4b…`) dianalisis modul dan tersimpan sebagai baris `external_signals` (`9dd82103…`) — penanda `sudahMengirimData` dibalik `true` beserta tes kontraknya (commit `78d095ee`). Pemanggil browser + tampilan hasil di halaman evaluasi juga hidup (E1b + panel "Ketenangan selama sesi") | selesai |
| E-port-0 | **Runner Vitest di `apps/web` — SELESAI 27 Agt** (keputusan Salma: tambah Vitest; sebelumnya apps/web hanya punya Playwright e2e, tanpa uji unit). `vitest.config.mts` + skrip `npm test` + uji perdana `cn()`. Commit `a7888f85` | selesai |
| E-port-1 | **Port logika murni — SELESAI 27 Agt**: parser paket BLE (`protocol.ts`), linimasa + jam sesi (`question-timing.ts`), pengiris grafik per pertanyaan (`question-heart-rate.ts`) ke `apps/web/src/lib/heart-rate/`, dengan 23 tes ikut. Adaptasi sadar: field camelCase (= DTO backend; terjemahan snake_case tetap satu tempat di `HrvModuleService`), `sessionElapsedSec` menerima `playbackSpeed` (apps/web tanpa simulator). Commit `84bc980e`. Kode belum dipakai layar mana pun sampai E1 | selesai |
| E2 | **Jaga dua jam (`offset_sec`) — SELESAI 27 Agt** lewat E-port-1 + E1b: tes offset di `question-heart-rate.test.ts` (port), passthrough offset di `submission.test.ts`, dan `offsetSec` dihitung dari panjang deret RR terkumpul saat persetujuan selesai (rekaman = deret interval itu sendiri, bukan selisih jam dinding). Mutasi hapus-offset terbukti menggigit | selesai |
| E1a | **Fondasi klien — SELESAI 27 Agt** (tiga keputusan Salma tercatat hari itu: pemetaan jenis pertanyaan lewat TIPE KOMPETENSI technical/behavioral → technical/behavioural, fallback studi_kasus→situational sisanya→technical; sensor HR ikut layar perizinan kamera/mikrofon sebagai fitur OPSIONAL — lanjut tanpa connect boleh; indikator bpm live ADA). Yang terpasang: `hrvQuestionType()` + union `HrvQuestionType` (commit `f1a51501`), `submitHeartRate()` di api-client (`917642e1`), port `device.ts` (pengenalan letak pakai + modalitas) dan hook Web Bluetooth `use-device-connection.ts` lengkap dengan watchdog 5 dtk & mutu sinyal, 23 tes hook/perangkat ikut (`065d60fb`; devDeps `@types/web-bluetooth`, `jsdom`, `@testing-library/react`). Simulator `?dev=1` sengaja TIDAK ikut — perkakas demo, pekerjaan tersendiri bila dibutuhkan | selesai |
| E1b | **Integrasi UI — SELESAI 27 Agt** (commit `7de5a88c` + `20bb7d8e`): kartu sensor di langkah Perangkat gerbang perizinan (opsional — lanjut tanpa connect sah; iOS dijelaskan, bukan tombol mati) + baris rekap netral; kartu yang sama di rel pemantauan saat sesi (bpm live + banner merah saat macet); hook DIMILIKI halaman sesi supaya koneksi bertahan setelah gerbang tertutup; `buildHeartRateSubmission` (fungsi murni, teruji hitung-tangan) menyusun kiriman — patokan jam saat persetujuan selesai, `offsetSec` dari jumlah interval RR (bukan selisih jam dinding), `baselineMinutes` = masa tunggu pertanyaan pertama dijepit [2,8] (di bawah 2 modul menambal dari prelude); jendela jawab = pertanyaan tampil → tombol kirim ditekan, dicatat hanya bila jawaban tersimpan; kiriman dilepas di latar setelah sesi resmi tertutup, semua kegagalan lunak. **Dua keputusan terbuka tercatat:** (a) `isDifficult=false` semua — belum ada penanda kesulitan di alur karirlink, jadi pemulihan dilaporkan "belum terukur"; (b) `storeConsented` selalu false — belum ada centang persetujuan riset di UI karirlink | selesai |
| E4 | **Degradasi anggun — SELESAI 27 Agt**, tertanam berlapis: sensor tak tersambung / tanpa denyut / letak pakai tak dijawab → `buildHeartRateSubmission` mengembalikan null (keadaan normal, tanpa pesan galat); modul HRV mati / kuota habis → backend membalas `stored:false` dan frontend menampilkannya sebagai toast berita, bukan galat; kegagalan jaringan pun lunak — sesi sudah resmi tertutup sebelum kiriman dilepas. LLM gagal di dalam modul → label tetap keluar (aturan luring), `meta.trustworthy` menandai narasinya (sisi modul, sudah lama selesai) | selesai |

**Keputusan arsitektur (DIPUTUSKAN 27 Agt): NestJS memanggil modul HRV langsung**,
bukan lewat AI Gateway. Alasannya `apps/ai-gateway` khusus Gemini sedangkan modul
HRV mandiri (endpoint sendiri, `X-API-Key`, panggil Gemini sendiri) — proxy hanya
menambah hop Python→Python tanpa manfaat. Koreksi bertanggal ada di
`rancangan-rag-hrv.md` §4.1.

---

## Blok F — Prasyarat dari sisi TA yang menghalangi integrasi  ⬜ BELUM

Bukan seluruh sisa TA — hanya yang **benar-benar prasyarat** sebelum modul boleh
dipercaya di produk. Sisa TA lain (ablasi tanpa-KB, verifikasi 11 sitasi KB, sesi
dua-perangkat HW9+H808S) tetap di `BACKLOG.md`, **tidak** menghalangi integrasi.

| ID | Tugas | Status |
|---|---|---|
| F1 | **Uji perangkat HW9 sungguhan sampai gerbang protokol lulus.** Semua angka acuan (0,871 HR-saja) dari simulasi armband — rekaman ECG WESAD dengan RMSSD disembunyikan — **bukan HW9 nyata**. Gerbang perangkat (RR asli) sudah lulus; gerbang protokol **belum** (stresor tidak menggigit, HR cuma +1,5%; baseline melayang). Detail di `BACKLOG.md` H6–H10 dan `docs/AKUISISI_HRV_WEB_BLUETOOTH.md` | blokir |
| F2 | **Putuskan aturan baseline** sebelum menyentuh subjek: blok 6–7 menit, baseline dari 2–3 jendela **terakhir** saja, kestabilan dipakai sebagai penolakan bukan pemicu berhenti (gerbang kestabilan terukur lebih buruk dari durasi tetap). `BACKLOG.md` H7 | belum |
| F3 | **Aktifkan billing / pakai kunci Gemini tim** (lihat B4) — tanpa ini, evaluasi produksi terhalang kuota 20 panggilan/hari | belum |

---

## Yang sudah terbukti di dunia nyata (bukan lab) — konteks

Supaya tidak salah kira status kesiapan:

- **HW9 lolos uji hari pertama** (20 Agt): bit RR menyala, interval asli.
- **Tiga sesi pilot manusia** sudah dilakukan (arsip `outputs/session_archive/`).
  Sesi 3 sempat GAGAL 422 (aplikasi lain merebut sensor) — watchdog & tampilan
  alasan server sudah diperbaiki sesudahnya.
- **Belum satu pun sesi wawancara KARIRLINK nyata** pernah dianalisis. Semua angka
  dari WESAD (TSST di lab). Ini wajib jujur dikatakan.

---

## Jebakan yang sudah menggigit — jangan terulang

Dari `handover.md` §6, yang relevan ke integrasi:

- **python-dotenv: nama kunci ganda → baris terakhir menang, tanpa peringatan** (lihat B4).
- **Aplikasi lain menyambar sensor BLE**: koneksi tampak hidup, notifikasi mati.
  Watchdog kedatangan denyut satu-satunya deteksi. Wajib disebut ke tim web (E1).
- **`offset_sec` dua jam** (E2): kelas bug yang tidak menghasilkan error.
- **`SIMULATION_SPEED`** dipakai jam sesi DAN pemutar denyut — hanya urusan
  simulator dev, tapi jangan pisahkan keduanya.
