# Knowledge Base HRV — untuk RAG Interpretasi Tekanan

> Basis pengetahuan untuk sistem RAG. Setiap bagian (heading `##`) adalah satu *chunk* yang dapat
> di-embed dan diambil saat retrieval. Prinsip utama: **gunakan perubahan relatif terhadap baseline
> pengguna**, bukan ambang absolut, karena HRV sangat individual. Sistem memberi *indikasi tekanan*,
> **bukan diagnosis klinis**.

---

## HRV dan Sistem Saraf Otonom
Heart Rate Variability (HRV) adalah variasi interval waktu antar denyut jantung berurutan (RR-interval).
HRV mencerminkan kerja sistem saraf otonom, yaitu keseimbangan antara cabang simpatis (mempercepat
jantung saat menghadapi tekanan) dan parasimpatis/vagal (menenangkan jantung saat istirahat). Karena
nodus sinoatrial dipersarafi kedua cabang, perubahan keseimbangan ini tampak pada pola HRV.

## Makna HRV Tinggi vs Rendah
HRV yang lebih tinggi umumnya menandakan dominasi parasimpatis, kondisi rileks, dan kemampuan adaptasi
yang baik. HRV yang lebih rendah menandakan dominasi simpatis yang kerap muncul saat tubuh menghadapi
stres atau tekanan. Dalam konteks wawancara, penurunan HRV mengindikasikan meningkatnya tekanan.

## RMSSD
RMSSD (root mean square of successive differences) adalah fitur domain waktu yang mencerminkan
aktivitas parasimpatis (vagal) jangka pendek. RMSSD **menurun** saat stres/tekanan meningkat. RMSSD
termasuk fitur yang paling andal untuk rekaman singkat.

## SDNN
SDNN (standard deviation of NN intervals) mengukur variabilitas keseluruhan HRV pada suatu segmen.
SDNN dipengaruhi aktivitas simpatis maupun parasimpatis. SDNN cenderung **menurun** pada kondisi
tertekan.

## pNN50 dan meanRR
pNN50 adalah persentase pasangan RR berurutan yang berbeda lebih dari 50 ms; nilainya turun saat
tekanan meningkat dan berkaitan dengan aktivitas vagal. meanRR adalah rata-rata RR-interval; meanRR
yang mengecil berarti detak jantung meningkat (indikasi arousal/tekanan).

## Domain Frekuensi: LF, HF, LF/HF
HF (high frequency, 0,15–0,4 Hz) mencerminkan aktivitas parasimpatis (terkait pernapasan) dan
**menurun** saat stres. LF (low frequency, 0,04–0,15 Hz) dipengaruhi campuran simpatis, parasimpatis,
dan baroreflex. Rasio LF/HF sering ditafsirkan sebagai keseimbangan simpato-vagal: nilai **lebih tinggi**
dikaitkan dengan dominasi simpatis/tekanan, meskipun interpretasinya masih diperdebatkan.

## Nilai Rujukan (perkiraan — gunakan dengan hati-hati)
Untuk populasi sehat pada rekaman singkat (~5 menit), nilai rujukan perkiraan: SDNN sekitar 30–100 ms
(rerata ~50 ms) dan RMSSD sekitar 20–90 ms (rerata ~42 ms) (Shaffer & Ginsberg, 2017; Nunan dkk., 2010).
Nilai ini **sangat individual** dan dipengaruhi usia, jenis kelamin, ritme pernapasan, serta durasi
rekaman. Untuk sistem ini, **utamakan perbandingan terhadap baseline masing-masing pengguna**
(perubahan relatif), bukan ambang absolut.

## Pola HRV pada Stres dan Kecemasan
Saat menghadapi stresor sosial-evaluatif seperti wawancara, keseimbangan otonom bergeser ke arah
simpatis. Pola khasnya (dibandingkan baseline pengguna): **RMSSD menurun, HF menurun, SDNN menurun,
LF/HF meningkat, dan detak jantung meningkat**. Semakin besar dan konsisten pola ini, semakin tinggi
indikasi tekanan.

## Reaktivitas
Reaktivitas adalah besarnya perubahan fitur HRV terhadap baseline pengguna ketika menghadapi stresor.
Reaktivitas tinggi (mis. RMSSD turun tajam, LF/HF naik tajam) menunjukkan respons tekanan yang kuat.
Reaktivitas dihitung sebagai selisih atau persentase perubahan terhadap baseline.

## Pemulihan (Recovery)
Pemulihan adalah seberapa cepat HRV kembali mendekati baseline setelah segmen menekan berlalu.
Pemulihan yang cepat menandakan kemampuan mengelola tekanan yang baik; pemulihan yang lambat
menandakan tekanan yang bertahan. Pemulihan diukur dari laju kembalinya fitur HRV ke baseline pada
segmen setelah stresor.

## Indeks Ketahanan (Resilience)
Ketahanan terhadap tekanan dinilai dari kombinasi **reaktivitas** dan **pemulihan**. Ketahanan tinggi =
reaktivitas terkendali disertai pemulihan cepat. Ketahanan rendah = reaktivitas besar disertai
pemulihan lambat. Indeks ini merupakan gambaran kemampuan pengguna mengelola tekanan sepanjang sesi.

## Faktor Pengganggu HRV
Interpretasi HRV harus memperhatikan faktor pengganggu: usia (HRV menurun seiring usia), jenis kelamin,
ritme dan kedalaman pernapasan, postur tubuh, aktivitas fisik sebelum pengukuran, serta konsumsi kafein
dan nikotin. Faktor-faktor ini dapat menyerupai atau menutupi perubahan akibat tekanan, sehingga
perbandingan terhadap baseline pengguna sendiri lebih dapat diandalkan.

## HRV Ultra-Short-Term (segmen 60 detik)
Pada rekaman sangat singkat seperti segmen 60 detik, fitur **domain waktu (terutama RMSSD dan detak
jantung)** relatif andal, sedangkan fitur **domain frekuensi (terutama LF)** kurang stabil karena
memerlukan jendela lebih panjang. Karena itu, pada segmen pendek, prioritaskan RMSSD dan reaktivitasnya,
dan tafsirkan LF/HF secara lebih hati-hati.

## Pedoman Interpretasi Tingkat Tekanan (berbasis pola, relatif ke baseline)
- **Tekanan rendah:** fitur HRV mendekati atau di atas baseline pengguna; RMSSD/HF stabil; LF/HF tidak meningkat berarti.
- **Tekanan sedang:** perubahan moderat terhadap baseline; RMSSD/HF sedikit menurun; LF/HF sedikit meningkat.
- **Tekanan tinggi:** penurunan jelas pada RMSSD dan HF, disertai kenaikan LF/HF dan detak jantung.
Penilaian akhir harus mempertimbangkan **reaktivitas** (besar perubahan) dan **pemulihan** (kecepatan kembali), bukan satu nilai tunggal.

## Batasan dan Etika Interpretasi
Sistem memberi **indikasi tekanan/stres berbasis fisiologi**, bukan diagnosis kecemasan klinis.
Interpretasi bersifat mendukung latihan, bukan penilaian medis. Hasil dapat dipengaruhi kualitas sinyal
dan faktor pengganggu, sehingga sebaiknya disertai skor keyakinan dan divalidasi terhadap data berlabel.

---

## Sumber
- Shaffer, F., & Ginsberg, J. P. (2017). *An Overview of Heart Rate Variability Metrics and Norms.* Frontiers in Public Health, 5, 258.
- Nunan, D., Sandercock, G. R. H., & Brodie, D. A. (2010). *A quantitative systematic review of normal values for short-term HRV in healthy adults.*
- Task Force of ESC/NASPE (1996). *Heart rate variability: standards of measurement, physiological interpretation, and clinical use.*
- (Lengkapi dengan rujukan dari kajian pustaka proposalmu.)
