# BACKLOG — Interpretasi Tingkat Tekanan dari HRV dengan RAG

Tugas Akhir Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Terakhir diperbarui: 31 Juli 2026

> Berkas ini melacak pekerjaan. Aturan desain dan alasan ilmiahnya ada di
> `CLAUDE.md`; di sini hanya **apa yang dikerjakan, urutannya, dan statusnya**.

Status: `belum` · `jalan` · `selesai` · `tulis-ulang` · `blokir`

---

## Keputusan Terkunci

Sudah disepakati, tidak perlu dibahas ulang kecuali ada alasan baru.

| # | Keputusan | Alasan singkat |
|---|---|---|
| K1 | Repo resmi di `Documents\hrv-rag` | Di luar OneDrive, aman untuk git & dataset besar |
| K2 | PSD dihitung **dua metode** berdampingan: interpolasi 4 Hz + Welch, dan Lomb-Scargle | CLAUDE.md ambigu; dua kolom terpisah jadi bahan pembahasan sidang |
| K3 | Retrieval **manual** (cosine similarity), tanpa LangChain/LlamaIndex | KB hanya ~15 chunk; kode manual lebih mudah dipertanggungjawabkan |
| K4 | Keluaran **dua lapis**: `tampilan_user` (bahasa awam) + `data_teknis` (angka lengkap) | User tidak boleh melihat RMSSD/LF-HF — tidak sesuai UX |
| K5 | **Composure dilebur** ke pemulihan, bukan skor terpisah | Duplikatif secara teknis; label sifat bertabrakan dengan Aturan Wajib #4 |
| K6 | **Beban kognitif ditampilkan**, dibedakan lewat jenis pertanyaan | Tanda HRV-nya identik dengan stres; pembedanya konteks, bukan fisiologi |
| K7 | WESAD `amusement` **tidak dipakai** sama sekali | Sesuai CLAUDE.md; tidak dijadikan kontrol negatif |
| K8 | Dataset ditambah **bertahap**: WESAD selesai penuh → SWELL-KW → UBFC-Phys | Hindari mengerjakan tiga dataset sekaligus sebelum satu pun tuntas |
| K9 | Antisipasi diukur **di tingkat sesi**, bukan per pertanyaan | Jendela 5–10 dtk di bawah resolusi segmen 60 dtk — tidak terukur |
| K10 | Subjek WESAD dibagi **5 pengembangan / 10 pengujian**, per subjek (bukan per segmen) | (a) 10 subjek uji → satu subjek bernilai 10%, angka utama cukup stabil; dengan 5 subjek satu orang bernilai 20% dan F1 jadi rapuh. (b) 5 subjek cukup untuk menyetel prompt tanpa memboroskan panggilan API. (c) Pembagian per segmen akan membocorkan informasi karena baseline dihitung per subjek |
| K11 | Jeda pemulihan 60 dtk **hanya untuk pertanyaan sulit** | 60 dtk adalah lantai keras (= panjang segmen); memberlakukannya ke semua pertanyaan membuat sesi terlalu panjang. Pertanyaan biasa tetap dapat reaktivitas, hanya pemulihannya tidak dilaporkan |
| K15 | **Seluruh kode, KB, kueri, dan prompt berbahasa Inggris**; keluaran LLM untuk pengguna tetap Bahasa Indonesia | Kueri Inggris terhadap KB Indonesia menurunkan skor retrieval 0,03–0,08 dan sempat membuat satu kueri jatuh di bawah ambang sehingga mengembalikan nol chunk. Satu bahasa menghilangkan variabel tak terkendali itu |
| K13 | **Tanpa vector store** — 23 chunk disimpan sebagai matriks numpy | Perpanjangan K3. Indeks pencarian baru berguna di puluhan ribu dokumen; di sini hanya menambah dependensi. Pencarian = satu perkalian matriks |
| K14 | Embedding **`gemini-embedding-001`**, SDK **`google-genai`** | Bukan pilihan: `text-embedding-004` mengembalikan 404, dan `google-generativeai` sudah usang serta tidak terpasang |
| K12 | OOP hanya pada dua sumbu variasi nyata: **modalitas** dan **dataset** | Abstraksi di tempat yang memang bervariasi; sisanya fungsi biasa agar tetap mudah dijelaskan baris per baris |

---

## Fakta Lingkungan (terverifikasi 31 Juli 2026)

- Python 3.10.6 · neurokit2 0.2.13 · numpy 2.2.6 — semua tersedia
- WESAD ada di `Documents\WESAD\` (15 subjek, S2–S17)
- WESAD S2: ECG chest 700 Hz & BVP wrist 64 Hz & ACC wrist, durasi sama 6079 dtk
  → klaim "ECG+PPG dari subjek sama" terverifikasi
- S2: baseline 1144 dtk, stress 615 dtk
- **SWELL-KW dan UBFC-Phys belum ada di komputer ini** → lihat T7.0 dan T8.0

---

## Tahap 0 — Fondasi Repo

| ID | Tugas | Status |
|---|---|---|
| T0.1 | Struktur folder sesuai CLAUDE.md (`data/raw`, `data/processed`, `kb`, `src`, `notebooks`, `outputs`) | selesai |
| T0.2 | Salin CLAUDE.md, Rancangan, knowledge base ke repo (checksum terverifikasi) | selesai |
| T0.3 | `requirements.txt` disesuaikan: buang llama-index/langchain & sentence-transformers, tambah scikit-learn/matplotlib/seaborn | selesai |
| T0.4 | `.gitignore` untuk `.env`, `data/raw`, `data/processed`, `outputs` | selesai |
| T0.5 | ~~Hapus dokumen kembar di OneDrive~~ — diputuskan **tidak perlu dihapus** | selesai |
| T0.6 | `git init` + commit awal — **ditunda atas permintaan** | belum |
| T0.7 | `.env` berisi `GEMINI_API_KEY` — **ada dan terverifikasi bekerja**. `.gitignore` sudah mengabaikannya kembali | selesai |

---

## Tahap 1 — `preprocessing/base.py` + `preprocessing/ecg.py`  ✅ SELESAI

Kode lama `src/preprocess.py` **tidak sesuai spesifikasi CLAUDE.md** dan ditulis ulang, bukan ditambal.
Kode lama diarsipkan di `_arsip_tahap1_lama/` untuk perbandingan.

**Temuan saat verifikasi:** percobaan membandingkan RR terhadap "interval terakhir yang
diterima" (alih-alih interval tepat sebelumnya) membuat nilai acuan membeku dan menolak
denyut secara beruntun — terukur **59,5% outlier pada S2 kondisi tertekan**, padahal
kriteria harfiah hanya 1,5%. Sudah dikembalikan ke kriteria harfiah CLAUDE.md.
Hasil akhir seluruh subjek pengembangan: outlier 0,0–4,2%, semua di bawah gate 10%.

| ID | Tugas | Status |
|---|---|---|
| T1.1 | Ganti nama `preprocess.py` → `preprocess_ecg.py` (file terpisah, bukan percabangan `if`) | selesai |
| T1.2 | Quality check eksplisit: clipping, flat-line, derau berlebih | selesai |
| T1.3 | Butterworth **orde 2** (kode lama orde 3) + notch 50 Hz | selesai |
| T1.4 | Deteksi puncak R (NeuroKit2) → deret RR | selesai |
| T1.5 | Koreksi ektopik **sesuai spesifikasi**: RR di luar 0,3–2,0 dtk **atau** selisih >20% dari interval **sebelumnya** (kode lama pakai median lokal 5 denyut) | selesai |
| T1.6 | Gate baru: segmen dengan outlier **>10% dibuang** | selesai |
| T1.7 | Keluarkan penanda outlier per denyut agar gate T1.6 bisa diterapkan per segmen | selesai |
| T1.8 | Semua parameter numerik pindah ke `config.py` dengan komentar alasan | selesai |

---

## Tahap 2 — `features/`

| ID | Tugas | Status |
|---|---|---|
| T2.1 | Segmentasi 60 dtk **overlap 30 dtk** (kode lama tanpa overlap) | selesai |
| T2.2 | Fitur domain waktu: meanRR, meanHR, SDNN, RMSSD, pNN50 | selesai |
| T2.3 | Domain frekuensi **dua metode** (K2): kolom `*_welch` dan `*_ls` | selesai |
| T2.4 | Kolom wajib: `subjek`, `modalitas`, `fase`, `kualitas_sinyal` | selesai |
| T2.5 | Baseline per subjek = median segmen fase kalibrasi | selesai |
| T2.6 | Reaktivitas (% perubahan terhadap baseline) | selesai |
| T2.7 | **Pemulihan** — rumus + pengaman ditulis di `features/dynamics.py`, **terverifikasi lewat 10 uji** di `tests/test_dynamics.py` (termasuk contoh acuan S2 = 52,99%). Belum dijalankan pada data sesi nyata karena WESAD tidak punya fase jeda | selesai |
| T2.8 | **Indeks ketahanan** — kuadran 2×2 terverifikasi lewat 3 uji (empat kuadran + nilai mutlak + sumbu hilang). Ambangnya masih sementara, wajib dikalibrasi di 5 subjek dev lalu dibekukan | jalan |
| T2.9 | Indeks **beban kognitif** (K6) — dibedakan lewat metadata jenis pertanyaan | belum |
| T2.10 | Indeks **arousal** | belum |
| T2.11 | Timeline per pertanyaan: urutkan segmen berdasarkan reaktivitas (kode, bukan LLM) | selesai |
| T2.12 | Bandingkan Welch vs Lomb-Scargle, catat selisihnya sebagai bahan sidang | selesai |

---

## Tahap 2b — Skema Masukan & Keluaran

Dipisah karena dipakai bersama oleh Tahap 4, 5, dan 9.

| ID | Tugas | Status |
|---|---|---|
| T2b.1 | Skema masukan tunggal untuk produksi **dan** validasi (label dataset mengisi slot yang di produksi diisi user) | belum |
| T2b.2 | Skema keluaran dua lapis (K4) | belum |
| T2b.3 | Linimasa sesi **disetujui, versi cepat ~15,5 mnt**: adaptasi 1 → kalibrasi 4 → pengarahan 2 → jawab 90 dtk → jeda 60 dtk (sulit) / 20 dtk (biasa). Sudah masuk `SessionConfig` | selesai |
| T2b.4 | Anonimisasi: tidak ada nama/NRP/email yang dikirim ke LLM | belum |

---

## Tahap 3a — Rekayasa Isi Knowledge Base

KB bukan bahan yang sudah jadi — ia **produk kerja TA ini**. Kualitas RAG dibatasi
kualitas KB, jadi ini dikerjakan sebelum `kb_index.py`.

**Status `kb_v2.0` (3 Agustus 2026):** knowledge base diterjemahkan ke Bahasa Inggris
(keputusan K15) agar retrieval satu bahasa. Isi, ID chunk, dan rujukannya tidak berubah
dari `kb_v1.1` — hanya bahasanya. Skor retrieval naik 0,03–0,08 di semua kueri uji.

**Status `kb_v1.1` (versi Indonesia, digantikan):** 23 chunk (naik dari 15), rerata 92 kata,
rentang 80–108 kata, simpangan baku 8 kata. Semua chunk punya ID unik. Versi lama
diarsipkan di `kb/versi/knowledge_base_HRV_v1.0.md`.

Delapan chunk baru: `KB-LFHF-02`, `KB-RECOV-02`, `KB-CONF-02`, `KB-COGN-01`,
`KB-AROUS-01`, `KB-MODAL-01`, `KB-MODAL-02`, `KB-INTERP-02`.

**Lubang cakupan yang sudah teridentifikasi:**

| ID | Tugas | Status |
|---|---|---|
| T3a.1 | **Chunk PPG/PRV vs ECG** — KB sekarang **tidak punya satu kalimat pun** soal ini, padahal Aturan Wajib #5 menyuruh LLM menyesuaikan keyakinan berdasarkan modalitas. Tanpa chunk ini, LLM tidak punya dasar untuk melakukannya | selesai |
| T3a.2 | **Chunk beban kognitif** — dibutuhkan K6; CLAUDE.md sendiri memperkirakan SWELL akan gagal justru karena KB terlalu bias ke stres sosial-evaluatif | selesai |
| T3a.3 | **Chunk arousal vs valensi** — dibutuhkan indeks arousal (T2.10); alasan amusement dikecualikan sekarang hanya ada di CLAUDE.md, tidak di KB | selesai |
| T3a.4 | **Chunk kuantifikasi pemulihan** — chunk pemulihan sekarang kualitatif; butuh dasar untuk T2.7 | selesai |
| T3a.5 | Sumber diperluas dari 3 → 14 rujukan. **11 rujukan baru bertanda ⚠ BELUM DIVERIFIKASI** — Salma wajib membuka tiap sumber dan memastikan isinya mendukung klaim chunk yang menyitasinya | jalan |
| T3a.6 | Beri **ID stabil tiap chunk** (mis. `KB-RMSSD-01`) — wajib untuk mengisi field `rujukan` di keluaran LLM dan untuk gold standard T3b.4 | selesai |
| T3a.7 | Samakan panjang chunk — sekarang timpang (4–8 baris); chunk terlalu pendek buruk saat retrieval | selesai |
| T3a.8 | **Versi KB** (mis. `kb_v1.0`) dicap ke tiap keluaran — hasil berubah kalau KB berubah, jadi hasil tanpa versi KB tidak bisa direproduksi | selesai |
| T3a.10 | **Chunk pengaruh berbicara terhadap HRV** — lubang yang baru ketahuan dari L9. KB sekarang menyebut "ritme pernapasan" sebagai faktor pengganggu, tapi tidak menjelaskan bahwa TUGAS BERBICARA itu sendiri mengubah pola napas dan dapat menaikkan HF/RMSSD. Tanpa chunk ini, LLM tidak punya dasar menjelaskan subjek berpola terbalik | selesai |
| T3a.9 | Tiap chunk kini punya baris **Rujukan** eksplisit di bawah ID-nya. Ketepatan isinya menunggu verifikasi T3a.5 | jalan |

## Tahap 3b — `kb_index.py`

| ID | Tugas | Status |
|---|---|---|
| T3b.1 | Potong KB per heading `##` | selesai |
| T3b.2 | Embedding `gemini-embedding-001` (3072 dim, batch, `task_type` dibedakan dokumen/kueri). `text-embedding-004` **404 — tidak tersedia** | selesai |
| T3b.3 | ~~Chroma~~ → `vectors.npy` + `meta.json` di `data/processed/kb_index/`. Keputusan K13 | selesai |
| T3b.4 | **Gold-standard mapping**: kondisi fitur → chunk yang *seharusnya* terambil (dasar Precision@k/Recall@k/MRR di T5.5). Dibuat manual oleh Salma, sebelum melihat hasil retrieval, supaya tidak bias | belum |

---

## Tahap 4 — `rag.py`

| ID | Tugas | Status |
|---|---|---|
| T4.1 | Fitur → deskripsi tekstual ("RMSSD 35% di bawah baseline, LF/HF meningkat") | belum |
| T4.2 | Retrieval manual: cosine similarity, top-k | belum |
| T4.3 | Susun prompt: instruksi + konteks KB + fitur + **modalitas** (Aturan Wajib #5) | belum |
| T4.4 | Structured output JSON Gemini 2.5 Flash | belum |
| T4.5 | Pagar anti-halusinasi: hanya jawab dari konteks, wajib menyatakan ketidakpastian | belum |
| T4.6 | Pastikan LLM **tidak pernah** diminta menghitung angka (Aturan Wajib #1) | belum |

---

## Tahap 5 — `validate.py`

| ID | Tugas | Status |
|---|---|---|
| T5.1 | Metrik klasifikasi **per dataset & per modalitas** — jangan digabung | belum |
| T5.2 | WESAD: F1 biner, confusion matrix, Cohen's Kappa | belum |
| T5.3 | Catatan independensi sampel: segmen overlap 30 dtk **tidak independen** | belum |
| T5.4 | **Konsistensi antar-run**: prompt sama 3–5×, ukur variasi | belum |
| T5.5 | **Kualitas retrieval**: Precision@k, Recall@k, MRR (butuh T3.4) | belum |
| T5.6 | **Faithfulness**: tiap klaim di `alasan` didukung chunk terambil | belum |
| T5.7 | **Kalibrasi skor keyakinan** vs kebenaran prediksi | belum |

---

## Skema Pengujian

Tiga lapis berbeda yang sering tertukar. `validate.py` (Tahap 5) hanya
mengerjakan lapis 2.

### Lapis 1 — Uji Perangkat Lunak (apakah kodenya benar?)

**Status: 62 uji, semua lolos** (`python -m pytest tests/ -q`). Uji tambahan di luar
daftar semula: rumus pemulihan & kuadran ketahanan (`tests/test_dynamics.py`), yang
justru paling penting karena WESAD tidak bisa mengujinya sama sekali.

Aturan Wajib #1 menempatkan **kode sebagai sumber kebenaran angka**. Kalau kode
salah hitung, seluruh TA ikut salah dan LLM tidak bisa disalahkan. Jadi kode
wajib diuji dengan masukan yang jawabannya sudah diketahui.

| ID | Tugas | Status |
|---|---|---|
| U1.1 | Uji fitur domain waktu dengan deret RR sintetis ber-RMSSD/SDNN/pNN50 yang dihitung tangan | selesai |
| U1.2 | Uji domain frekuensi dengan sinyal sintetis: RR termodulasi sinus 0,25 Hz harus muncul sebagai puncak HF | selesai |
| U1.3 | Uji koreksi ektopik: sisipkan denyut ektopik buatan, pastikan tertandai & terkoreksi | selesai |
| U1.4 | Uji gate outlier >10%: buat segmen rusak, pastikan benar-benar dibuang | selesai |
| U1.5 | Uji segmentasi overlap: hitung jumlah segmen yang seharusnya dari durasi tertentu | selesai |
| U1.6 | Uji reaktivitas: baseline dan segmen identik harus menghasilkan delta 0% | selesai |
| U1.7 | Uji parser JSON keluaran LLM: keluaran cacat/terpotong tidak boleh membuat pipeline mati | blokir (menunggu Tahap 4) |

### Lapis 2 — Validasi Sistem (apakah tafsirnya benar?)

Metrik terhadap label — rinciannya di Tahap 5.

### Lapis 3 — Rancangan Eksperimen (apakah RAG-nya berguna?)

**Ini yang paling menentukan pertahanan sidang.** Tanpa pembanding, tidak ada
cara menjawab "dari mana Anda tahu RAG-nya membantu?"

| ID | Tugas | Status |
|---|---|---|
| U3.1 | **Pembanding aturan ambang** (tanpa LLM sama sekali): if RMSSD turun >X% → tinggi. Kalau RAG tidak mengalahkan ini, LLM tidak memberi nilai tambah | belum |
| U3.2 | **Ablasi: LLM tanpa KB** (fitur langsung ke Gemini, tanpa retrieval). Selisihnya = kontribusi nyata knowledge base | belum |
| U3.3 | **Ablasi: chunk acak** menggantikan chunk relevan. Kalau hasilnya tidak turun, berarti retrieval tidak berperan dan sistem hanya mengandalkan pengetahuan bawaan LLM | belum |
| U3.4 | **Sapuan nilai k** (k=1,3,5,7) — berapa chunk yang optimal | belum |
| U3.5 | **Sapuan temperature** — kaitkan dengan konsistensi antar-run (T5.4) | belum |
| U3.6 | Ablasi: prompt tanpa info modalitas — apakah skor keyakinan benar-benar berubah? Menguji Aturan Wajib #5 | belum |

### Protokol Pengujian (wajib ditetapkan **sebelum** menjalankan evaluasi akhir)

| ID | Tugas | Status |
|---|---|---|
| U4.1 | **Pisah subjek pengembangan vs pengujian** — disetujui. Dev: S2, S6, S10, S14, S17 (dipilih menyebar). Uji: 10 sisanya, disegel. Sudah masuk `SplitConfig` | selesai |
| U4.2 | Segel prompt & KB (beri versi, bekukan) sebelum menyentuh subjek uji | belum |
| U4.3 | Tetapkan jumlah run untuk konsistensi (3 atau 5) dan cara melaporkan variasinya | belum |
| U4.4 | Catat versi model Gemini di tiap keluaran — model bisa diperbarui pihak Google dan hasil ikut berubah | belum |
| U4.5 | Simpan seluruh keluaran mentah LLM, bukan hanya labelnya — supaya faithfulness (T5.6) bisa diaudit ulang | belum |

---

## Tahap 6 — `preprocess_ppg.py` (WESAD wrist BVP)

| ID | Tugas | Status |
|---|---|---|
| T6.1 | Bandpass **0,5–8 Hz**, deteksi puncak sistolik → deret IBI | belum |
| T6.2 | Buang artefak gerakan pakai `wrist['ACC']` | belum |
| T6.3 | Pakai ulang `features.py` apa adanya, `modalitas="PPG"` | belum |
| T6.4 | **Perbandingan berpasangan subjek sama**: ICC, Bland-Altman, label agreement — bukti terkuat di TA ini | belum |

---

## Tahap 7 — SWELL-KW *(setelah Tahap 1–6 tuntas, sesuai K8)*

| ID | Tugas | Status |
|---|---|---|
| T7.0 | **Dapatkan datasetnya — belum ada di komputer** | blokir |
| T7.1 | Loader ECG ~2048 Hz | belum |
| T7.2 | Pemetaan tiga tingkat: neutral→rendah, time pressure→sedang, interruption→tinggi | belum |
| T7.3 | Macro-F1 tiga kelas | belum |
| T7.4 | Uji kecukupan KB: apakah KB yang sama tetap bekerja pada tekanan **kognitif**, bukan hanya sosial-evaluatif | belum |

---

## Tahap 8 — UBFC-Phys *(paling akhir)*

| ID | Tugas | Status |
|---|---|---|
| T8.0 | **Dapatkan datasetnya — belum ada di komputer** | blokir |
| T8.1 | Loader PPG/BVP | belum |
| T8.2 | **Uji arah perubahan**, bukan klasifikasi — fase berbicara/aritmetika vs istirahat pada subjek sama | belum |
| T8.3 | Uji modalitas PPG lintas-perangkat (bukan Empatica) | belum |

---

## Tahap 9 — Penyajian

| ID | Tugas | Status |
|---|---|---|
| T9.1 | Backend FastAPI | belum |
| T9.2 | Dashboard Chart.js: timeline tekanan per pertanyaan | belum |
| T9.3 | Terapkan K4 — layar hanya menampilkan bahasa awam | belum |
| T9.4 | Bahasa perilaku, bukan label sifat ("butuh 90 detik kembali tenang", bukan "regulasi emosi rendah") | belum |

---

## Tahap 10 — Dokumentasi & Reproduksibilitas

Dikerjakan **berjalan bersama** tiap tahap, bukan ditumpuk di akhir. Alasan
keputusan paling mudah ditulis saat keputusannya baru diambil.

### Dokumentasi teknis

| ID | Tugas | Status |
|---|---|---|
| D1.1 | `README.md`: cara pasang, cara menjalankan, urutan skrip | belum |
| D1.2 | Docstring + komentar Bahasa Indonesia di bagian penting (aturan CLAUDE.md) | jalan |
| D1.3 | **Buat `Gambar_pipeline_RAG_HRV.png`** — `Rancangan_RAG_HRV.md:15` merujuknya tapi berkasnya tidak ada; rujukan rusak | belum |
| D1.4 | Diagram alir pra-pemrosesan per modalitas (ECG vs PPG) untuk bab metodologi | belum |
| D1.5 | Catatan tiap parameter numerik + alasannya, terpusat di `config.py` | belum |
| D1.6 | Kamus data: arti tiap kolom di CSV keluaran | belum |

### Dokumentasi RAG (khas pendekatan ini)

| ID | Tugas | Status |
|---|---|---|
| D2.1 | **Berkas prompt berversi** (`prompts/v1.md`, `v2.md`) — di RAG, prompt itu bagian dari sistem, setara arsitektur model di DL. Wajib bisa dilacak | belum |
| D2.2 | Catatan perubahan prompt: apa yang diubah, kenapa, dampaknya ke metrik | belum |
| D2.3 | Catatan perubahan KB: chunk apa ditambah/diubah, dampaknya | belum |
| D2.4 | Dokumentasikan gold-standard mapping (T3b.4) beserta alasan tiap pemetaan | belum |
| D2.5 | **Log eksperimen**: tiap run mencatat versi KB, versi prompt, versi model, k, temperature, timestamp | belum |

### Dokumentasi TA

| ID | Tugas | Status |
|---|---|---|
| D3.1 | Petakan tiap tahap backlog ke bab laporan | belum |
| D3.2 | Tulis bab keterbatasan dari daftar L1–L8 di bawah | belum |
| D3.3 | Siapkan jawaban untuk pertanyaan sidang yang bisa diduga (lihat kolom alasan di tiap keputusan K1–K9) | belum |
| D3.4 | Catat alasan perubahan metode dari 4 arsitektur DL → RAG | belum |

---

## Keterbatasan untuk Ditulis di Laporan

Bukan bug — ini yang harus jujur disebut dan hampir pasti ditanya penguji.

| ID | Keterbatasan |
|---|---|
| L1 | Baseline pra-wawancara bukan baseline netral sejati — kecemasan antisipatif membuat reaktivitas terukur **lebih kecil** dari sebenarnya. Mitigasi: buang fase adaptasi awal, pisahkan fase pengarahan |
| L2 | Segmen overlap 30 dtk **tidak independen** — memengaruhi tafsir F1 dan uji signifikansi |
| L3 | LF tidak stabil pada segmen 60 dtk. Bukti empiris di S2: satu segmen **baseline** menunjukkan LF/HF +288% padahal kondisi istirahat |
| L4 | Beban kognitif dan tekanan sosial punya tanda HRV **identik**; pemisahannya berbasis konteks pertanyaan, bukan fisiologi |
| L5 | LLM stokastik — perlu pelaporan konsistensi antar-run (T5.4) |
| L6 | Tidak ada satu macro-F1 tunggal untuk seluruh sistem; metrik selalu per dataset & per modalitas |
| L7 | **Meski tidak ada model dilatih, menyetel prompt dan KB sambil melihat hasil tetap bentuk *fitting*.** Karena itu perlu subjek uji yang disegel (U4.1). Ini kritik paling tajam yang bisa dilontarkan ke pendekatan "tanpa pelatihan" — lebih baik diakui dan ditangani duluan daripada dibantah |
| L9 | **Dua dari lima subjek pengembangan berpola terbalik**: S6 dan S10 menunjukkan RMSSD/HF/pNN50 NAIK saat TSST, padahal detak jantungnya ikut naik. Dugaan penyebab: (a) TSST menuntut subjek BERBICARA, dan napas dalam saat bicara menaikkan daya pita HF secara artifisial — pita HF memang digerakkan pernapasan; (b) baseline S10 tampak bukan istirahat sejati (RMSSD 14,4 ms, HR 99 bpm saat "diam", IQR relatif 52%). Konsekuensi: RMSSD saja tidak cukup, dan detak jantung — yang naik pada **kelima** subjek (+5,1% s.d. +74%) — adalah penanda paling konsisten |
| L10 | Persentase perubahan **tidak simetris**: penurunan mentok −100%, kenaikan tak terbatas (teramati +442%). Seluruh peringkasan reaktivitas WAJIB memakai median; memakai rata-rata sempat membalik kesimpulan pNN50 dari −61,2% jadi +61,8% |
| L8 | Sistem bergantung pada layanan pihak ketiga (Gemini). Model dapat diperbarui atau dihentikan Google, sehingga hasil persis bisa tidak terulang di masa depan. Mitigasi: catat versi model (U4.4) dan simpan keluaran mentah (U4.5) |

---

## Menunggu Keputusan

| ID | Pertanyaan |
|---|---|
| Q1 | **Terjawab: ya.** Linimasa disetujui, dipercepat jadi ~15,5 mnt |
| Q2 | **Terjawab.** Jeda 60 dtk hanya untuk pertanyaan sulit; pertanyaan biasa 20 dtk dan pemulihannya tidak dilaporkan |
| Q3 | **Terjawab: tidak perlu.** Dokumen OneDrive dibiarkan |
| Q4 | **Ditunda.** `git init` nanti saja |
| Q5 | **Terjawab: ya.** CLAUDE.md sudah disinkronkan |
| Q6 | **Terjawab: setuju 5/10.** Alasan tercatat di K10 |
| Q7 | **Terjawab.** Draft lubang KB disusun Claude, diperiksa & disitasi Salma |
| Q8 | **Terjawab.** Gambar pipeline dibuatkan |
| T3b.5 | **Ambang kemiripan dikalibrasi ulang untuk Inggris**: 0,65 → 0,60. Tak relevan 0,527–0,561; agak relevan 0,661; sangat relevan 0,807 | selesai |
| T3b.6 | **Peringatan mutu retrieval**: skor sangat berdempet (kueri 1: tiga teratas hanya berjarak 0,009). Pada 2 dari 5 kueri, chunk paling tepat kalah tipis — `KB-COGN-01` kalah 0,002 dari `KB-RECOV-02`. Perlu diukur di T3b.4 | belum |
| Q10 | Pemulihan & ketahanan tidak bisa diuji dengan WESAD (tidak ada fase jeda). Pilihan: (a) uji dengan data sintetis di U1 saja, (b) pakai WESAD label 4 (meditation) sebagai fase jeda — tapi urutan protokolnya berbeda antar subjek sehingga maknanya tidak setara. Rekomendasi: (a) |
| Q9 | **Terjawab: semua ablasi U3.1–U3.6 masuk laporan** |
