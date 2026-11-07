# Tanya-Jawab Persiapan Bimbingan

Disusun 29 Agustus 2026 dari kode & dokumen repo — bahasa sederhana untuk
menjelaskan ke dosen pembimbing. Angka-angka: `docs/demo-bimbingan.md`.

## 1. Dataset publik
Dirancang tiga, TERPAKAI SATU: **WESAD** — 15 subjek, protokol TSST
(paling mirip wawancara), ECG dada 700 Hz + PPG pergelangan 64 Hz dari
subjek yang sama. SWELL-KW dan UBFC-Phys tidak pernah tersedia (jujur).

## 2. Data turunan heart rate
**Interval RR**: jarak antar denyut dalam milidetik, deret angka
`[820, 810, ...]`. Fitur: meanRR/HR, **RMSSD** (utama), SDNN, pNN50, LF/HF.
Turunan relatif-pribadi: **reaktivitas** (% perubahan vs baseline sendiri),
**pemulihan**, **indeks ketahanan**.

## 3. Datasetnya diapain
Baca pickle → bersihkan → potong 60 dtk (overlap 30) → hitung fitur →
bandingkan vs baseline pribadi tiap subjek. Kondisi *amusement* DIBUANG
(gairah positif, bukan tekanan).

## 4. Label
Biner dari protokol WESAD: baseline → **rendah**, TSST → **tinggi**.

## 5. Langkah awal–akhir (singkat)
Sinyal → bersihkan → segmen 60 dtk → fitur HRV → reaktivitas vs baseline
pribadi → **aturan deterministik memberi label** → RAG+Gemini menulis
narasi Indonesia → guard anti-karangan → validasi vs label WESAD →
integrasi KARIRLINK. Prinsip #1: kode menghitung, LLM hanya menafsirkan.

## 6. Pembersihan
Bandpass Butterworth 0,5–40 Hz + notch 50 Hz → deteksi puncak R
(NeuroKit2) → koreksi ektopik (di luar 0,3–2,0 dtk atau lompat >20% =
outlier) → segmen dengan outlier >10% DIBUANG utuh → pemeriksa kelayakan
sinyal per rekaman.

## 7. Menghitung sampai hasil
Per pertanyaan: potongan saat menjawab → RMSSD & HR → banding baseline
pribadi → ambang aturan → label. Ambang dikalibrasi di 5 subjek
pengembangan, DIBEKUKAN, diuji di 10 subjek tersegel. Deterministik:
identik tiap dijalankan, luring, bisa diaudit.

## 8. Metode
(a) **Aturan skor deterministik** — dipakai produk; (b) **RAG + Gemini** —
narasi saja; (c) **1D-CNN** — pembanding; (d) **LLM-sebagai-pelabel** —
diukur, DITOLAK.

## 9. Langkah RAG + tujuannya
1. Fitur → kalimat (agar bisa dicari semantik).
2. Retrieval ke KB 23 chunk Inggris bersitasi (embedding
   gemini-embedding-001; cosine similarity manual, tanpa vector store —
   23×3072 float ≈ 280 KB) → membumikan LLM pada rujukan.
3. Prompt = instruksi + chunk + fitur + modalitas (ECG/PPG → keyakinan).
4. Gemini → JSON terstruktur (penjelasan/saran/rujukan — BUKAN label).
5. Guard: tiap angka tertelusur ke prompt, tiap sitasi benar terambil →
   bendera `trustworthy`; narasi karangan ditahan, label tetap sah.

## 10. Hasil deep learning
1D-CNN macro-F1 **0,878** — di atas aturan (0,839) tipis, tapi gagal total
di satu subjek (0,398 vs 0,920 milik aturan), butuh PyTorch, tak bisa
menjelaskan. Dilaporkan sebagai pembanding, tidak dipakai.

## 11. Metode akhir
**Aturan deterministik (label) + RAG-LLM (narasi).** HR-saja **0,871**
[0,808–0,925] untuk armband (HR tepercaya ICC 0,986; RMSSD tidak, 0,109);
RMSSD+HR 0,839; LLM-pelabel 0,672 → ditolak. RAG: faithfulness 95,2%,
konsisten di temperature 0, keyakinan terkalibrasi 0,47→0,88.

## 12. Metrik + acuan jurnal (ada di knowledge base)
- Reaktivitas & pemulihan: **Laborde, Mosley & Thayer (2017)**.
- Standar fitur HRV: **Task Force ESC/NASPE (1996)**, **Shaffer & Ginsberg
  (2017)**.
- HRV & stres: **Kirschbaum dkk. (1993)** (TSST), **Castaldo dkk. (2015)**,
  **Kim dkk. (2018)**.
- Kehati-hatian LF/HF: **Billman (2013)**; normatif: **Nunan dkk. (2010)**.
- **Bukan "anxiety"**: yang diukur respons stres fisiologis, bukan
  diagnosis kecemasan klinis. Sinyal tak boleh menilai kandidat — korelasi
  fisiologi ↔ penilaian pewawancara lemah (−0,07 s.d. −0,28; McCarthy &
  Goffin 2004).
- Jujur: 11 sitasi KB belum diverifikasi ulang ke teks penuh (daftar kerja).

## Posisi sekarang (29 Agt 2026)
Riset inti selesai & terkunci. Integrasi KARIRLINK: rantai penuh hidup dan
terbukti dengan satu sesi nyata tersimpan; layanan di-vendor ke monorepo
(`apps/hrv-service`). Sisa: keandalan aliran sensor HW9, rapat kontrak
Tegar, pilot bersih, staging; sisi TA: ablasi tanpa-KB + verifikasi sitasi.
