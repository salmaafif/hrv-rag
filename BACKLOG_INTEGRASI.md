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
| E3b | **Panggilan server-ke-server ke modul HRV** → dapat `SessionResponse` → panggil writer E3a. **Butuh keputusan arsitektur dulu (lihat catatan bawah).** Saat slice ini nyambung: balik penanda `sudahMengirimData` di kontrak jadi `true` — tripwire `external-signal.contract.spec.ts` akan menggigit dan memaksa catatan status diperbarui | blokir |
| E-port-1 | **Port logika murni** `heartRateProtocol.ts` + `questionTiming.ts` + `questionHeartRate.ts` + tipe kontrak dari `frontend/` (Vite) ke Next.js, bawa tesnya. Aman (fungsi murni), tapi jadi kode mati sampai UI (E1) memakainya | belum |
| E2 | **Jaga dua jam** (`offset_sec`) di sisi Next.js: sensor mengalir **sejak tersambung**, jam sesi mulai **saat tombol ditekan**. Salah di sini tidak error — hanya tiap pertanyaan dinilai dari menit rekaman yang salah, diam-diam. Bergantung E-port-1 (belum ada "client karirlink" sebelum itu). Kelas bug ini dijaga tes di backend hrv-rag dan client (`questionHeartRate.test.ts`) | belum |
| E1 | **Port akuisisi Web Bluetooth** dari `frontend/` (Vite) ke Next.js KARIRLINK: hook + layar sesi ke App Router. Termasuk watchdog aliran denyut (5 dtk sunyi saat "tersambung" → banner merah; `gattserverdisconnected` TIDAK menyala saat aplikasi lain merebut sensor — hanya kedatangan denyut yang mendeteksinya). Paling besar, paling banyak keputusan desain | belum |
| E4 | **Degradasi anggun** (kontrak §4.3): modul mati / sensor tak tersambung → wawancara jalan penuh tanpa baris `heart_rate`. LLM gagal / kuota habis → label tetap keluar (aturan luring), hanya narasi kosong, `meta.trustworthy` menandainya | belum |

**Keputusan arsitektur yang memblokir E3b:** modul HRV (FastAPI terpisah) dipanggil
**lewat AI Gateway** (sesuai diagram rancangan §2: NestJS → AI Gateway → Modul HRV)
atau **NestJS memanggil modul HRV langsung**? Pola `AiGatewayService` sudah jadi
template untuk salah satunya. Harus diputuskan sebelum E3b.

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
