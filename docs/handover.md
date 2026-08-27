# Handover — Lanjutan Sesi

Ditulis 26 Agustus 2026 (menggantikan versi 13 Agustus seluruhnya).
Branch: `feat/train-dl`. Buat dibaca di awal sesi baru, biar nggak ngulang dari nol.

---

## 1. Posisi sekarang: fase INTEGRASI ke KARIRLINK

Riset intinya selesai dan terkunci. Yang berjalan sekarang adalah menyisipkan
modul ini ke web KARIRLINK (`C:\Users\Salma Afifa Azis\Documents\karirlink\karirlink`
— sudah masuk `additionalDirectories` di settings, dan repo itu punya CLAUDE.md
+ `docs/module-design/rancangan-rag-hrv.md` versi baru yang kami tulis).

Arsitektur final (tidak dibahas ulang):

```
sinyal → pemeriksa kelayakan sinyal → ATURAN SKOR → label
                                        ↓
                          retrieval KB → LLM → narasi Indonesia
                                        ↓
                                    guards → dashboard
```

Angka acuan (10 subjek WESAD tersegel, selang 95% bootstrap per-subjek):
aturan RMSSD+HR **0,839 [0,773–0,897]** · HR-saja **0,871 [0,808–0,925]** ·
1D-CNN 0,878 (pembanding, tidak dipakai) · LLM-sebagai-pelabel 0,672 (ditolak).

**397 tes Python · 207 tes frontend**, sebagian besar teruji-mutasi.

---

## 2. Yang SUDAH terjadi di dunia nyata (bukan lab)

**HW9 lolos uji hari pertama (20 Agt)** — bit RR menyala, interval asli.

**Tiga sesi pilot manusia sungguhan** (arsip: `outputs/session_archive/`):

| Sesi | Hasil | Pelajaran |
|---|---|---|
| 1 (26 Agt) | semua `low`; laporan diri "tenang" → **SEPAKAT** | offset 1 dtk (tanpa prelude) → evidence `minimal` |
| 2 | 2 `moderate` didorong RMSSD; laporan diri "tenang" → **TIDAK sepakat** | HR bilang tenang; HR-saja = laporan diri. Baseline tercemar (main HP sebelum mulai, HR 95 → gerbang menyala BENAR) |
| 3 | GAGAL 422 | aplikasi lain merebut sensor; saat itu belum ada watchdog & alasan servernya dibuang frontend — dua-duanya sudah diperbaiki |

Label laporan-diri tercatat DI DALAM berkas arsipnya masing-masing.

---

## 3. Yang dibangun di sesi 26 Agustus (BELUM di-commit — ~28 berkas!)

- **Pemeriksa kelayakan sinyal** (`features/signal_fitness.py` + `SignalFitnessConfig`):
  per-REKAMAN, bukan per-jenis-perangkat. Tiga cek: outlier fase jawab >10%,
  denyut hilang >2%, lantai kuantisasi >30% dari RMSSD istirahat. RMSSD yang tak
  layak di-NaN-kan saat penilaian (aturan otomatis menilai dari HR saja) tapi
  tetap dilaporkan di lapisan teknis. Blok `signal_fitness` ikut di respons API.
  HW9 LOLOS semua cek, bahkan saat bicara — jadi RMSSD-nya dipertahankan.
- **Arsip sesi berizin** (`backend/hrv_api/services/archive.py`): dua kunci —
  centang persetujuan dari pengguna + `HRV_ARCHIVE_DIR` dari operator. Sesi
  GAGAL yang berizin juga diarsipkan (rekamannya justru data paling berharga).
- **Watchdog aliran denyut**: 5 dtk sunyi saat "tersambung" → banner merah di
  layar sesi. `gattserverdisconnected` TIDAK menyala saat aplikasi lain merebut
  sensor — hanya kedatangan denyut yang bisa mendeteksinya.
- **Detail 422 sampai ke layar**: `ApiError.serverDetail` ditampilkan di layar
  gagal. Sebelumnya semua kegagalan tampak identik.
- **Layar hasil**: dashboard (3 kartu ringkas + radar 3 sumbu Calm/Recovery/
  Resilience + linimasa + slider per pertanyaan) + **grafik detak jantung per
  pertanyaan** (diiris di browser dari rekaman yang sudah di memori — kontrak
  API tidak berubah; jalur unggah V2 belum digambar, disengaja).
- **Stream detak live saat sesi** (keputusan pemilik 26 Agt, menimpa aturan lama
  "no live bpm" — pagar: satu warna, tanpa zona, skala-y terkunci 40–160).
- **Simulator dev memutar rekaman WESAD S2 sungguhan 10× cepat**; jam sesi ikut
  faktor yang sama (`SIMULATION_SPEED`, dipakai DUA tempat — jangan pisahkan).
- **`docs/openapi-hrv.json`** — spec dibangkitkan dari kode, artefak serah terima.
- Mode pengembang memakai data tiruan penuh (`?dev=1` → fixture, banner tetap).

## 4. Yang tersisa sebelum "terintegrasi" — urut

1. **Commit** semua perubahan di hrv-rag.
2. **Rapat kontrak dengan Tegar** — agendanya §5 `rancangan-rag-hrv.md` di repo
   karirlink: (a) `hrv_score` tidak akan diisi → usul hapus; (b) `heart_rate`
   TIDAK boleh dibaca jalur evaluasi KSAO; (c) aturan tampilan mengikat.
   Plus satu: konfirmasi kunci Gemini tim (`GEMINI_API_KEY_KARIRLINK` di .env —
   AWAS: sempat jadi duplikat `GEMINI_API_KEY` dan diam-diam aktif; python-dotenv
   memakai baris TERAKHIR saat nama sama) boleh dipakai modul ini → itu jawaban
   penghalang kuota produksi.
3. **Satu sesi pilot bersih**: prelude 2 mnt diam + 6 pertanyaan + jeda 15–20
   dtk sebelum "Lanjut" → kolom recovery & kuadran ketahanan terisi pertama kali.
4. **Deploy staging** (modul masih di laptop; cold start scipy/neurokit2 nyata).
5. Port akuisisi Bluetooth ke Next.js mereka + jalur tulis `ExternalSignal`
   (`signalType: 'heart_rate'`, payload = SessionResponse utuh; granularitas
   per-pertanyaan hidup DI DALAM payload).

Sisi TA (bukan penghalang integrasi): jalankan ablasi tanpa-KB & chunk-acak
(kode SIAP: `--ablation none|random`, prompt buku-tertutup terpisah; belum pernah
dijalankan — judul TA menyebut RAG dan itu buktinya); verifikasi 11 sitasi KB;
sesi dua-perangkat HW9+H808S untuk sertifikasi bias RMSSD (H808S belum ada).

---

## 5. Menjalankan untuk pilot

```bash
HRV_API_KEYS=kunci-lokal HRV_CORS_ORIGINS=http://localhost:5173 HRV_ARCHIVE_DIR=outputs/session_archive python -m uvicorn hrv_api.app:app --app-dir backend --port 8000
```

Frontend: `npm run dev --prefix frontend` (`.env.local` sudah benar:
mock=false, base=8000, key=kunci-lokal). Tes frontend HARUS dari dalam
`frontend/`. Sesi nyata: mode pengembang MATI (dev=1 → data tiruan, tidak ada
yang tersimpan), centang persetujuan, sensor tersambung 2 mnt sebelum mulai
DAN dua menit terakhirnya benar-benar diam (pelajaran sesi 2).

## 6. Jebakan yang sudah menggigit — jangan terulang

- **python-dotenv: nama kunci ganda → baris terakhir menang, tanpa peringatan.**
- **Aplikasi lain menyambar sensor BLE**: koneksi tampak hidup, notifikasi mati.
  Watchdog kedatangan denyut satu-satunya deteksi. Wajib disebut ke tim web.
- **Tab tersembunyi men-throttle timer**: simulator dev (rantai setTimeout)
  melambat, jam sesi (Date.now) tidak → dua jam berpisah. Hanya di pratinjau
  headless; sensor asli kebal (event BLE, bukan timer).
- **`SIMULATION_SPEED` dipakai jam sesi DAN pemutar denyut** — ubah satu tanpa
  yang lain = tiap pertanyaan dinilai dari menit rekaman yang salah, tanpa error.
- **Offset dua jam** (`offset_sec`): sensor mengalir sejak tersambung, jam sesi
  sejak tombol. Kelas bug yang sama dijaga tes di backend DAN client
  (`questionHeartRate.test.ts`).
- `cfg.model` vs `model_label` di kunci cache; tes yang tidak menggigit
  (selalu uji mutasi); `sys.stdout.reconfigure` untuk konsol Windows —
  semua masih berlaku dari handover lama.

## 7. Cara kerja yang diharapkan

- Bahasa Indonesia natural, kalimat pendek; jangan pakai kode BACKLOG tanpa
  menjelaskan isinya. Setiap perubahan bawa tes + buktikan menggigit (mutasi).
- Verifikasi empiris, jangan klaim dari penalaran. Tanya dulu untuk keputusan
  bahasa/framework/arsitektur. Kerjakan bertahap.
