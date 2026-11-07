# BACKLOG — Interpretasi Tingkat Tekanan dari HRV dengan RAG

Tugas Akhir Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Terakhir diperbarui: 20 Agustus 2026 — **status disinkronkan dengan isi repo**

> Berkas ini melacak pekerjaan. Aturan desain dan alasan ilmiahnya ada di
> `CLAUDE.md`; di sini hanya **apa yang dikerjakan, urutannya, dan statusnya**.
>
> Susunan di sini mengikuti **urutan pengerjaan** (T0 → T10, U1 → U4). Untuk melihat
> satu bagian secara utuh — misalnya "frontend-ku sudah sampai mana" — pakai
> `docs/PETA_PEKERJAAN.md`, yang menyusun ulang isi yang sama **menurut domain**.

Status: `belum` · `jalan` · `selesai` · `tulis-ulang` · `blokir`

**Sinkronisasi 20 Agustus 2026.** Status di bawah diperiksa langsung terhadap isi
`src/`, `backend/`, `frontend/`, `scripts/`, `tests/`, `outputs/`, dan riwayat git —
bukan disalin dari catatan sebelumnya. Tujuh baris ternyata tertinggal dari kodenya.
Yang berubah: T9.2, T9.3, T9.4, U4.4, U4.5 menjadi `selesai`; U3.2 dan U3.3 menjadi
`jalan` karena **kodenya sudah ada tetapi pengukurannya belum dijalankan** — perbedaan
yang penting, sebab yang dinilai di sidang adalah angkanya, bukan kodenya.

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
| K16 | **Arsitektur gabungan**: aturan skor menentukan LABEL, LLM menulis PENJELASAN. Satu panggilan per sesi, bukan per segmen | Diukur, bukan diasumsikan: aturan mencapai macro-F1 0,828 / kappa 0,656, sedangkan LLM menjawab "uncertain" pada 6 dari 13 segmen istirahat yang dijawab benar oleh aturan. Aturan juga gratis, instan, luring, dan hasilnya sama tiap kali dijalankan — label yang berubah-ubah tidak layak ditampilkan ke pengguna. LLM memegang bagian yang memang lebih baik ia kerjakan: menyusun kalimat yang bisa ditindaklanjuti |
| K17 | **Model terlatih tidak dipakai untuk KARIRLINK** | Bukan soal biaya komputasi melainkan ketiadaan data: tidak ada satu pun sesi wawancara nyata berlabel tingkat stres. Mengumpulkannya butuh kuesioner tervalidasi per pertanyaan selama berbulan-bulan. Melatih dari WESAD pun tidak menyelesaikan — TSST di lab (berdiri, juri sungguhan, chest strap) berbeda dari orang duduk di kamar menghadap webcam. Lagi pula keluaran model hanya angka, sedangkan produknya butuh kalimat |
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
Kode lama diarsipkan di `archive/` untuk perbandingan.

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
| T2.9 | Indeks **beban kognitif** — sengaja BUKAN skor. Kode tidak bisa memisahkannya dari tekanan sosial (tanda HRV identik), jadi yang dihasilkan besar reaksi + kalimat dugaan berdasarkan jenis pertanyaan | selesai |
| T2.10 | Indeks **arousal** — dibaca dari detak jantung. Bukan pengukuran kedua: nilainya identik dengan Δ detak jantung, jadi tidak ditampilkan sebagai kolom terpisah agar tidak terkesan dua temuan yang saling menguatkan | selesai |
| T2.11 | Timeline per pertanyaan: urutkan segmen berdasarkan reaktivitas (kode, bukan LLM) | selesai |
| T2.12 | Bandingkan Welch vs Lomb-Scargle, catat selisihnya sebagai bahan sidang | selesai |

---

## Tahap 2c — Arsitektur Gabungan (K16)

Perubahan arah setelah bukti terkumpul: LLM tidak lagi menentukan label.

| ID | Tugas | Status |
|---|---|---|
| T2c.1 | `features/stress_level.py` — aturan skor 3 tingkat (rendah/sedang/tinggi), 0–4 poin dari RMSSD + detak jantung | selesai |
| T2c.2 | Ambang aturan di `StressRuleConfig` dengan alasan tiap angka | selesai |
| T2c.3 | 15 uji: batas ambang, determinisme, pola terbalik S6/S10 tetap terdeteksi | selesai |
| T2c.4 | `prompts/HRV_session_narrative.md` — prompt narasi, label dinyatakan sudah final | selesai |
| T2c.5 | `core/schemas.py` — `SessionNarrative`, **tanpa** field tingkat tekanan | selesai |
| T2c.6 | `rag/narrative.py` — satu panggilan per sesi, kueri dibangun dari sesi utuh | selesai |
| T2c.7 | `run_session.py` menampilkan label tanpa API | selesai |

| T2c.9 | **Kalibrasi ambang SELESAI & DIBEKUKAN** (3 Agt 2026). 81 kombinasi disapu pada 5 subjek dev. Hanya satu nilai berubah: RMSSD sedang −15% → −20%. macro-F1 dev naik 0,831 → 0,851 | selesai |
| T2c.10 | **Ambang TINGGI tidak dapat dikalibrasi dengan WESAD** — dataset biner, sehingga sedang & tinggi dipetakan ke kelas sama. Lima kombinasi teratas berskor identik. Nilai dari literatur dipertahankan; butuh SWELL-KW atau laporan-diri pengguna | blokir |

**Dampak biaya**: dari 5 panggilan/sesi (7.596 token masukan) menjadi 1 panggilan
(1.519 token). Turun lima kali lipat, dan pengguna menunggu ~10 detik, bukan semenit.

---

## Tahap 2b — Skema Masukan & Keluaran

Dipisah karena dipakai bersama oleh Tahap 4, 5, dan 9.

| ID | Tugas | Status |
|---|---|---|
| T2b.1 | Skema masukan tunggal untuk produksi **dan** validasi (label dataset mengisi slot yang di produksi diisi user) | selesai |
| T2b.2 | Skema keluaran dua lapis (K4) | selesai |
| T2b.3 | Linimasa sesi **disetujui, versi cepat ~13,5 mnt**: adaptasi 1 → kalibrasi **2** → pengarahan 2 → jawab 90 dtk → jeda 60 dtk (sulit) / 20 dtk (biasa). **Direvisi dua kali**: 4 → 3 menit (6 Agt), lalu 3 → 2 menit (7 Agt, atas masukan dosen bahwa menunggu terlalu lama). Alasannya UX, bukan statistik. **2 menit adalah LANTAI KERAS** — 1 menit menghasilkan deret denyut yang membentang hanya ~59 dtk (diukur dari denyut pertama ke terakhir, bukan dari timer mulai), sehingga tidak ada satu pun jendela 60 dtk yang muat: bukan baseline lemah, tapi **nol baseline**, dan sesi jadi tak ternilai sama sekali. Merapatkan geser pun tidak menolong — nol tetap nol | selesai |
| T2b.4 | **Geser baseline dirapatkan 30 → 15 dtk** (`baseline_overlap_sec`), khusus fase istirahat. Ini yang membuat 2 menit tetap layak: 2 menit dengan geser 15 dtk memberi 2–4 jendela, setara 3 menit dengan geser 30 dtk. Tidak menambah informasi — hanya menarik nilai tengah yang lebih stabil dari data yang sama. Diverifikasi pada fase istirahat WESAD penuh: baseline RMSSD hanya bergeser **0,07–1,33%**, dan **holdout tidak berubah sama sekali** (0,852 / 0,839 / 0,678). Dev bergeser tipis: macro-F1 0,851 → 0,837, kappa 0,703 → 0,676 | selesai |
| T2b.5 | **Jebakan yang sempat terjadi dan sudah diperbaiki.** Kerapatan baseline awalnya diterapkan di `extract_features`, sehingga ikut menggandakan baris fase istirahat di tabel fitur. Di WESAD baris itu **juga** contoh kelas "rendah", jadi satu sisi data uji berlipat dan macro-F1 dev jatuh 0,851 → 0,797 tanpa satu pun pengukuran berubah. Kerapatan kini hanya di `BaselineProfile.from_series`; tabel fitur tetap geser 30 dtk. Dikunci uji mutasi | selesai |
| T2b.4 | Anonimisasi: tidak ada nama/NRP/email yang dikirim ke LLM | selesai |

---

## Tahap 3a — Rekayasa Isi Knowledge Base

KB bukan bahan yang sudah jadi — ia **produk kerja TA ini**. Kualitas RAG dibatasi
kualitas KB, jadi ini dikerjakan sebelum `kb_index.py`.

**Status `kb_v2.0` (3 Agustus 2026):** knowledge base diterjemahkan ke Bahasa Inggris
(keputusan K15) agar retrieval satu bahasa. Isi, ID chunk, dan rujukannya tidak berubah
dari `kb_v1.1` — hanya bahasanya. Skor retrieval naik 0,03–0,08 di semua kueri uji.

**Status `kb_v1.1` (versi Indonesia, digantikan):** 23 chunk (naik dari 15), rerata 92 kata,
rentang 80–108 kata, simpangan baku 8 kata. Semua chunk punya ID unik. Versi lama
diarsipkan di `knowledge_base/versions/knowledge_base_HRV_v1.0.md`.

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
| T3b.4 | **Gold-standard mapping**: kondisi fitur → chunk yang *seharusnya* terambil (dasar Precision@k/Recall@k/MRR di T5.5). Dibuat manual oleh Salma, sebelum melihat hasil retrieval, supaya tidak bias. **Ditunda dengan sadar:** kerangkanya ada di `docs/gold_standard_retrieval.md` dengan 24 kondisi masih kosong, dan syarat "ditulis buta" sudah tidak terpenuhi karena hasil retrieval sudah terlihat. Konsekuensinya T5.5 dilaporkan sebagai pemeriksaan kualitatif, bukan Precision@k. Jendelanya terbuka lagi kalau KB diganti versi | blokir |

---

## Tahap 4 — `rag.py`

| ID | Tugas | Status |
|---|---|---|
| T4.1 | Fitur → deskripsi tekstual ("RMSSD 35% di bawah baseline, LF/HF meningkat") | selesai |
| T4.2 | Retrieval manual: cosine similarity, top-k | selesai |
| T4.3 | Susun prompt: instruksi + konteks KB + fitur + **modalitas** (Aturan Wajib #5) | selesai |
| T4.4 | Structured output JSON Gemini 2.5 Flash | selesai |
| T4.5 | Pagar anti-halusinasi: hanya jawab dari konteks, wajib menyatakan ketidakpastian | selesai |
| T4.6 | Aturan Wajib #1 ditegakkan **secara otomatis**, bukan cuma diinstruksikan: `rag/guards.py` memeriksa tiap angka di keluaran LLM harus dapat ditelusuri ke prompt, dan tiap ID rujukan harus benar-benar terambil. Hasil pada 3 segmen uji: nol angka karangan, nol rujukan palsu | selesai |

---

## Tahap 5 — `validate.py`

| ID | Tugas | Status |
|---|---|---|
| T5.1 | Metrik klasifikasi **per dataset & per modalitas** — jangan digabung | selesai |
| T5.2 | **WESAD holdout SELESAI** — 10 subjek tersegel, 561 segmen: accuracy **0,852**, macro-F1 **0,839**, kappa **0,678**. Selisih dengan dev hanya −0,012 macro-F1, menandakan overfitting minimal | selesai |
| T5.3 | Catatan independensi sampel: segmen overlap 30 dtk **tidak independen** | selesai |
| T5.4 | **Konsistensi antar-run** — sudah bisa dijalankan (`--consistency`). Uji awal S14: 3 run identik (level, keyakinan, rujukan) pada temperature 0,0. Masih perlu diperluas ke banyak segmen & temperature lain (U3.5) | jalan |
| T5.5 | **Kualitas retrieval**: Precision@k, Recall@k, MRR (butuh T3.4) | belum |
| T5.6 | **Faithfulness** — modul siap (`evaluation/rag_metrics.py`), memakai hasil pengaman per-assessment. Menunggu kuota API untuk dijalankan pada sampel memadai | jalan |
| T5.7 | **Kalibrasi skor keyakinan** vs kebenaran prediksi | selesai |

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
| U3.1 | **Pembanding aturan ambang** — SELESAI pada seluruh 293 segmen dev. Hasil: RMSSD saja macro-F1 0,742 / kappa 0,487; RMSSD atau HR macro-F1 **0,828** / kappa **0,656**; selalu-'low' kappa 0,000. Inilah bar yang harus dilampaui RAG | selesai |
| U3.1b | **Ablasi HR-saja SELESAI (25 Agt 2026) — hasil POSITIF, dan mengejutkan.** Pertanyaannya: berapa harga kehilangan RMSSD pada armband PPG (Coospo HW9)? Jawabannya: tidak ada — membuang RMSSD justru MENAIKKAN hasil. Aturan skor produksi pada 10 subjek tersegel: RMSSD+HR macro-F1 0,839 / kappa 0,678 → HR-saja **0,871 / 0,742**. Per subjek: menolong 5, netral 5, merugikan 0; selisih berpasangan +0,031, selang 95% [+0,008, +0,056] — tidak menyentuh nol. Pembanding ambang sederhana searah: HR-saja 0,899 [0,787–0,982]. Sebabnya sudah tercatat sebagai L9: RMSSD bergerak TERBALIK pada sebagian subjek (bicara mengubah napas), sedangkan HR naik pada semuanya — fitur yang menunjuk arah salah menambah derau, bukan bukti. Batasan: ini simulasi armband (rekaman ECG dengan RMSSD disembunyikan), bukan HW9 sungguhan; dan kuadran ketahanan tetap butuh RMSSD, jadi T1 tetap tanpa ketahanan. `rule_hr_only` di `evaluation/rule_baseline.py` (bug definisi ganda ditemukan & diperbaiki di sini) | selesai |
| U3.2 | **Ablasi: LLM tanpa KB** (fitur langsung ke Gemini, tanpa retrieval). Selisihnya = kontribusi nyata knowledge base. **DIJALANKAN PERTAMA KALI 2 Sep** — 21 dari 40 segmen sampel selesai sebelum kuota harian habis (cache melanjutkan otomatis di run berikutnya). Hasil sementara yang sudah bisa dikutip hati-hati: macro-F1 **0,438** [0,250–0,533] vs 0,672 dengan RAG pada data dev; **9/21 segmen abstain** (cakupan 57,1%) — tanpa konteks, model lebih sering menolak menjawab; kalibrasi keyakinan rusak (bin 0,7–0,9 hanya 25% benar); guard tetap bersih (nol sitasi karangan — memang tidak ada yang bisa dikutip). Sisa 19 segmen: jalankan ulang `--ablation none` saat kuota pulih | jalan (21/40) |
| U3.3 | **Ablasi: chunk acak** menggantikan chunk relevan. Kalau hasilnya tidak turun, berarti retrieval tidak berperan dan sistem hanya mengandalkan pengetahuan bawaan LLM. **Kodenya SUDAH ADA** — `RetrievalMode.RANDOM`, undian ber-seed per segmen lewat blake2b (bukan `hash()` yang bergaram per proses), melaporkan kemiripan sejati dari yang terundi, dan mengabaikan ambang. Yang belum: **menjalankannya**, di dua sumbu — klasifikasi *dan* grounding (kalau diberi chunk acak, apakah model tetap pede mengutipnya?). **Dicoba 2 Sep: 0/40 — kuota harian sudah habis dimakan run U3.2**; jalankan ulang `--ablation random` besok, cache melanjutkan sendiri | jalan (0/40) |
| U3.4 | **Sapuan nilai k** (k=1,3,5,7) — berapa chunk yang optimal | belum |
| U3.5 | **Sapuan temperature** — kaitkan dengan konsistensi antar-run (T5.4) | belum |
| U3.6 | Ablasi: prompt tanpa info modalitas — apakah skor keyakinan benar-benar berubah? Menguji Aturan Wajib #5 | belum |

### Protokol Pengujian (wajib ditetapkan **sebelum** menjalankan evaluasi akhir)

| ID | Tugas | Status |
|---|---|---|
| U4.1 | **Pisah subjek pengembangan vs pengujian** — disetujui. Dev: S2, S6, S10, S14, S17 (dipilih menyebar). Uji: 10 sisanya, disegel. Sudah masuk `SplitConfig` | selesai |
| U4.2 | Segel prompt & KB (beri versi, bekukan) sebelum menyentuh subjek uji | belum |
| U4.3 | Tetapkan jumlah run untuk konsistensi (3 atau 5) dan cara melaporkan variasinya | belum |
| U4.4 | Catat versi model Gemini di tiap keluaran — model bisa diperbarui pihak Google dan hasil ikut berubah. Terpasang di `rag/pipeline.py`: tiap keluaran membawa `kb_version`, `prompt_version`, `model`, `temperature`, ID chunk terambil beserta skornya | selesai |
| U4.5 | Simpan seluruh keluaran mentah LLM, bukan hanya labelnya — supaya faithfulness (T5.6) bisa diaudit ulang. `outputs/assessment_cache.jsonl` menyimpan objek `response` utuh (level, keyakinan, penalaran, rujukan) berikut kunci provenance-nya | selesai |

---

## Tahap 6 — `preprocess_ppg.py` (WESAD wrist BVP)

| ID | Tugas | Status |
|---|---|---|
| T6.1 | Bandpass **0,5–8 Hz**, deteksi puncak sistolik → deret IBI | selesai |
| T6.2 | Buang artefak gerakan pakai `wrist['ACC']` | selesai |
| T6.3 | Pakai ulang `features.py` apa adanya, `modalitas="PPG"` | selesai |
| T6.4 | **Perbandingan berpasangan** — DIJALANKAN ULANG 6 Agt 2026 setelah bug penjodohan ditemukan (lihat catatan di bawah). 90 segmen 5 subjek. meanHR ICC **+0,986**; RMSSD ICC **+0,109** (bias +95 ms); reaktivitas RMSSD **+0,620** berkat normalisasi baseline | selesai |

---

**Catatan penting soal angka T6.4 yang lama.** Versi sebelumnya (91 segmen, meanHR
ICC +0,936, RMSSD ICC +0,103, reaktivitas +0,513) **tidak sah** dan tidak boleh
dikutip. `run_ppg.py` menjodohkan ECG dan PPG lewat kolom `segment`, yang saat itu
berisi peringkat segmen yang lolos gerbang mutu, bukan nomor jendela. PPG membuang
jauh lebih banyak segmen daripada ECG, sehingga kedua kolom menghitung hal berbeda:
dari 91 pasangan hanya **2** yang benar-benar sewaktu, selisih mediannya **210
detik**, dan **74** pasangan jendelanya tidak bertumpang tindih sama sekali.
Penjodohan kini memakai `start_sec`, dan `Segment.index` sudah diperbaiki menjadi
nomor jendela sungguhan. Arah kesimpulan tidak berubah — justru menguat.

**Temuan baru yang muncul setelah perbaikan:** PPG menghasilkan **nol segmen layak
selama fase TSST pada 4 dari 5 subjek dev** (hanya S14 menyisakan 9). Outlier PPG
saat TSST 16–37%, jauh di atas gerbang 10%. Jadi perbandingan berpasangan praktis
bersandar pada fase istirahat (81 dari 90 pasangan). Ini memperkuat L11 dan wajib
masuk pertimbangan T8.4: kalau PPG runtuh justru saat orang tertekan, UBFC-Phys
yang PPG-saja tidak bisa diandalkan untuk kondisi tertekan.

---

## Tahap 7 — SWELL-KW *(setelah Tahap 1–6 tuntas, sesuai K8)*

| ID | Tugas | Status |
|---|---|---|
| T7.0 | **Dataset didapat 6 Agt 2026** lewat `kagglehub` (`qiriro/swell-heart-rate-variability-hrv`, 233 MB). Bukan SWELL asli Radboud | selesai |
| T7.1 | ~~Loader ECG ~2048 Hz~~ — **tidak mungkin**: paket Kaggle tidak memuat ECG mentah. Lihat catatan di bawah | tulis-ulang |
| T7.2 | Pemetaan tiga tingkat: neutral→rendah, time pressure→sedang, interruption→tinggi. Ada di `evaluation/labels.py` | selesai |
| T7.3 | **Macro-F1 tiga kelas SELESAI — dan hasilnya NEGATIF.** 14 subjek, 1.019 menit: accuracy **0,177**, macro-F1 **0,175**, kappa **−0,207**. Di bawah tebakan acak | selesai |
| T7.4 | Uji kecukupan KB pada tekanan kognitif — **tertunda**: percuma menguji KB sebelum labelnya sendiri terbukti sejalan dengan fisiologi (lihat T7.5) | blokir |
| T7.5 | **Sebab kegagalan teridentifikasi: kondisi SWELL terancu urutan.** `no_stress` SELALU blok pertama (menit ~10–15) sementara `time_pressure` dan `interruption` diselang-seling belakangan (rata-rata menit ~118). Gradien fisiologisnya justru terbalik dari gradien label: median ΔRMSSD `no_stress` **−20,9%**, `time_pressure` −3,5%, `interruption` **−2,5%**. RMSSD naik seiring waktu pada 5 dari 6 subjek (r sampai +0,64) — habituasi. Diuji juga dengan baseline lokal (blok istirahat tepat sebelum tiap kondisi): kappa membaik −0,207 → −0,094, **tetap di bawah nol**. Jadi bukan soal pilihan baseline | selesai |

---

**Apa yang sebenarnya ada di paket Kaggle.** Tiga lapis, dan hanya satu yang bisa
dipakai — alasan lengkapnya di docstring `datasets/swell.py`:

| Lapis | Isi | Putusan |
|---|---|---|
| `final/*.csv` | 36 fitur, jendela 5 menit | **Ditolak** — tidak ada kolom subjek, hanya `datasetId` konstan. Tanpa identitas subjek, baseline per orang mustahil (Aturan Wajib #2) |
| `raw/rri/p*.txt` | deret RR per subjek | **Ditolak** — kolom waktunya melangkah persis 0,25 dtk, jadi ini tachogram yang sudah diinterpolasi ke 4 Hz, bukan deret denyut. Nol pasangan berurutan berselisih >20% (deret denyut asli ~1,5%). RMSSD dan pNN50 didefinisikan antar-DENYUT, jadi menghitungnya dari kurva interpolasi menghasilkan angka yang tampak wajar tapi bermakna lain. Sumbu waktunya juga tidak cocok dengan label (RR 150 menit vs label 179 menit) |
| `raw/labels/*.xlsx` | HR + RMSSD **per menit**, per subjek, dengan kondisi | **Dipakai.** Jendela 1 menit setara segmen 60 dtk; ada blok istirahat eksplisit untuk baseline; aturan skor hanya butuh RMSSD + HR dan keduanya ada |

**Batasan yang wajib ditulis di laporan:** fitur SWELL dihitung oleh penulis
dataset, bukan oleh kode ini. Aturan Wajib #1 tetap aman (LLM tidak menghitung
apa pun), tapi reproduksibilitasnya berbeda dari WESAD yang seluruh angkanya
lahir dari `features/`. Angka SWELL dan WESAD **dilaporkan berdampingan, tidak
pernah digabung**. Selain itu hanya RMSSD dan HR yang tersedia — tanpa LF/HF,
pNN50, SDNN — sehingga kueri retrieval dibangun dari 2 dari 5 fitur biasanya.

**Catatan positif yang jarang didapat:** menit-menit SWELL tidak tumpang tindih,
jadi barisnya benar-benar independen. Keterbatasan L2 **tidak berlaku** untuk
dataset ini, dan `evaluate_classification` sudah tidak lagi menempelkan peringatan
overlap pada laporan SWELL.

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
| T9.1 | **Backend FastAPI SELESAI** — `backend/hrv_api/`. Dua endpoint sesuai kontrak `types/api.ts`: `/api/v1/analyze/timeline` (V1, per jendela) dan `/api/v1/analyze/session` (V2/V3, per pertanyaan). Otentikasi lewat `X-API-Key`; **tanpa kunci terkonfigurasi layanan menolak semua**, bukan mengizinkan semua. CORS dari daftar origin, bukan `*`, karena endpoint ini membelanjakan kuota Gemini sungguhan. Angka teknis **ditahan secara bawaan** dan hanya keluar bila `include_technical` diminta eksplisit — aturan "pengguna tidak melihat RMSSD" tidak bisa dipaksakan dari API, jadi yang aman dibuat jadi bawaan. 22 tes | selesai |
| T9.1b | **Degradasi anggun terverifikasi.** Label berasal dari aturan skor yang luring dan deterministik, jadi kuota habis / model tak terjangkau / guard menangkap angka karangan **hanya menghilangkan prosa**, bukan angkanya. `meta.trustworthy` menandai narasi yang tidak boleh ditampilkan apa adanya. Sesuai permintaan PRD KARIRLINK bahwa modul ini gagal secara lunak | selesai |
| T2c.8 | **Uji narasi ujung-ke-ujung dengan API — SELESAI 7 Agt 2026.** Dijalankan lewat backend pada rekaman 7 menit: 4 jendela baseline, RMSSD 34,4 ms, label `low`, narasi Bahasa Indonesia keluar utuh, `trustworthy: true` (nol angka karangan, nol sitasi palsu). Satu panggilan per sesi sesuai arsitektur gabungan | selesai |
| T9.2 | Dashboard Chart.js: timeline tekanan per pertanyaan. `frontend/src/components/StressTimeline.tsx` (chart.js 4 + react-chartjs-2), diplot dari **label** hasil aturan skor dan bukan dari persen perubahan, sehingga garis dan badge tidak pernah bisa berselisih. Ditemani `RecoveryBars`, `QuestionResultCard`, dan `ResponseRadar` | selesai |
| T9.3 | Terapkan K4 — layar hanya menampilkan bahasa awam. Ditegakkan di `SessionResult.tsx` (tanpa RMSSD, tanpa persen terhadap baseline, tanpa skor, tanpa nama fitur) dan diperkuat pengaman `find_k4_violations` + `tests/test_k4_guard.py`. **Catatan:** penegakannya masih di sisi klien; A6 di `docs/ARSITEKTUR_KARIRLINK_HRV.md` memindahkannya ke bentuk respons API supaya tetap berlaku waktu tim web menulis ulang frontend | selesai |
| T9.4 | Bahasa perilaku, bukan label sifat ("butuh 90 detik kembali tenang", bukan "regulasi emosi rendah"). Diterapkan di `lib/sessionInsights.ts` dan `lib/format.ts`; tiap angka adalah bagian dari sesi orang itu sendiri, tanpa norma populasi. **Belum tuntas:** badge Rendah/Sedang/Tinggi masih berupa label tekanan, dan sumbu grafik masih berbahasa Inggris — lihat A12 dan daftar layar hasil di `docs/PETA_PEKERJAAN.md` | selesai |

---

## Tahap 11 — Akuisisi & Perangkat *(dimulai 7 Agt 2026)*

Seluruh domain ini tidak pernah masuk BACKLOG karena baru muncul setelah keputusan
memakai sensor sungguhan. Rinciannya — riset perangkat, protokol, kriteria terkunci,
dan keterbatasan L13–L22 — ada di **`docs/AKUISISI_HRV_WEB_BLUETOOTH.md`**. Di sini
hanya statusnya, supaya BACKLOG tidak lagi diam soal satu bagian utuh pekerjaan.

| ID | Tugas | Status |
|---|---|---|
| H1 | Riset tujuh perangkat + tabel perbandingan; proposal pengajuan dana; **Coospo HW9 dibeli** | selesai |
| H2 | Halaman uji sensor & halaman protokol tiga blok, beserta modul logika bersama dan tesnya | selesai |
| H3 | **Gerbang perangkat (G1) — LULUS.** Field RR ada; sumber RR terbukti asli, bukan `60000/bpm`; outlier 4,5% istirahat / 4,3% tertekan, setara mutu ECG dada di WESAD | selesai |
| H4 | **Sifat instrumen HW9 terukur** — deteksi denyut tepat 128 Hz, kisi RR 7,8125 ms, harga kuantisasi terhitung 0,16 ms pada RMSSD istirahat (§3.3) | selesai |
| H5 | **Enam cacat perkakas ditemukan lewat uji ini dan diperbaiki** — detektor RR sintetis salah kaidah, dua sumber pembulatan yang merusak presisi, label fase `'pra'` dipakai untuk pra *dan* pasca, cakupan waktu tak pernah dilaporkan, kartu Field RR memantulkan paket terakhir. **Nol cacat ada di perangkatnya** | selesai |
| H6 | **Gerbang protokol (G2) — BELUM LULUS.** Stresor tidak menggigit (HR hanya +1,5%), dan baseline melayang sepanjang blok istirahat | jalan |
| H7 | **Putuskan aturan baseline (L22).** Terukur: gerbang kestabilan justru **lebih buruk** daripada durasi tetap — melayang pelan tampak stabil di jendela pendek, dan semua varian yang diuji menyala di 120 dtk lalu mengunci nilai 28,5% terlalu rendah. Arah yang disarankan: blok 6–7 menit, baseline diambil dari 2–3 jendela **terakhir** saja, kestabilan dipakai sebagai penolakan bukan pemicu berhenti. **Harus diputuskan sebelum menyentuh subjek** | belum |
| H8 | Uji rumus H7 pada 15 subjek WESAD (`analyse_baseline_duration.py`) sebelum dikunci — termasuk memeriksa apakah kriteria yang sudah ada di skrip itu jatuh ke perangkap 120 detik yang sama | belum |
| H9 | Ulangi protokol tiga blok: pemasangan **lengan atas** (§6.2), stresor lebih menuntut, baseline hasil H7 | belum |
| H10 | Pilot 1–2 subjek, dianalisis sampai tuntas dari sensor hingga layar, sebelum pengumpulan penuh | belum |
| H11 | Chest strap H808S sebagai slot pembanding B — uji satu perangkat dapat **membantah**, tidak dapat **memastikan** | belum |
| H12 | Aktifkan billing Gemini (HW-Q1) | belum |
| H13 | Ambil teks lengkap versi IJSPP Protzen dkk. (HW-Q4) | belum |

---

## Tahap 10 — Dokumentasi & Reproduksibilitas

Dikerjakan **berjalan bersama** tiap tahap, bukan ditumpuk di akhir. Alasan
keputusan paling mudah ditulis saat keputusannya baru diambil.

### Dokumentasi teknis

| ID | Tugas | Status |
|---|---|---|
| D1.1 | `README.md`: cara pasang, cara menjalankan, urutan skrip | belum |
| D1.2 | Docstring + komentar Bahasa Indonesia di bagian penting (aturan CLAUDE.md) | jalan |
| D1.3 | **Buat `pipeline_RAG_HRV.png`** — `RAG_HRV_Design.md:15` merujuknya tapi berkasnya tidak ada; rujukan rusak | belum |
| D1.4 | Diagram alir pra-pemrosesan per modalitas (ECG vs PPG) untuk bab metodologi | belum |
| D1.5 | Catatan tiap parameter numerik + alasannya, terpusat di `config.py` | belum |
| D1.6 | Kamus data: arti tiap kolom di CSV keluaran | belum |

### Dokumentasi RAG (khas pendekatan ini)

| ID | Tugas | Status |
|---|---|---|
| D2.1 | **Berkas prompt berversi** (`prompts/HRV_stress_interpretation.md`, `v2.md`) — di RAG, prompt itu bagian dari sistem, setara arsitektur model di DL. Wajib bisa dilacak | selesai |
| D2.2 | Catatan perubahan prompt: apa yang diubah, kenapa, dampaknya ke metrik | belum |
| D2.3 | Catatan perubahan KB: chunk apa ditambah/diubah, dampaknya | belum |
| D2.4 | Dokumentasikan gold-standard mapping (T3b.4) beserta alasan tiap pemetaan | belum |
| D2.5 | **Log eksperimen**: tiap run mencatat versi KB, versi prompt, versi model, k, temperature, timestamp | belum |

### Dokumentasi TA

| ID | Tugas | Status |
|---|---|---|
| D3.1 | Petakan tiap tahap backlog ke bab laporan. Pengelompokan per domain di `docs/PETA_PEKERJAAN.md` bisa dipakai sebagai kerangka awal | belum |
| D3.5 | **`docs/development_journey.md`** — kronologi, alasan keputusan, 10 temuan empiris terukur, status validasi. Sumber utama saat menyusun laporan | selesai |
| D3.2 | Tulis bab keterbatasan dari daftar L di bawah (L1–L11 di sini) **dan** L13–L22 di `docs/AKUISISI_HRV_WEB_BLUETOOTH.md` §7 | belum |
| D3.3 | Siapkan jawaban untuk pertanyaan sidang yang bisa diduga (lihat kolom alasan di tiap keputusan K1–K9) | belum |
| D3.4 | Catat alasan perubahan metode dari 4 arsitektur DL → RAG | belum |

---

## Keterbatasan untuk Ditulis di Laporan

Bukan bug — ini yang harus jujur disebut dan hampir pasti ditanya penguji.

> Seri ini **berlanjut di `docs/AKUISISI_HRV_WEB_BLUETOOTH.md` §7 sebagai L13–L22**,
> yang memuat keterbatasan sisi akuisisi: firmware tertutup, ketiadaan Web Bluetooth di
> iOS, RR sintetis, kuantisasi 7,8125 ms, lubang rekaman yang tak terlihat gerbang
> outlier, dan baseline yang melayang. Waktu menulis bab keterbatasan (D3.2), ambil dari
> **kedua** daftar.

| ID | Keterbatasan |
|---|---|
| L1 | Baseline pra-wawancara bukan baseline netral sejati — kecemasan antisipatif membuat reaktivitas terukur **lebih kecil** dari sebenarnya. Mitigasi: buang fase adaptasi awal, pisahkan fase pengarahan |
| L2 | Segmen overlap 30 dtk **tidak independen** — memengaruhi tafsir F1 dan uji signifikansi |
| L3 | LF tidak stabil pada segmen 60 dtk. Bukti empiris di S2: satu segmen **baseline** menunjukkan LF/HF +288% padahal kondisi istirahat |
| L4 | Beban kognitif dan tekanan sosial punya tanda HRV **identik**; pemisahannya berbasis konteks pertanyaan, bukan fisiologi |
| L5 | LLM stokastik — perlu pelaporan konsistensi antar-run (T5.4) |
| L6 | Tidak ada satu macro-F1 tunggal untuk seluruh sistem; metrik selalu per dataset & per modalitas |
| L7 | **Meski tidak ada model dilatih, menyetel prompt dan KB sambil melihat hasil tetap bentuk *fitting*.** Karena itu perlu subjek uji yang disegel (U4.1). Ini kritik paling tajam yang bisa dilontarkan ke pendekatan "tanpa pelatihan" — lebih baik diakui dan ditangani duluan daripada dibantah |
| L11 | **PPG WESAD (Empatica E4, 64 Hz) tidak layak untuk RMSSD.** ICC hanya **+0,109** dengan bias +95 ms, dan tidak tertolong oleh pelonggaran ambang (diuji 20–50%) maupun upsampling (64→256 Hz). Yang dapat dipercaya hanya detak jantung (ICC **+0,986**). Lebih tajam lagi: PPG **tidak menghasilkan satu pun segmen layak selama TSST** pada 4 dari 5 subjek dev, jadi kesimpulan ini bahkan belum teruji pada kondisi tertekan. Konsekuensi: UBFC-Phys yang hanya PPG perlu bersandar pada detak jantung (angka diperbarui 6 Agt 2026 setelah bug penjodohan diperbaiki) |
| L9 | **Dua dari lima subjek pengembangan berpola terbalik**: S6 dan S10 menunjukkan RMSSD/HF/pNN50 NAIK saat TSST, padahal detak jantungnya ikut naik. Dugaan penyebab: (a) TSST menuntut subjek BERBICARA, dan napas dalam saat bicara menaikkan daya pita HF secara artifisial — pita HF memang digerakkan pernapasan; (b) baseline S10 tampak bukan istirahat sejati (RMSSD 14,4 ms, HR 99 bpm saat "diam", IQR relatif 52%). Konsekuensi: RMSSD saja tidak cukup, dan detak jantung — yang naik pada **kelima** subjek (+5,1% s.d. +74%) — adalah penanda paling konsisten |
| L10 | Persentase perubahan **tidak simetris**: penurunan mentok −100%, kenaikan tak terbatas (teramati +442%). Seluruh peringkasan reaktivitas WAJIB memakai median; memakai rata-rata sempat membalik kesimpulan pNN50 dari −61,2% jadi +61,8% |
| L12 | **Kondisi SWELL-KW terancu urutan, sehingga labelnya tidak membentuk gradien fisiologis.** `no_stress` selalu blok pertama; `time_pressure` dan `interruption` menyusul jauh belakangan. Reaksi HRV terkuat justru muncul di kondisi yang dilabeli paling ringan, dan RMSSD naik seiring waktu (habituasi). Konsekuensi: aturan skor yang terkalibrasi di WESAD memberi kappa **−0,207** di SWELL, dan baseline lokal hanya menaikkannya ke −0,094. Ini keterbatasan **dataset**, bukan kegagalan metode — penulis SWELL asli pun menyimpulkan HRV bukan prediktor baik untuk stresor perkantoran. Akibat lanjutan: **ambang sedang/tinggi tetap tidak terkalibrasi** (T2c.10 masih terbuka), dan klaim tiga tingkat harus dinyatakan berdasar literatur, bukan terukur |
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
| T4.7 | **Chunk pedoman penilaian tidak selalu terambil.** Pada segmen kalibrasi S2, `KB-INTERP-01` (yang mendefinisikan kriteria rendah/sedang/tinggi) TIDAK terambil, sehingga LLM menilai "uncertain" padahal itu segmen istirahat. Usul: sematkan `KB-INTERP-01` sebagai chunk tetap di tiap prompt, terpisah dari k hasil pencarian | belum |
| T4.8 | **Keyakinan belum terkalibrasi**: S14 mendapat confidence 1,0 tiga kali berturut-turut tanpa menyebut satu pun keterbatasan. Keyakinan sempurna hampir tidak pernah wajar. Perlu ditangani di prompt v2 dan diukur di T5.7 | belum |
| T5.8 | **Kuota tier gratis 20 panggilan/hari** membatasi evaluasi. Mitigasi cache lintas-hari sudah dibangun (`evaluation/cache.py`). Perlu keputusan: aktifkan billing, atau kecilkan cakupan evaluasi | belum |
| T8.4 | **Antisipasi risiko UBFC-Phys**: dataset PPG-saja. Bila keterbatasan L11 berlaku juga di sana, uji arah perubahan harus memakai detak jantung, bukan RMSSD. Putuskan sebelum Tahap 8 dimulai |
| Q10 | Pemulihan & ketahanan tidak bisa diuji dengan WESAD (tidak ada fase jeda). Pilihan: (a) uji dengan data sintetis di U1 saja, (b) pakai WESAD label 4 (meditation) sebagai fase jeda — tapi urutan protokolnya berbeda antar subjek sehingga maknanya tidak setara. Rekomendasi: (a) |
| Q9 | **Terjawab: semua ablasi U3.1–U3.6 masuk laporan** |
