# Gold-Standard Retrieval Mapping (T3b.4)

Status: **KOSONG — menunggu diisi Salma.**
Dibuat 13 Agustus 2026, sebelum hasil evaluasi RAG dilihat.

---

## Kenapa berkas ini harus diisi SEKARANG

Precision@k, Recall@k, dan MRR (T5.5) mengukur satu hal: seberapa sering
retrieval mengambil chunk yang **seharusnya** diambil. "Seharusnya" itu harus
ditetapkan **sebelum** melihat apa yang benar-benar diambil sistem.

Kalau diisi setelahnya, yang terukur bukan mutu retrieval melainkan ingatanmu
tentang keluaran tadi — dan angkanya akan tinggi tanpa berarti apa-apa. Sekali
terkontaminasi tidak bisa dibersihkan; tidak ada cara memulihkannya selain
mengganti dataset atau mengganti KB.

**Aturan pengisian:** jangan buka `outputs/assessment_cache.jsonl`,
`outputs/llm_comparison/`, atau keluaran `run_evaluation.py` sebelum berkas ini
selesai dan di-commit. Commit-nya yang menjadi bukti urutan waktunya.

Yang menyusun ini harus **kamu**, bukan model bahasa dan bukan asisten. Ini
penilaian domain: chunk mana yang secara ilmiah relevan untuk kondisi tertentu.
Kalau dibuat oleh sistem yang sama yang sedang dinilai, ia tidak menguji apa pun.

---

## Chunk yang tersedia (kb_v2.0, 23 chunk)

| ID | Judul |
|---|---|
| KB-ANS-01 | HRV and the Autonomic Nervous System |
| KB-LEVEL-01 | Interpreting High vs Low HRV |
| KB-RMSSD-01 | RMSSD |
| KB-SDNN-01 | SDNN |
| KB-PNN50-01 | pNN50 and meanRR |
| KB-FREQ-01 | Frequency Domain: LF and HF |
| KB-LFHF-02 | Interpreting the LF/HF Ratio with Care |
| KB-NORM-01 | Population Reference Values |
| KB-STRESS-01 | HRV Patterns Under Social-Evaluative Stress |
| KB-REACT-01 | Reactivity |
| KB-RECOV-01 | Recovery |
| KB-RECOV-02 | Quantifying Recovery |
| KB-RESIL-01 | Resilience Index |
| KB-CONF-01 | HRV Confounding Factors |
| KB-CONF-02 | How Speaking Affects HRV |
| KB-COGN-01 | Cognitive Load and Mental Effort |
| KB-AROUS-01 | Arousal and Valence |
| KB-ULTRA-01 | Ultra-Short-Term HRV in 60-Second Segments |
| KB-MODAL-01 | Modality Differences: ECG and PPG |
| KB-MODAL-02 | When PRV Diverges from HRV |
| KB-INTERP-01 | Guidance for Rating Stress Level |
| KB-INTERP-02 | Handling Atypical Patterns |
| KB-ETHIC-01 | Limitations and Interpretation Ethics |

---

## Cara mengisi

Untuk tiap kondisi di bawah, tulis chunk yang **seharusnya** terambil, dibagi dua:

- **Wajib** — kalau chunk ini tidak terambil, jawaban sistem kehilangan dasar.
  Ini yang dipakai menghitung **Recall@k**.
- **Boleh** — relevan dan tidak salah bila terambil, tapi bukan keharusan.
  Dipakai supaya Precision@k tidak menghukum chunk yang sebenarnya masuk akal.

Sistem mengambil **k = 3**, jadi daftar "wajib" yang panjangnya lebih dari 3
membuat Recall@3 mustahil sempurna. Itu boleh saja — asal disengaja, dan
disebutkan di laporan sebagai batas atas yang diketahui.

Isi kolom **Alasan** dengan satu kalimat. Kolom itu yang akan kamu bacakan saat
penguji bertanya "kenapa chunk ini yang seharusnya?", dan menuliskannya sekarang
jauh lebih mudah daripada merekonstruksinya tiga bulan lagi.

---

## Kondisi yang dibentuk `query_builder.py`

Kueri disusun dari: besar & arah reaktivitas tiap fitur, modalitas, jenis
pertanyaan, pola atipikal, dan mutu sinyal. Kondisi di bawah mengikuti sumbu itu.

### A. Reaktivitas — besar dan arah

| # | Kondisi | Wajib | Boleh | Alasan |
|---|---|---|---|---|
| A1 | RMSSD turun sedang (−20% s.d. −30%) | | | |
| A2 | RMSSD turun besar (> −30%) | | | |
| A3 | RMSSD turun kecil (< −10%) — praktis tidak berubah | | | |
| A4 | RMSSD **naik** dari baseline | | | |
| A5 | HR naik sedang, RMSSD hampir tidak berubah | | | |
| A6 | HR naik besar (> +20%) | | | |
| A7 | SDNN turun tapi RMSSD stabil | | | |
| A8 | LF/HF naik tajam | | | |
| A9 | HF turun tajam | | | |
| A10 | pNN50 jatuh ke nol | | | |

### B. Pola yang saling bertentangan

| # | Kondisi | Wajib | Boleh | Alasan |
|---|---|---|---|---|
| B1 | Fitur vagal **naik** sementara HR juga naik (atipikal) | | | |
| B2 | RMSSD dan HR menunjuk arah berlawanan | | | |
| B3 | Domain waktu tenang, domain frekuensi tertekan | | | |

### C. Modalitas

| # | Kondisi | Wajib | Boleh | Alasan |
|---|---|---|---|---|
| C1 | Modalitas ECG, sinyal baik | | | |
| C2 | Modalitas PPG, sinyal baik | | | |
| C3 | Modalitas PPG, outlier tinggi (mutu diragukan) | | | |

### D. Konteks sesi

| # | Kondisi | Wajib | Boleh | Alasan |
|---|---|---|---|---|
| D1 | Fase istirahat / kalibrasi | | | |
| D2 | Pertanyaan jenis *behavioural* | | | |
| D3 | Pertanyaan jenis *numerical* (beban kognitif) | | | |
| D4 | Fase pemulihan setelah pertanyaan sulit | | | |
| D5 | Pemulihan tidak dapat dihitung (jeda terlalu pendek) | | | |

### E. Mutu dan keterbatasan

| # | Kondisi | Wajib | Boleh | Alasan |
|---|---|---|---|---|
| E1 | Outlier > 10%, segmen tetap dinilai | | | |
| E2 | Baseline tidak stabil (IQR relatif tinggi) | | | |
| E3 | Segmen 60 detik, fitur LF dipakai | | | |

---

## Dua hal yang perlu kamu putuskan sambil mengisi

**1. Apakah `KB-INTERP-01` wajib di SETIAP kondisi?** Chunk itu yang
mendefinisikan kriteria rendah/sedang/tinggi. T4.7 sudah mencatat ia kadang tidak
terambil, dan ketika itu terjadi model menilai tanpa memegang definisinya. Kalau
menurutmu ia wajib di mana-mana, tulis begitu — konsekuensinya Recall@3 akan
rendah secara sistematis, dan itu justru temuan yang layak dilaporkan, bukan
kegagalan yang perlu disembunyikan.

**2. Apakah `KB-ETHIC-01` masuk di kondisi apa pun?** Ia soal batas penafsiran,
bukan soal fitur. Kalau tidak pernah wajib, ia tidak akan pernah terhitung di
metrik mana pun — dan itu perlu disebut, supaya tidak terlihat seperti chunk yang
sistemnya gagal temukan.

---

## Setelah selesai

```bash
git add docs/gold_standard_retrieval.md
git commit -m "docs: gold-standard retrieval mapping T3b.4, ditulis sebelum hasil dilihat"
```

Commit itu yang membuktikan urutan waktunya. Baru setelah itu T5.5 boleh
dijalankan, dan hasil evaluasi RAG boleh dibaca.
