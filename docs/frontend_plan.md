# Rencana Frontend & API — Web Demo Pengujian

Dokumen ini berisi konteks yang **tidak ada di kode** dan diperlukan siapa pun yang
mengerjakan frontend atau backend web. Ditulis 3 Agustus 2026.

Baca juga: `README.md` (cara menjalankan), `BACKLOG.md` (status pekerjaan),
`docs/development_journey.md` (alasan tiap keputusan).

---

## 1. Tujuan web ini

Web ini **bukan produk akhir**. Tujuannya dua:

1. Salma menguji sistem AI-nya sendiri secara visual, sebelum diserahkan
2. Memberi gambaran ke tim web KARIRLINK tentang bentuk aplikasinya nanti

Tim web akan membangun ulang frontend-nya. Yang benar-benar diserahkan adalah
**kontrak API**, bukan tampilannya. Jadi jangan habiskan waktu mempercantik UI.

---

## 2. Tiga versi dalam satu web

Dipilih lewat dropdown. Ketiganya memakai pipeline analisis yang **sama persis** —
yang berbeda hanya konteks yang tersedia dan satuan keluarannya.

| | V1 — Deteksi | V2 — Analisis Sesi | V3 — Simulasi Penuh |
|---|---|---|---|
| **Masukan** | Bluetooth / unggah file | Bluetooth / unggah file | Bluetooth, direkam saat wawancara |
| **Linimasa pertanyaan** | tidak ada | diisi pengguna | otomatis dari aplikasi |
| **Satuan keluaran** | per menit | per pertanyaan | per pertanyaan |
| **Interpretasi LLM** | ya, menarasikan garis waktu | ya, per pertanyaan | ya, per pertanyaan |
| **Wawancara berjalan di web?** | tidak | tidak | ya |

**V3 bukan analisis yang berbeda dari V2.** Bedanya hanya dari mana linimasa
pertanyaannya datang: di V2 pengguna memberi tahu, di V3 aplikasi sudah tahu karena
dialah yang menjalankan wawancaranya. Backend-nya identik.

Karena itu backend cukup **dua endpoint**, bukan tiga.

---

## 3. Kontrak API

Belum diimplementasikan. Bentuk di bawah ini yang disepakati, dan **frontend boleh
dibangun lebih dulu dengan data tiruan (mock) mengikuti bentuk ini**.

### `POST /api/v1/analyze/timeline` — untuk V1

**Masukan** (multipart/form-data):
- `file` — CSV interval RR, atau
- `rr_ms` — array angka (dari Bluetooth), sebagai JSON
- `baseline_minutes` — berapa menit awal dipakai sebagai baseline (bawaan: 4)
- `modality` — `"ECG"` atau `"PPG"`

#### Format CSV interval RR — DITETAPKAN 6 Agt 2026

**Tanpa header, satu kolom angka, satuan milidetik, satu interval per baris:**

```
856
842
871
863
```

Dipilih karena itulah keluaran mentah aplikasi pengukur denyut (Polar Sensor
Logger, Elite HRV, dan sejenisnya), sehingga pengguna tidak perlu menyunting
berkas sebelum mengunggah — dan menyuruh orang menyunting berkas justru
mengundang kesalahan yang lebih parah daripada yang dicegahnya.

Konsekuensinya berkas tidak membawa penanda satuan sama sekali, jadi berkas yang
salah satuan tidak bisa dibedakan dari yang benar hanya dari bentuknya.
`preprocessing/intervals.py` karena itu memeriksa terhadap fisiologi manusia dan
**menolak**, bukan menebak. Dua kekeliruan yang mudah terjadi:

| Isi berkas | Median | Ditolak dengan alasan |
|---|---|---|
| Detik (`0.856`) | < 10 | Semua nilai di luar rentang 0,3–2,0 dtk; tanpa penolakan, 100% denyut ditandai outlier dan laporannya jadi "tidak ada data" yang membingungkan |
| **Detak jantung** (`70`) | 10–300 | **Paling berbahaya.** BPM dan interval adalah kebalikan satu sama lain, jadi membacanya tertukar tidak sekadar salah skala — ia **membalik kesimpulan**. Jantung yang berpacu dilaporkan melambat, dan tekanan yang meningkat terbaca sebagai menenang |

Yang ditoleransi: baris header bila ada, baris kosong, nilai desimal, dan kolom
kedua (diabaikan). Yang tidak ditoleransi: baris rusak di tengah berkas —
melewatinya diam-diam akan memendekkan rekaman dan menggeser seluruh stempel
waktu sesudahnya.

**Catatan metodologis untuk sidang.** Masukan berupa interval RR **menggantikan**
tahap filter dan deteksi puncak, bukan melewatinya: alatnya sudah mengerjakan itu
pada sinyal mentah sebelum berkasnya keluar. Artinya untuk berkas unggahan, cabang
ECG dan PPG tidak berbeda sama sekali — modalitas hanya bertahan sebagai label yang
masuk ke prompt (Aturan Wajib #5). Pemisahan dua berkas yang diwajibkan CLAUDE.md
tetap berlaku untuk jalur dataset penelitian, yang memang mulai dari gelombang.

**Keluaran**:
```json
{
  "session_id": "demo-001",
  "modality": "ECG",
  "duration_sec": 900,
  "baseline": {
    "rmssd_ms": 32.0,
    "mean_hr_bpm": 73.0,
    "n_segments": 7,
    "is_stable": true,
    "warning": null
  },
  "timeline": [
    {
      "minute": 5,
      "start_sec": 240, "end_sec": 300,
      "level": "high",
      "score": 4,
      "delta_rmssd_pct": -79.8,
      "delta_hr_pct": 85.9,
      "evidence": ["RMSSD 80% below baseline (2 pt)",
                   "heart rate 86% above baseline (2 pt)"],
      "features_disagree": false
    }
  ],
  "summary": {
    "peak_minute": 5,
    "median_reactivity_pct": -74.9,
    "count_low": 12, "count_moderate": 3, "count_high": 5
  },
  "narrative": {
    "ringkasan": "...", "rekomendasi": "...", "penyemangat": "..."
  },
  "meta": { "kb_version": "kb_v2.0", "model": "gemini-2.5-flash",
            "trustworthy": true }
}
```

### `POST /api/v1/analyze/session` — untuk V2 dan V3

**Masukan**: sama seperti di atas, ditambah linimasa pertanyaan:
```json
{
  "questions": [
    { "number": 1, "text": "Ceritakan tentang diri Anda",
      "type": "introduction",
      "answer_start_sec": 0, "answer_end_sec": 90,
      "gap_end_sec": 150, "is_difficult": true }
  ]
}
```

`type` harus salah satu dari: `introduction`, `behavioural`, `technical`,
`numerical`, `situational`.

**Keluaran**:
```json
{
  "session_id": "demo-002",
  "baseline": { "...sama seperti di atas..." },
  "questions": [
    {
      "number": 1, "text": "...", "type": "introduction",
      "level": "high", "score": 4,
      "delta_rmssd_pct": -79.8, "delta_hr_pct": 85.9,
      "recovery_pct": 12.0,
      "recovery_note": "",
      "evidence": ["..."],
      "features_disagree": false,
      "penjelasan": "Saat menjawab pertanyaan ini tubuh Anda...",
      "saran": "Coba tarik napas dalam sebelum mulai menjawab."
    }
  ],
  "summary": {
    "most_triggering_question": 2,
    "resilience": "low resilience",
    "median_reactivity_pct": -74.9,
    "median_recovery_pct": 26.0
  },
  "narrative": { "ringkasan_sesi": "...", "penyemangat": "..." },
  "meta": { "...": "..." }
}
```

### Catatan penting soal keluaran

- `recovery_pct` **boleh `null`**, artinya tidak dapat diukur karena tidak ada jeda
  cukup panjang. **Jangan tampilkan sebagai 0%** — nol berarti "sama sekali tidak
  pulih", klaim yang sangat berbeda. Tampilkan sebagai "tidak diukur".
- `features_disagree: true` berarti RMSSD naik padahal detak jantung juga naik.
  Perlu ditandai di UI, karena pembacaannya lebih tidak pasti.
- `level` bernilai `low`, `moderate`, atau `high` — ditetapkan **aturan**, bukan LLM.
  Nilainya selalu sama untuk masukan yang sama.
- Angka teknis (`delta_rmssd_pct`, `score`, `evidence`) **jangan ditampilkan ke
  pengguna akhir**. Simpan untuk mode debug atau panel pengembang saja. Pengguna
  hanya melihat `level`, `penjelasan`, dan `saran`.

---

## 4. Keputusan teknis yang sudah diambil

| Hal | Keputusan | Alasan |
|---|---|---|
| Repo | **Satu repo (monorepo)**. Frontend di `frontend/`, API di `src/hrv_rag/api/` | Pengembang tunggal; frontend dan backend berubah bersamaan. Vercel/Railway bisa diarahkan ke subfolder |
| Frontend | **React** | Pilihan Salma; akan di-deploy untuk keperluan TA |
| Format file utama | **CSV interval RR** | Berkas WESAD `.pkl` ratusan MB — tidak realistis diunggah ke demo terhosting. CSV cuma beberapa KB |
| Kunci API | **Wajib di server**, tidak pernah di React | Apa pun di frontend bisa dibaca lewat DevTools; kunci akan terekspos |
| Bluetooth | Web Bluetooth API, Heart Rate Service standar | Hanya jalan di Chrome/Edge dan **wajib HTTPS** (kecuali `localhost`) |
| CORS | Harus diaktifkan di FastAPI | Frontend dan backend beda domain saat di-deploy |

---

## 5. Yang perlu diketahui soal data Bluetooth

Chest strap Bluetooth standar **tidak mengirim sinyal ECG mentah**. Yang dikirim
adalah **interval RR yang sudah jadi** — alat sudah mendeteksi denyutnya sendiri.

```
Dari file WESAD:  sinyal mentah → filter → deteksi puncak → interval RR → fitur
Dari Bluetooth:                                             interval RR → fitur
```

Kode saat ini **selalu mulai dari sinyal mentah**, jadi pintu masuk untuk interval
RR **belum ada** dan perlu ditambah di backend. Pekerjaannya kecil: lewati dua
langkah pertama, langsung ke koreksi ektopik.

---

## 6. Jebakan yang sudah diketahui

**V1 tetap butuh periode tenang.** Seluruh sistem bekerja dengan membandingkan ke
baseline orang itu sendiri. Tanpa periode tenang di awal rekaman, angkanya tidak
bermakna. Solusi: ambil beberapa menit pertama sebagai baseline otomatis, dan beri
tahu penguji bahwa awal rekaman harus kondisi tenang.

**Cold start saat demo.** Backend butuh `scipy`, `numpy`, `neurokit2` — ratusan MB.
Di hosting gratis, permintaan pertama setelah idle bisa menunggu 30–60 detik. Buka
halamannya beberapa menit sebelum demo di depan penguji.

**Segmen tumpang tindih 30 detik.** Garis waktu V1 bergeser tiap 30 detik, bukan
tiap menit penuh. Dua titik bertetangga berbagi separuh data yang sama — jangan
ditampilkan seolah dua pengukuran yang saling menguatkan.

---

## 7. Status: apa yang sudah ada dan belum

**Sudah ada dan teruji** (90 uji lolos):
- Pra-pemrosesan ECG dan PPG
- Ekstraksi fitur HRV, baseline, reaktivitas, pemulihan, ketahanan
- Aturan penentu tingkat tekanan — sudah dikalibrasi dan dibekukan
- Knowledge base 23 chunk + pencarian
- Pemanggilan LLM untuk narasi
- Pengelompokan segmen per pertanyaan

**Belum ada:**
- API FastAPI
- Pintu masuk interval RR (untuk Bluetooth dan CSV)
- Frontend

**Angka acuan** (subjek uji tersegel, 561 segmen): accuracy 0,852 · macro-F1 0,839 ·
Cohen's kappa 0,678.

---

## 8. Urutan yang disarankan

1. Frontend React dengan **data tiruan** mengikuti kontrak di bagian 3
2. Backend FastAPI + pintu masuk interval RR
3. Sambungkan keduanya
4. Deploy

Membangun frontend lebih dulu dengan data tiruan itu wajar — bentuk keluarannya
sudah ditetapkan, jadi tidak akan sia-sia.
