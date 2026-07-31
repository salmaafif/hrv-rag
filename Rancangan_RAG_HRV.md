# Rancangan Pipeline RAG untuk Interpretasi HRV

**Penilaian Tingkat Tekanan dari HRV Tanpa Melatih Model (Magang)**
Salma Afifa Azis — Modul KARIRLINK

---

## 1. Ringkasan
Sistem menilai tingkat tekanan pengguna dari fitur HRV **tanpa melatih model machine learning**. Sebagai gantinya, fitur HRV dikirim ke sebuah **LLM (Gemini)** yang ditambah pengetahuan domain melalui pendekatan **Retrieval-Augmented Generation (RAG)**. LLM menginterpretasi fitur berdasarkan pengetahuan yang diambil dari basis pengetahuan HRV, lalu menghasilkan penilaian dan umpan balik yang terstruktur dan berujukan.

---

## 2. Arsitektur / Alur

![Pipeline RAG untuk interpretasi HRV](Gambar_pipeline_RAG_HRV.png)

*Gambar 1. Pipeline RAG untuk interpretasi HRV*

**Alur:** Device (HR monitor/smartwatch) → pra-pemrosesan & ekstraksi fitur HRV → fitur (JSON) menjadi dasar retrieval → pengetahuan relevan diambil dari knowledge base → fitur + pengetahuan disusun jadi prompt → LLM Gemini menghasilkan penilaian terstruktur → ditampilkan di dashboard.

---

## 3. Komponen

### 3.1 Pra-pemrosesan & Ekstraksi Fitur HRV (tetap diperlukan)
Sama seperti pipeline HRV pada umumnya: quality check → filter → deteksi puncak R → deret RR → koreksi ektopik → segmentasi 60 detik. Dari tiap segmen dihitung fitur HRV domain waktu (RMSSD, SDNN, pNN50, meanRR), domain frekuensi (LF, HF, LF/HF), serta reaktivitas (perubahan terhadap baseline) dan pemulihan. Keluarannya berupa objek JSON fitur per segmen.

### 3.2 Knowledge Base HRV
Kumpulan dokumen rujukan yang dipotong menjadi bagian kecil (chunk), di-embed, dan disimpan pada vector store. Isinya antara lain:
- Nilai normal dan rentang HRV saat istirahat vs kondisi tertekan (RMSSD, SDNN, LF/HF).
- Hubungan HRV dengan stres/kecemasan (dominasi simpatis menurunkan HRV dan menaikkan LF/HF).
- Konsep reaktivitas dan pemulihan sebagai indikator pengelolaan tekanan.
- Faktor pengganggu HRV (usia, pernapasan, kafein, postur) sebagai kehati-hatian interpretasi.
- Pedoman interpretasi HRV ultra-short term. Sumber dapat diambil dari kajian pustaka proposal.

### 3.3 Retrieval
Fitur HRV pengguna diubah menjadi deskripsi singkat (mis. "RMSSD di bawah baseline, LF/HF meningkat"), lalu dipakai sebagai kueri *semantic search* untuk mengambil beberapa chunk pengetahuan paling relevan dari knowledge base.

### 3.4 LLM (Gemini) + Prompt
Prompt menggabungkan: (a) instruksi sistem, (b) pengetahuan terambil sebagai konteks, dan (c) fitur HRV pengguna. LLM diminta menilai **HANYA** berdasarkan konteks yang diberikan (mengurangi halusinasi) dan mengeluarkan JSON terstruktur.

### 3.5 Output Terstruktur
Keluaran JSON berisi tingkat tekanan, alasan, rekomendasi latihan, dan rujukan, yang kemudian ditampilkan pada dashboard.

---

## 4. Output Sistem & Metrik Penilaian
Keluaran sistem terdiri atas **dua lapis**: metrik objektif yang dihitung langsung dari sinyal oleh **kode** (deterministik), dan interpretasi serta umpan balik dari **LLM**. Pemisahan ini penting agar angka tidak dikarang LLM — **kode yang menghitung, LLM yang menafsirkan**.

| Metrik | Definisi | Sumber |
|---|---|---|
| Fitur HRV (RMSSD, SDNN, pNN50, LF, HF, LF/HF) | Ukuran variabilitas detak jantung per segmen, dari deret RR | Kode |
| Reaktivitas | Besar perubahan fitur HRV terhadap baseline (mis. RMSSD turun, LF/HF naik) | Kode |
| Pemulihan (recovery) | Seberapa cepat HRV kembali ke baseline setelah segmen menekan | Kode |
| Indeks ketahanan (resilience) | Skor gabungan: reaktivitas rendah + pemulihan cepat = ketahanan tinggi | Kode (formula) |
| Tingkat tekanan per segmen (rendah/sedang/tinggi) | Label respons tekanan tiap pertanyaan | LLM / aturan |
| Skor keyakinan | Tingkat keyakinan penilaian | LLM |
| Timeline tekanan | Urutan tingkat tekanan sepanjang sesi (kapan memuncak) | Kode/agregasi |
| Ringkasan sesi & rekomendasi latihan | Umpan balik naratif yang actionable & berujukan | LLM |

**Catatan istilah (tekanan vs kecemasan):** keluaran utama adalah **tingkat tekanan/respons stres** yang terukur secara fisiologis. Kecemasan merupakan konstruk psikologis; sistem **tidak mendiagnosis kecemasan klinis**, melainkan memberi *indikasi tekanan/stres* yang berkorelasi dengan kecemasan situasional. Sebaiknya dibingkai sebagai "indikasi tekanan", dan **divalidasi terhadap label dataset**.

---

## 5. Contoh Prompt & Keluaran

**Instruksi sistem:**
```
Anda menilai tingkat tekanan pengguna dari fitur HRV. Gunakan HANYA pengetahuan pada KONTEKS.
Jika tidak yakin, katakan tidak yakin. Keluarkan JSON sesuai skema.
```

**Masukan fitur HRV:**
```json
{ "segmen": 3, "RMSSD": 22, "SDNN": 31, "LF_HF": 3.1,
  "reaktivitas": "RMSSD turun 35% dari baseline",
  "pemulihan": "lambat kembali ke baseline" }
```

**Keluaran terstruktur:**
```json
{ "tingkat_tekanan": "tinggi", "skor_keyakinan": 0.8,
  "alasan": "RMSSD dan HF menurun serta LF/HF meningkat, menandakan dominasi simpatis (stres).",
  "rekomendasi": "Latih pertanyaan ini dengan teknik pernapasan sebelum menjawab.",
  "rujukan": ["Interpretasi RMSSD & LF/HF pada stres"] }
```

---

## 6. Validasi (penting untuk klaim)
Karena LLM tidak mengukur melainkan menafsirkan, hasilnya harus divalidasi. Caranya: jalankan pipeline pada dataset berlabel (**WESAD** baseline vs stress), bandingkan `tingkat_tekanan` keluaran LLM dengan label sebenarnya, lalu hitung tingkat kesesuaian (accuracy/macro-F1). Ini memberi bukti objektif atas kualitas interpretasi.

---

## 7. Tech Stack per Komponen

| Komponen | Teknologi |
|---|---|
| Pra-pemrosesan & fitur HRV | Python, NeuroKit2, NumPy/SciPy |
| Embedding | Gemini embeddings atau sentence-transformers |
| Vector store | Chroma atau FAISS (lokal) |
| Orkestrasi RAG | LlamaIndex atau LangChain |
| LLM | Google Gemini 2.5 Flash (structured output/JSON) |
| Backend | FastAPI |
| Dashboard | JavaScript, Chart.js |

---

## 8. Catatan & Risiko
- LLM menafsirkan angka yang diberikan, **bukan mengukur**; kualitas bergantung pada fitur yang benar, knowledge base tepercaya, dan prompt yang baik.
- Cegah halusinasi: batasi jawaban hanya pada konteks terambil, minta LLM menyatakan ketidakpastian.
- Pra-pemrosesan & ekstraksi fitur **TETAP wajib**; yang dihilangkan hanya pelatihan model.
- Pertimbangkan privasi data; bila diperlukan, gunakan LLM lokal (mis. Llama/Mistral via Ollama).
