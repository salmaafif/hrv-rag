# CLAUDE.md — Interpretasi Tingkat Tekanan dari HRV dengan RAG

## Konteks Proyek

Tugas Akhir Salma Afifa Azis (NRP 3123600017), Teknik Informatika PENS.
Modul untuk platform latihan wawancara kerja KARIRLINK.

Sistem menilai **tingkat tekanan** pengguna dari **HRV** saat simulasi wawancara
kerja, **tanpa melatih model machine learning**. Pendekatannya **RAG**: fitur HRV
dihitung deterministik oleh kode, lalu ditafsirkan oleh LLM (Gemini) yang
dibekali pengetahuan domain dari knowledge base.

Metode ini menggantikan rencana awal berupa perbandingan empat arsitektur deep
learning. Yang dihilangkan **hanya tahap pelatihan model** — pra-pemrosesan
sinyal dan ekstraksi fitur tetap wajib dan tidak berubah.

Dokumen pendukung: `Rancangan_RAG_HRV.md` (rancangan pipeline),
`kb/knowledge_base_HRV.md` (pengetahuan domain).

---

## Aturan Desain WAJIB

**1. Kode yang MENGHITUNG angka; LLM hanya MENAFSIRKAN.**
Ini aturan paling penting di proyek ini. Semua nilai numerik — fitur HRV,
reaktivitas, pemulihan, indeks ketahanan — dihitung deterministik oleh Python.
LLM tidak pernah diminta menghitung, memperkirakan, atau melengkapi angka.
LLM hanya menghasilkan: label tingkat tekanan, skor keyakinan, alasan,
rekomendasi, dan rujukan.

Kalau LLM boleh mengarang angka, seluruh klaim ilmiah TA ini runtuh karena
hasilnya tidak bisa diverifikasi.

**2. Gunakan perubahan relatif terhadap baseline pengguna, bukan ambang absolut.**
Nilai HRV sangat individual dan dipengaruhi usia, jenis kelamin, ritme
pernapasan, postur, serta kafein. Perbandingan antar individu tanpa kendali
memadai bisa menyesatkan. Yang dimodelkan adalah reaktivitas, bukan nilai mentah.

**3. Cegah halusinasi.**
LLM hanya boleh menjawab berdasarkan konteks yang diberikan. Bila konteks tidak
memadai, ia harus menyatakan ketidakpastian, bukan menebak.

**4. Output adalah indikasi tekanan, BUKAN diagnosis kecemasan klinis.**
Kecemasan adalah konstruk psikologis; yang sistem ukur adalah respons stres
fisiologis yang berkorelasi dengan kecemasan situasional. Framing ini harus
konsisten di kode, komentar, dan keluaran sistem.

**5. Modalitas sumber data harus ikut masuk ke prompt.**
ECG dan PPG tidak sama keandalannya. Informasi modalitas dipakai LLM untuk
menyesuaikan skor keyakinan.

---

## Cara Kerja yang Diharapkan

- Salma sedang belajar dan akan mempertahankan karya ini di sidang.
  **Jelaskan setiap kode dan alasan di balik keputusannya**, bukan hanya apa
  yang dilakukannya.
- Komentar kode **berbahasa Indonesia** pada bagian penting.
- Kerjakan **bertahap**. Jangan menulis banyak modul sekaligus. Sebelum
  perubahan besar, jelaskan rencananya dulu dan tunggu persetujuan.
- Setiap parameter numerik (panjang segmen, pita filter, ambang) harus punya
  alasan yang bisa dijelaskan saat sidang. Taruh di `config.py` dengan komentar.

---

## Dua Modalitas: ECG dan PPG

| | ECG | PPG |
|---|---|---|
| Sumber | Chest strap (Polar, Coospo) | Smartwatch, wristband |
| Yang direkam | Sinyal listrik jantung | Perubahan volume darah (optik) |
| Bentuk puncak | Puncak R, tajam | Puncak sistolik, landai |
| Deret turunan | RR-interval | IBI (inter-beat interval) |
| Nama variabilitas | HRV | PRV |
| Status | Acuan / gold standard | Divalidasi terhadap ECG |

Saat diam, PRV mendekati HRV. Saat bergerak atau tertekan, keduanya bisa
menyimpang karena PPG rentan artefak gerakan dan dipengaruhi *pulse transit
time*. Justru kondisi tertekan itulah yang diukur sistem ini, sehingga
perbedaan modalitas tidak boleh diabaikan.

**Implikasi teknis:** cabang pra-pemrosesan dipisah menjadi dua file
(`preprocess_ecg.py` dan `preprocess_ppg.py`), bukan satu file dengan
percabangan `if`. Alasannya: pita filter, algoritma deteksi puncak, dan
kebutuhan pembuangan artefak gerakan benar-benar berbeda.

Setelah pra-pemrosesan, keduanya sama-sama menjadi deret interval dalam
milidetik, sehingga tahap sesudahnya (fitur, RAG, validasi) dipakai ulang.
Perbedaannya dicatat di kolom `modalitas`.

---

## Tiga Dataset dengan Struktur Label Berbeda

| Dataset | Subjek | Modalitas | Kelas efektif | Peran |
|---|---|---|---|---|
| **WESAD** | 15 | ECG 700 Hz (RespiBAN) + BVP 64 Hz (Empatica E4) | **Biner**: baseline→rendah, TSST→tinggi | Jangkar utama. TSST paling mirip wawancara. Satu-satunya dengan ECG+PPG dari subjek sama |
| **SWELL-KW** | 25 | ECG ~2048 Hz | **Tiga tingkat**: neutral→rendah, time pressure→sedang, interruption→tinggi | Satu-satunya sumber gradien tiga tingkat penuh |
| **UBFC-Phys** | 56 | PPG/BVP | Tiga fase (istirahat/berbicara/aritmetika), **tidak** dipetakan ke tiga tingkat | Uji modalitas PPG lintas-perangkat |

**Catatan WESAD:** kondisi `amusement` (label 3) **dikecualikan**. Itu arousal
positif, bukan tekanan — mencampurnya akan mengotori skala.

**Konsekuensi penting:** tidak ada satu angka macro-F1 tunggal untuk seluruh
sistem. Metrik dilaporkan **per dataset** sesuai jumlah kelasnya, dan **per
modalitas**. Jangan pernah menggabungkan label dari dataset berbeda ke dalam
satu perhitungan metrik.

Cara membaca WESAD:
```python
with open(path, "rb") as f:
    data = pickle.load(f, encoding="latin1")
ecg = data["signal"]["chest"]["ECG"]   # 700 Hz
bvp = data["signal"]["wrist"]["BVP"]   # 64 Hz
label = data["label"]                   # 1=baseline, 2=stress(TSST), 3=amusement
```

---

## Pipeline

```
Sinyal jantung (ECG atau PPG)
    ↓  pra-pemrosesan per-modalitas
Deret RR/IBI bersih, tersegmentasi 60 detik
    ↓  ekstraksi fitur (deterministik, oleh kode)
Fitur HRV + reaktivitas terhadap baseline subjek
    ↓  fitur diubah jadi deskripsi tekstual
"RMSSD 35% di bawah baseline, LF/HF meningkat"
    ↓  semantic search ke knowledge base
Chunk pengetahuan paling relevan
    ↓  prompt = instruksi + konteks + fitur + modalitas
LLM Gemini
    ↓
JSON: tingkat_tekanan, skor_keyakinan, alasan, rekomendasi, rujukan
    ↓
Dashboard
```

### Pra-pemrosesan — cabang ECG
1. Quality check: deteksi clipping, flat-line, derau berlebih
2. Bandpass Butterworth orde 2, 0,5–40 Hz + notch 50 Hz (standar listrik Indonesia)
3. Deteksi puncak R (Pan-Tompkins++ atau NeuroKit2)
4. Deret RR + koreksi ektopik (interval di luar 0,3–2,0 detik atau berselisih
   >20% dari sebelumnya ditandai outlier; segmen dibuang bila outlier >10%)
5. Segmentasi 60 detik, overlap 30 detik

### Pra-pemrosesan — cabang PPG
Alurnya mirip, berbeda di tiga hal: pita filter 0,5–8 Hz (gelombang lebih
halus), deteksi puncak sistolik alih-alih puncak R, dan pembuangan artefak
gerakan memakai kanal akselerometer bila tersedia.

### Fitur
- Domain waktu: meanRR, SDNN, RMSSD, pNN50
- Domain frekuensi: LF (0,04–0,15 Hz), HF (0,15–0,4 Hz), LF/HF — dihitung
  **dua cara berdampingan** lalu dibandingkan (keputusan K2 di `BACKLOG.md`):
  (a) interpolasi deret RR ke 4 Hz lalu Welch, dan (b) Lomb-Scargle langsung
  pada deret tak seragam. Cara (a) paling lazim disitasi; cara (b) menghindari
  distorsi interpolasi. Selisih keduanya jadi bahan pembahasan sidang.
- Baseline per subjek, reaktivitas (% perubahan), pemulihan, indeks ketahanan

**Catatan segmen 60 detik:** fitur domain waktu (terutama RMSSD) relatif andal,
tapi LF kurang stabil karena butuh jendela lebih panjang. Prioritaskan RMSSD;
tafsirkan LF/HF lebih hati-hati.

---

## Validasi

Karena LLM menafsirkan dan bukan mengukur, hasilnya wajib divalidasi.

**Metrik klasifikasi** (per dataset, per modalitas): accuracy, macro-F1, F1 per
kelas, confusion matrix, Cohen's Kappa.
- WESAD → F1 biner
- SWELL-KW → macro-F1 tiga kelas
- UBFC-Phys → uji arah perubahan (apakah fase berbicara/aritmetika dinilai
  lebih tinggi daripada istirahat pada subjek yang sama), bukan klasifikasi

**Metrik khas RAG** (tidak ada di pendekatan DL, tapi wajib):
- **Konsistensi antar-run**: jalankan prompt sama 3–5 kali, ukur variasi output.
  LLM stokastik — penguji hampir pasti menanyakan ini.
- **Faithfulness**: apakah setiap klaim di `alasan` didukung chunk yang terambil,
  atau LLM mengarang.
- **Kualitas retrieval**: Precision@k, Recall@k, MRR terhadap gold-standard
  mapping kondisi fitur → chunk yang seharusnya terambil.
- **Kalibrasi skor keyakinan**: apakah keyakinan tinggi berkorelasi dengan
  prediksi benar.

**Perbandingan modalitas:**
- Berpasangan pada subjek sama (hanya WESAD): ICC, Bland-Altman, label
  agreement rate — bukti terkuat
- Antar-dataset dalam modalitas sama: apakah KB dan prompt yang sama tetap
  bekerja pada jenis stresor berbeda

**Catatan soal "lintas-dataset":** di pendekatan DL artinya latih di satu
dataset, uji di dataset lain. Di RAG tidak ada yang dilatih, jadi konsepnya
berubah menjadi: **apakah satu knowledge base dan satu prompt bisa melayani
ketiga dataset?** Kalau performa jatuh di SWELL padahal KB-nya sama, artinya KB
terlalu bias ke pola stres sosial-evaluatif dan kurang mencakup tekanan
kognitif. Framing-nya jadi "cakupan dan kecukupan knowledge base", bukan
"generalisasi model".

---

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Sinyal & fitur | Python, NeuroKit2, NumPy, SciPy, pandas |
| LLM | Google Gemini 2.5 Flash via `google-generativeai`, structured output JSON |
| Embedding | Gemini embeddings (`text-embedding-004`) |
| Vector store | Chroma (lokal) |
| Orkestrasi RAG | Manual — retrieval ditulis sendiri, tanpa LangChain/LlamaIndex |
| Evaluasi | scikit-learn |
| Visualisasi | matplotlib, seaborn |
| Backend | FastAPI |
| Dashboard | JavaScript, Chart.js |

**Kenapa retrieval manual, bukan framework?** Knowledge base-nya kecil (~15
chunk). Untuk skala itu, cosine similarity yang ditulis sendiri sudah cukup dan
jauh lebih transparan untuk dijelaskan baris per baris saat sidang. Framework
menambah lapisan abstraksi yang justru menyulitkan pertanggungjawaban.

**Rahasia:** `GEMINI_API_KEY` di `.env`. JANGAN pernah commit.

---

## Struktur Folder

```
hrv-rag/
├── data/
│   ├── raw/                  # wesad/, swell/, ubfc/ (tidak di-commit)
│   └── processed/            # deret RR & fitur hasil olahan
├── kb/knowledge_base_HRV.md
├── prompts/                  # prompt berversi (v1.md, v2.md, ...)
├── docs/gambar/              # diagram pipeline & alur
├── src/hrv_rag/              # paket Python (underscore agar bisa di-import)
│   ├── config/settings.py    # SEMUA parameter numerik + alasannya
│   ├── core/types.py         # objek domain: RRSeries, Modality, Phase
│   ├── datasets/             # base.py (ABC), wesad.py, swell.py, ubfc.py
│   ├── preprocessing/        # base.py (ABC), ecg.py, ppg.py
│   ├── features/             # fitur HRV, reaktivitas, pemulihan, ketahanan
│   ├── rag/                  # kb_index, retrieval, prompt, Gemini
│   └── evaluation/           # bandingkan hasil vs label
├── scripts/                  # skrip yang dijalankan manual
├── tests/                    # uji perangkat lunak (BACKLOG U1)
├── notebooks/                # eksplorasi & grafik
├── outputs/                  # hasil eksperimen (tidak di-commit)
├── .env                      # GEMINI_API_KEY (TIDAK di-commit)
├── requirements.txt
├── BACKLOG.md                # rencana kerja & keputusan terkunci
├── CLAUDE.md
└── Rancangan_RAG_HRV.md
```

**Catatan penamaan.** Berkas per-modalitas kini berada di
`preprocessing/ecg.py` dan `preprocessing/ppg.py`, bukan `preprocess_ecg.py`
di akar `src/`. Maksud aslinya tetap dijaga — **dua modalitas tetap di berkas
terpisah, bukan satu berkas dengan percabangan `if`** — hanya saja kontrak
bersamanya kini eksplisit di `preprocessing/base.py`.

**Prinsip OOP yang dipakai.** Kelas hanya dibuat di tempat yang benar-benar
punya ragam varian, yaitu dua sumbu: **modalitas** (`BasePreprocessor` →
`ECGPreprocessor`, `PPGPreprocessor`) dan **dataset** (`BaseDatasetLoader` →
`WESADLoader`, `SWELLLoader`, `UBFCLoader`). Selebihnya fungsi biasa.
Membungkus semua menjadi kelas hanya menambah lapisan yang menyulitkan
pertanggungjawaban saat sidang.

---

## Urutan Pengerjaan

Rincian tugas per tahap ada di `BACKLOG.md`. Tabel ini hanya ringkasannya.

| Tahap | Berkas | Status |
|---|---|---|
| 0 | fondasi repo, struktur folder, `config/settings.py` | selesai |
| 1 | `preprocessing/base.py` + `preprocessing/ecg.py` | selesai |
| 2 | `features/` — fitur, reaktivitas, pemulihan, ketahanan | jalan |
| 3a | isi knowledge base (tambal lubang cakupan) | belum |
| 3b | `rag/kb_index.py` | belum |
| 4 | `rag/` — retrieval + prompt + Gemini | belum |
| 5 | `evaluation/` — metrik vs label | belum |
| 6 | `preprocessing/ppg.py` (WESAD wrist BVP) | belum |
| 7 | SWELL-KW | blokir (dataset belum ada) |
| 8 | UBFC-Phys | blokir (dataset belum ada) |
| 9 | FastAPI + dashboard | belum |
| 10 | dokumentasi & reproduksibilitas | jalan |

Cabang PPG dikerjakan setelah cabang ECG jalan penuh: menambah PPG hanya soal
mengganti tahap filter dan deteksi puncak — tahap sesudahnya sudah bisa
dipakai ulang lewat kontrak di `preprocessing/base.py`.

Dataset ditambahkan bertahap (WESAD tuntas dulu, baru SWELL, baru UBFC).

Perbarui kolom status setiap satu tahap selesai.
