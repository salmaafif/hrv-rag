# BACKLOG SMARTWATCH — jalur bpm dan aplikasi Wear OS

Tugas Akhir Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Dibuat: 14 September 2026

> **Beda dengan berkas backlog lain.** `BACKLOG.md` melacak riset (T0–T11).
> `BACKLOG_INTEGRASI.md` melacak pemasangan modul yang sudah jadi ke web
> KARIRLINK (blok A–F). Berkas ini melacak **perluasan ke smartwatch**: jalur
> bpm yang membuat perangkat tanpa RR interval bisa dinilai, lalu aplikasi
> Wear OS untuk jam tangan yang menolak menyiarkan.
>
> Rancangan dan alasannya: `docs/RENCANA_JALUR_BPM_DAN_WEAR_OS.md`. **Baca itu
> dulu sebelum mengerjakan satu tugas pun di sini** — berkas ini hanya daftar
> pekerjaan, alasannya ada di sana. Diagram alur:
> `docs/images/alur-web.svg` dan `docs/images/alur-android.svg`.

Status: `belum` · `jalan` · `selesai` · `blokir`

Repo riset: `C:\Users\Salma Afifa Azis\Documents\hrv-rag`
Repo web: `C:\Users\Salma Afifa Azis\Documents\karirlink\karirlink`

---

## Peta cepat

| Blok | Isi | Repo | Branch | Status |
|---|---|---|---|---|
| W | Jalur bpm + dua tier di modul HRV | hrv-rag | `feat/tier-bpm` | belum |
| X | Gerbang NestJS + pengumpulan di peramban | karirlink | `feat/tier-bpm` | belum |
| Y | Penampungan aliran + kode pemasangan | karirlink | `feat/wear-pairing` | belum |
| Z | Aplikasi Wear OS `apps/wear-app` | karirlink | `feat/wear-app` | belum |
| V | Verifikasi perangkat dan angka nyata | — | — | belum |
| Q | Utang lama yang ditutup sekalian | keduanya | ikut blok terkait | belum |

W harus selesai sebelum X. X sebelum Y. Y sebelum Z, karena sampai Y selesai
tidak ada tempat untuk mengirim data jam tangan. V bisa jalan kapan saja dan
sebaiknya dimulai lebih awal, karena V2 mengisi angka yang dibutuhkan W5.

**Berhenti di akhir blok X sudah menghasilkan demo smartwatch yang berjalan**,
untuk jam tangan yang menyiarkan 0x180D. Blok Y dan Z hanya menambah jam tangan
yang menolak menyiarkan.

---

## Aturan keras — berlaku di seluruh backlog ini

1. **Jangan pernah menyunting `apps/hrv-service` dengan tangan.** Folder itu
   hasil `scripts/export_service.py`. Sunting di hrv-rag, ekspor ulang.
2. **Jangan pernah membuat RR palsu dari bpm.** `60000/bpm` yang diulang
   menghasilkan RMSSD tepat nol, dan setiap kandidat akan dinilai sangat
   tertekan tanpa satu pun pesan galat.
3. **Daftar putih, bukan daftar hitam.** Yang boleh ada di `baseline.values`
   untuk tier bpm hanya `mean_hr`. Jangan menyebut satu per satu fitur yang
   diblokir.
4. **Fitur variabilitas dihapus, bukan diisi NaN.**
5. **Jalur HW9 tidak boleh berubah perilakunya.** Ada tes regresi khusus untuk
   ini (W11).

---

## Blok W — jalur bpm di modul HRV

Repo `hrv-rag`, branch `feat/tier-bpm`. Garis dasar sebelum mulai: `pytest`
hijau, 215 tes lewat.

| ID | Tugas | Selesai bila | Status |
|---|---|---|---|
| W1 | `backend/hrv_api/schemas.py`: tambah `bpm_samples: list[BpmSample] \| None` dan `rr_coverage: float \| None` ke `AnalyzeRequest`. `BpmSample` = `at_sec >= 0`, `bpm` di 25–250. Perluas `_exactly_one_recording`. | Request tanpa `rr_ms` tapi berisi `bpm_samples` lolos validasi; request tanpa keduanya tetap ditolak | belum |
| W2 | Modul baru `src/hrv_rag/preprocessing/bpm.py` berisi `beats_from_bpm()`: tahan tiap sampel sampai sampel berikutnya, pancarkan denyut tiap `60000/bpm` ms | Rata-rata jendela 60 detik dari deret rekonstruksi sama dengan rata-rata aritmetik sampel bpm dalam toleransi 1 bpm | belum |
| W3 | Konstanta `BPM_TIER_FEATURES = ("mean_hr",)` di satu tempat, plus fungsi yang membuang fitur lain dari `BaselineProfile.values` dan `.spread` | `set(baseline.values) == {"mean_hr"}` pada sesi tier bpm | belum |
| W4 | `Prepared` membawa `tier` dan `rr_coverage`. Jalur bpm **melewati** `assess_signal`, menyusun `SignalFitness(rmssd_trusted=False, reasons=["perangkat melaporkan bpm, bukan interval antar denyut"])` langsung | Tes dengan monkeypatch membuktikan `assess_signal` tidak pernah dipanggil di jalur bpm | belum |
| W5 | Ambang cakupan sebagai `settings.tier.min_rr_coverage`, sementara 0.9, dengan komentar bahwa angkanya menunggu V2 | Ambang tidak ditulis sebagai literal di lebih dari satu tempat | belum |
| W6 | `baseline_block()`: `rmssd_ms` lewat `_clean` | Nilainya `null`, bukan `NaN` | belum |
| W7 | `measure_question`: saat rmssd tidak ada di `baseline.values`, alasan pemulihan jadi "perangkat tidak memberi bahan untuk menghitung pemulihan" | Tidak ada sesi tier bpm yang melaporkan "no quiet gap followed this question" padahal jedanya ada | belum |
| W8 | `most_triggering_question` dan `median_reactivity_pct` jatuh ke `delta_pct_mean_hr` saat rmssd tidak ada; respons menyebut `reactivity_basis` | Sesi tier bpm tetap menamai pertanyaan paling memicu, dan dasarnya terbaca dari respons | belum |
| W9 | Prompt narasi diberi tahu bahwa variabilitas tidak diukur, mengikuti pola `note_for_model` di `baseline.py` | Narasi tier bpm tidak pernah menyebut variabilitas | belum |
| W10 | Penanda asal di respons: `source: "beat_intervals" \| "bpm"` dan `tier` | Arsip lama dan baru bisa dibedakan tanpa menebak | belum |
| W11 | `tests/test_tier_bpm.py` — daftar lengkap di bawah tabel ini | Semua lewat, dan `pytest` penuh tetap hijau | belum |
| W12 | Jalankan `python scripts/export_service.py <path apps/hrv-service>` | PROVENANCE.md tercap commit yang benar | belum |

**Isi W11, jangan dikurangi.**

- Seluruh badan respons lolos `json.dumps(payload, allow_nan=False)`. Satu tes
  ini menutup seluruh kelas kebocoran NaN sekaligus, jadi tulis ini duluan.
- Tiap pertanyaan, `session_level`, dan timeline mengembalikan
  `delta_rmssd_pct` bernilai `None`.
- `baseline_block()["rmssd_ms"] is None`.
- `signal_fitness.rmssd_trusted is False`, dengan alasan yang menyebut bpm.
- `summary.resilience is None`, dan pemulihan tidak terhitung dengan alasan
  yang benar (bukan alasan soal jeda).
- **Regresi:** sesi ber-RR lengkap menghasilkan angka yang identik dengan
  sebelum perubahan. Kunci sebuah sesi contoh dan bandingkan responsnya
  bidang per bidang.

---

## Blok X — gerbang NestJS dan pengumpulan di peramban

Repo `karirlink`, branch `feat/tier-bpm`. Termasuk hasil ekspor W12; sebutkan
di pesan commit bahwa isi `apps/hrv-service` adalah ekspor, bukan ketikan.

| ID | Tugas | Selesai bila | Status |
|---|---|---|---|
| X1 | `apps/web`: kumpulkan `bpmSamples` berdampingan dengan `rrIntervals` pada tiap notifikasi | Perangkat tanpa RR tetap mengisi satu larik | belum |
| X2 | `submission.ts`: `recordedBeforeFirstSec` dihitung dari cap waktu sampel, **bukan** dari jumlah interval. Kiriman batal hanya bila RR dan bpm dua-duanya kosong. Hitung `rrCoverage` | Sesi jam tangan menghasilkan `baselineMinutes` yang benar | belum |
| X3 | `sebabKirimanBatal`: tambah sebab yang sesuai keadaan baru | Tidak ada sesi jam tangan yang dapat pesan "aliran denyutnya kosong" padahal bpm-nya penuh | belum |
| X4 | `SubmitHeartRateDto`: field `bpmSamples` dan `rrCoverage` beserta validasinya | Kiriman bpm-only diterima | belum |
| X5 | `HeartRateService.submit`: baris log menghitung sampel, bukan hanya interval | Log menyebut jumlah sampel dan cakupan | belum |
| X6 | `HrvModuleService.analyzeSession`: teruskan field baru ke snake_case | Tidak ada field yang hilang di perjalanan | belum |
| X7 | Panel hasil merender `tier` dan `reactivity_basis`; `recovery_pct: null` tampil "belum terukur" | Kartu tier bpm tidak menampilkan 0% di mana pun | belum |
| X8 | Tes: satu kiriman bpm-only tersimpan sebagai satu baris `ExternalSignal` | Tes lewat | belum |

Sebelum menambah nilai `tier` baru, periksa nilai yang sudah didefinisikan di
`docs/module-design/rancangan-rag-hrv.md` di repo karirlink. Field `tier` sudah
ada di kontrak dan sudah disebut di `CLAUDE.md`; ini nilai baru, bukan konsep
baru.

---

## Blok Y — penampungan aliran dan kode pemasangan

Repo `karirlink`, branch `feat/wear-pairing`. Semua di `apps/backend`, karena
butuh Prisma dan pemeriksaan kepemilikan sesi yang sudah ada di
`HeartRateService.sesiMilikPengguna`.

| ID | Tugas | Selesai bila | Status |
|---|---|---|---|
| Y1 | Skema Prisma untuk penampungan: `sessionId`, hash kode, hash token, `expiresAt`, baris sampel | Migrasi jalan di basis data bersih | belum |
| Y2 | Endpoint menerbitkan kode 6 digit, dipanggil kandidat terautentikasi, berumur pendek dan sekali pakai | Kode kedua untuk sesi yang sama membatalkan kode pertama | belum |
| Y3 | Endpoint menukar kode dengan token panjang; ada rate limit; kode hangus setelah ditukar | Tebakan berulang terhenti oleh rate limit | belum |
| Y4 | Endpoint aliran bertoken menerima `{detik monotonik, nilai}`; waktu dinding paket pertama dicatat sebagai patokan jam | Patokan tersimpan sekali, tidak tertimpa paket berikutnya | belum |
| Y5 | Penggabungan saat sesi ditutup: aliran + linimasa jadi satu kiriman ke hrv-service | Sesi jam tangan menghasilkan kartu | belum |
| Y6 | Retensi: penampungan dihapus saat sesi ditutup, dan sesi yatim kena TTL | Tidak ada baris sampel yang hidup lebih lama dari batas yang ditulis | belum |
| Y7 | Tes keamanan: kode kedaluwarsa ditolak, token salah ditolak, sesi milik orang lain dibalas 404 | Semua lewat | belum |

Kode enam digit hanya satu juta kemungkinan, jadi ia **hanya** boleh berfungsi
sebagai pintu penukaran: sekali pakai, berumur pendek, dibatasi lajunya. Yang
dipakai jam tangan selama sesi adalah token panjang hasil penukaran, bukan
kodenya.

---

## Blok Z — aplikasi Wear OS

Repo `karirlink`, folder `apps/wear-app`, branch `feat/wear-app`. Android
Studio dibuka di folder itu, bukan di akar monorepo.

| ID | Tugas | Selesai bila | Status |
|---|---|---|---|
| Z1 | Proyek Gradle minimal untuk Wear OS; tambahkan `.gradle/`, `local.properties`, `*.apk`, `captures/` ke `.gitignore` akar | `git status` bersih setelah satu build | belum |
| Z2 | Layar masukkan kode 6 digit: angka besar, tanpa keyboard penuh | Bisa diisi di layar arloji tanpa salah tekan | belum |
| Z3 | Izin `BODY_SENSORS` dan foreground service dengan notifikasi berjalan | Aliran tetap jalan saat layar mati | belum |
| Z4 | Baca `Sensor.TYPE_HEART_RATE`, buffer, kirim tiap N detik | Sampel tiba di backend dengan cap waktu monotonik yang rapi | belum |
| Z5 | Penanganan putus jaringan: antre lokal lalu kirim ulang. **Jangan interpolasi lubang** | Lubang dilaporkan sebagai cakupan, bukan ditambal | belum |
| Z6 | Berkas kontrak JSON di satu tempat, dirujuk aplikasi dan backend | Perubahan bentuk data hanya perlu satu suntingan | belum |
| Z7 | README `apps/wear-app` berisi langkah pemasangan lewat adb | Orang lain bisa memasang tanpa bertanya | belum |
| Z8 | Uji sesi 20 menit penuh | Cakupan sampel dilaporkan dan tidak ada putus yang tidak tercatat | belum |

---

## Blok V — verifikasi perangkat dan angka nyata

Tidak bergantung pada blok lain. Mulai secepatnya, karena V2 mengisi angka yang
dibutuhkan W5.

| ID | Tugas | Selesai bila | Status |
|---|---|---|---|
| V1 | Uji perangkat kandidat dengan `frontend/uji-siaran-hr.html`: interval laporan, bulat atau tidak, bendera bit 4 | Ada catatan per perangkat yang diuji | belum |
| V2 | Rekam protokol tiga blok dengan HW9, lihat cakupan RR yang normal pada perangkat sehat, lalu tetapkan ambang W5 di bawahnya | Ambangnya punya dasar rekaman, bukan tebakan | belum |
| V3 | Rekam serentak HW9 di lengan dan jam tangan di pergelangan | Dapat SD per jendela dan bias saat tertekan untuk perangkat yang benar-benar dipakai | belum |
| V4 | Cocokkan V3 ke tabel `docs/HASIL_SIMULASI_SMARTWATCH.md` | macro-F1 yang berlaku untuk perangkat itu tercatat | belum |
| V5 | `python scripts/simulate_watch.py --emulate` di laptop yang punya WESAD | Tabel interval pelaporan dan penghalusan terisi | belum |

---

## Blok Q — utang lama yang ditutup sekalian

| ID | Tugas | Selesai bila | Status |
|---|---|---|---|
| Q1 | `scripts/export_service.py --check`: ekspor ke folder sementara, bandingkan dengan salinan di karirlink, keluar dengan kode error kalau berbeda | Satu perintah bisa membuktikan salinannya belum disunting | belum |
| Q2 | Perbaiki komentar di `settings.py` yang menyatakan ambangnya berasal dari literatur; nilainya berasal dari kalibrasi grid pada lima subjek pengembangan | Tidak ada klaim sitasi yang tidak bisa ditunjukkan | belum |
| Q3 | Selaraskan `CLAUDE.md` karirlink dengan kode soal jalur panggilan lewat AI Gateway, sebagai koreksi bertanggal | Dokumen dan kode menyatakan hal yang sama | belum |

---

## Definisi selesai untuk seluruh backlog ini

Sebuah sesi wawancara yang direkam dengan jam tangan yang hanya melaporkan bpm
menghasilkan kartu Ulasan Ketenangan yang benar: ada tingkat tekanan per
pertanyaan dan per sesi, Pemulihan dan Ketahanan tertulis belum terukur dan
bukan nol, tidak ada satu pun angka variabilitas yang muncul di mana pun, dan
sesi yang direkam dengan HW9 tetap menghasilkan angka yang persis sama seperti
sebelum seluruh pekerjaan ini dimulai.
