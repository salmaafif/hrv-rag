# Perjalanan Pengembangan Sistem

**Interpretasi Tingkat Tekanan dari HRV dengan RAG**
Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Modul untuk platform latihan wawancara kerja KARIRLINK

Dokumen ini mencatat **apa yang dikerjakan, apa yang ditemukan, dan kenapa
keputusannya diambil**. Berbeda dengan `BACKLOG.md` yang melacak status pekerjaan,
dokumen ini menyimpan penalarannya — bahan yang paling sulit direkonstruksi
belakangan dan paling dibutuhkan saat menyusun laporan serta menghadapi sidang.

Periode: 25 Juli – 3 Agustus 2026.

---

## 1. Ringkasan Sistem

Sistem menilai tingkat tekanan pengguna dari HRV saat simulasi wawancara kerja,
**tanpa melatih model machine learning**. Fitur HRV dihitung deterministik oleh
Python, lalu ditafsirkan oleh LLM (Gemini) yang dibekali pengetahuan domain lewat
pendekatan RAG.

Metode ini menggantikan rencana awal berupa perbandingan empat arsitektur deep
learning. Yang dihilangkan **hanya tahap pelatihan model** — pra-pemrosesan sinyal
dan ekstraksi fitur tetap wajib dan tidak berubah sedikit pun.

Pemisahan tanggung jawabnya tegas dan menjadi klaim utama TA ini:

| Dihitung **kode** | Dihasilkan **LLM** |
|---|---|
| Fitur HRV per segmen | Label tingkat tekanan |
| Baseline personal | Skor keyakinan |
| Reaktivitas (% perubahan) | Alasan penilaian |
| Pemulihan, indeks ketahanan | Rekomendasi latihan |
| Peringkat pemicu sepanjang sesi | Rujukan chunk pengetahuan |

---

## 2. Kronologi Pekerjaan

| Tahap | Isi | Status |
|---|---|---|
| 0 | Fondasi repo, struktur paket, `config/settings.py` | selesai |
| 1 | `preprocessing/` — ECG mentah → deret RR bersih | selesai |
| 2 | `features/` — segmentasi, fitur, baseline, reaktivitas, dinamika | selesai |
| U1 | Uji perangkat lunak — 62 uji | selesai |
| 3a | Knowledge base `kb_v2.0` — 23 chunk | selesai (sitasi belum diverifikasi) |
| 3b | `rag/kb_index.py` + `rag/retrieval.py` | selesai |
| 4 | `rag/` — kueri, prompt, Gemini, pengaman | selesai |
| 5 | `evaluation/` — metrik vs label | belum |
| 6 | Cabang PPG (WESAD wrist BVP) | belum |
| 7–8 | SWELL-KW, UBFC-Phys | blokir — dataset belum ada |
| 9 | FastAPI + dashboard | belum |

---

## 3. Keputusan Desain Penting

Daftar lengkap ada di `BACKLOG.md` (K1–K15). Yang berikut ini paling mungkin
ditanyakan penguji.

### 3.1 Kenapa retrieval ditulis manual, tanpa framework dan tanpa vector store

Knowledge base hanya 23 chunk. Seluruh embedding-nya berupa matriks 23 × 3072
float32, sekitar 280 KB — muat penuh di memori. Indeks pencarian baru memberi
manfaat pada puluhan ribu dokumen; pada skala ini ia hanya menambah dependensi dan
berkas basis data tanpa mempercepat apa pun.

Pencarian cukup satu perkalian matriks terhadap vektor yang sudah dinormalkan.
Beberapa baris kode yang bisa dijelaskan seluruhnya saat sidang lebih berharga
daripada pustaka yang harus dipercaya begitu saja.

### 3.2 Kenapa perbandingan selalu terhadap baseline pengguna sendiri

Nilai HRV sangat individual — dipengaruhi usia, jenis kelamin, ritme pernapasan,
postur, dan kafein. Pada data ini saja, RMSSD baseline antar subjek berbeda lebih
dari lima kali lipat (S10: 14,4 ms; S17: 77,6 ms). Ambang absolut lintas orang akan
menyesatkan, jadi yang dimodelkan adalah reaktivitas, bukan nilai mentah.

### 3.3 Kenapa ketahanan berupa kuadran, bukan skor 0–100

Angka seperti "ketahanan 72" hanya bermakna bila ada pembanding, dan pembanding itu
mengharuskan perbandingan antar individu — persis yang dihindari poin 3.2. Kuadran
2×2 (reaktivitas besar/kecil × pemulihan cepat/lambat) menyampaikan informasi yang
sama tanpa berpura-pura presisi.

### 3.4 Kenapa kode tidak menggabungkan fitur menjadi satu skor

Kode berhenti pada reaktivitas **per fitur**. Penggabungan kelima angka itu adalah
tugas LLM yang berbekal knowledge base. Kalau kode yang menggabungkan, LLM tinggal
membaca ambang dan seluruh pendekatan RAG kehilangan alasan keberadaannya.

Rumus penggabungan tetap akan ditulis — tetapi sebagai **pembanding berbasis
aturan** (U3.1), untuk dilawankan dengan RAG saat evaluasi.

### 3.5 Kenapa keluaran dua lapis

Pengguna KARIRLINK tidak perlu — dan tidak seharusnya — melihat RMSSD atau LF/HF.
Lapisan pengguna berbahasa Indonesia dan berbahasa awam; lapisan teknis menyimpan
seluruh angka dan penalaran untuk diaudit saat sidang. Keduanya dihasilkan dalam
satu panggilan LLM.

Umpan balik dirumuskan sebagai **perilaku yang dapat dilatih**, bukan label tentang
diri seseorang. "Butuh waktu lebih lama untuk kembali tenang setelah pertanyaan
sulit" — bukan "kapasitas regulasi emosi Anda rendah". Selain lebih baik secara UX,
ini menjaga sistem tetap berada di sisi indikasi tekanan dan bukan penilaian
psikologis.

### 3.6 Kenapa subjek uji disegel sejak awal

Meski tidak ada model yang dilatih, **menyetel prompt dan knowledge base sambil
melihat hasil tetap merupakan bentuk fitting**. Kalau prompt disusun dengan melihat
seluruh 15 subjek lalu F1 dilaporkan dari 15 subjek yang sama, angkanya terlalu
optimistis.

Pembagiannya 5 subjek pengembangan (S2, S6, S10, S14, S17 — dipilih menyebar) dan
10 subjek uji yang disegel. Pembagian **per subjek, tidak pernah per segmen**,
karena baseline dihitung per subjek sehingga segmen milik orang yang sama berbagi
acuan.

---

## 4. Temuan Empiris

Bagian ini yang paling sulit direkonstruksi belakangan. Semua angka di bawah berasal
dari pengukuran nyata pada data WESAD, bukan perkiraan.

### 4.1 Bug koreksi ektopik: 59,5% versus 1,5%

Spesifikasi menyebut denyut ditandai outlier bila berselisih >20% dari **interval
sebelumnya**. Sempat dicoba varian yang membandingkan terhadap "interval terakhir
yang diterima", dengan maksud mencegah satu artefak merembet ke denyut berikutnya.

Efeknya justru kebalikannya. Begitu satu denyut ditolak, nilai acuannya membeku,
lalu seluruh denyut sesudahnya yang menyimpang dari acuan basi itu ikut ditolak
beruntun. Pada S2 kondisi tertekan, 59,5% denyut tertandai — padahal kriteria
harfiah hanya menandai 1,5%, dan tidak ada satu pun RR di luar batas fisiologis.

**Pelajaran:** menyimpang dari spesifikasi tanpa diuji itu berbahaya, dan yang
menangkapnya adalah pemeriksaan kualitas otomatis, bukan mata. Uji regresi
`test_flagging_does_not_cascade` kini menjaga agar bug itu tidak kembali.

### 4.2 Rata-rata membalik kesimpulan; median tidak

Ringkasan reaktivitas awalnya memakai rata-rata dan menghasilkan pNN50 **+61,8%**
pada fase tertekan — berlawanan dengan seluruh literatur.

Ternyata bukan fiturnya yang salah, melainkan statistik ringkasnya. Persentase
perubahan **tidak simetris**: penurunan mentok di −100%, sedangkan kenaikan tak
terbatas — pada data ini terukur sampai +442%. Rata-rata tertarik ke atas oleh ekor
kanan yang panjang. Dengan median, pNN50 menjadi **−61,2%**.

**Konsekuensi:** seluruh peringkasan reaktivitas di TA ini wajib memakai median.

### 4.3 Dua dari lima subjek berpola terbalik

| Subjek | RMSSD | pNN50 | HF | meanHR | Pola |
|---|---|---|---|---|---|
| S2 | −33,5% | −52,5% | −53,5% | +5,1% | sesuai teori |
| S14 | −69,9% | −93,9% | −85,6% | +74,0% | sesuai teori |
| S17 | −66,2% | −84,2% | −76,4% | +63,8% | sesuai teori |
| **S6** | **+30,0%** | **+105,9%** | **+258,7%** | +13,4% | **terbalik** |
| **S10** | **+63,4%** | **+442,2%** | **+478,9%** | +7,9% | **terbalik** |

Dua dugaan penyebab:

**Pengaruh berbicara.** TSST menuntut subjek berbicara di depan penilai. Berbicara
mengubah pola napas menjadi lebih dalam dan lambat, dan karena pita HF digerakkan
pernapasan, hal itu dapat menaikkan HF dan RMSSD secara artifisial — menutupi
penurunan akibat tekanan.

**Baseline S10 tampaknya bukan istirahat sejati.** RMSSD 14,4 ms dengan detak 99 bpm
saat kondisi "diam" tidak wajar untuk duduk santai. Indikator kestabilan baseline
menandai IQR relatif 52% pada subjek ini — jauh di atas subjek lain (14–17%).

**Kenapa temuan ini menguntungkan TA:** detak jantung naik pada **kelima** subjek
(+5,1% s.d. +74%), sementara RMSSD hanya benar arah pada tiga. Artinya aturan ambang
sederhana berbasis RMSSD akan salah pada 2 dari 5 orang, sedangkan sistem RAG yang
tahu tentang faktor pengganggu bisa menimbang detak jantung dan menyatakan
ketidakpastian. Inilah kasus konkret yang membuat ablasi U3.1 dan U3.2 bermakna.

Temuan ini juga langsung melahirkan dua chunk baru di knowledge base:
`KB-CONF-02` (pengaruh berbicara) dan `KB-INTERP-02` (menangani pola tidak khas).

### 4.4 Welch dan Lomb-Scargle berbeda 36,8%

Dua metode domain frekuensi dihitung berdampingan (keputusan K2). Pada 293 segmen:

- Korelasi Pearson LF/HF: **0,748**
- Selisih relatif median: **36,8%**
- Rerata Welch 3,09 versus Lomb-Scargle 3,41

Keduanya sepakat soal arah tetapi berbeda nyata dalam besaran. Ini memperkuat
catatan knowledge base bahwa LF/HF pada segmen 60 detik harus ditafsirkan
hati-hati, dan menjadi bahan pembahasan yang bagus di sidang.

Bukti pendukungnya sudah terlihat sejak awal: satu segmen **kalibrasi** S2 —
kondisi istirahat — menunjukkan LF/HF +288% terhadap baseline-nya sendiri. Fitur
yang sestabil itu tidak layak menjadi penentu tunggal.

### 4.5 Retrieval lintas-bahasa menurunkan skor secara konsisten

Awalnya knowledge base berbahasa Indonesia sementara kueri hendak dibuat berbahasa
Inggris. Diuji langsung terhadap indeks yang sama:

| Kueri | Skor Indonesia | Skor Inggris | Selisih |
|---|---|---|---|
| Pola stres baku | 0,806 | 0,756 | −0,050 |
| PPG smartwatch | 0,782 | 0,743 | −0,039 |
| Pola terbalik | 0,821 | 0,768 | −0,053 |
| Pertanyaan teknis | 0,709 | **0,627** | −0,082 |
| Pemulihan | 0,747 | 0,689 | −0,058 |

Penurunannya konsisten tanpa kecuali. Yang menentukan: kueri "pertanyaan teknis"
jatuh ke 0,627, **di bawah ambang relevansi**, sehingga akan mengembalikan nol chunk
dan LLM tidak mendapat konteks sama sekali.

Karena itu knowledge base diterjemahkan ke bahasa Inggris (`kb_v2.0`). Setelah satu
bahasa, seluruh skor pulih naik 0,03–0,08.

### 4.6 Ambang kemiripan harus diukur, bukan ditebak

Embedding Gemini menghasilkan skor yang berkumpul di rentang sempit. Kalibrasi
dengan kueri yang sengaja tidak relevan:

| Jenis kueri | Skor tertinggi |
|---|---|
| Sangat relevan | 0,807 |
| Agak relevan | 0,661 |
| Tidak relevan (3 kueri berbeda) | 0,527 – 0,561 |

Ambang awal 0,30 yang semula dipakai ternyata tidak pernah menyaring apa pun —
teks tentang resep rendang pun mendapat 0,56. Ambang ditetapkan **0,60**, tepat di
celah antara pita "tidak relevan" dan "agak relevan".

### 4.7 Skor retrieval sangat berdempet, dan urutannya rapuh

Pada kueri pola stres, tiga chunk teratas hanya berjarak **0,009** (0,795 / 0,787 /
0,786). Akibatnya pada 2 dari 5 kueri uji, chunk yang paling tepat kalah tipis —
`KB-COGN-01` kalah **0,002** dari `KB-RECOV-02` untuk kueri tentang pertanyaan
teknis.

Ini bukan bug melainkan sifat embedding yang memampatkan segalanya ke rentang
sempit. Dua implikasinya: memakai k=3 dan bukan k=1 (mengambil satu teratas berarti
bertaruh pada selisih 0,002), dan inilah yang akan terukur di T3b.4 lewat
Precision@k.

### 4.8 Chunk rubrik penilaian tidak selalu terambil

Pada segmen **kalibrasi** S2 — yang seharusnya dinilai "rendah" — sistem menjawab
`uncertain`. Penyebabnya `KB-INTERP-01`, chunk yang mendefinisikan kriteria
rendah/sedang/tinggi, tidak masuk tiga besar.

Ini masalah struktural: chunk rubrik bersaing dengan chunk pengetahuan biasa,
padahal fungsinya berbeda. Usulan perbaikan (T4.7) adalah menyematkan `KB-INTERP-01`
di tiap prompt, terpisah dari k hasil pencarian. Belum dikerjakan karena mengubah
semantik retrieval dan berpengaruh ke rancangan ablasi.

### 4.9 Rantai temuan → pengetahuan → perilaku sistem terbukti utuh

Kasus S6 menunjukkan seluruh rantai bekerja:

1. Tahap 2 menemukan S6 berpola terbalik dari data
2. Tahap 3a menuliskannya sebagai chunk `KB-INTERP-02`
3. Pembangun kueri menandai pola terbalik secara otomatis
4. Retrieval mengambil `KB-INTERP-02` sebagai chunk teratas
5. LLM menjawab `uncertain` dengan keyakinan 0,4, menyebut konflik bukti secara
   eksplisit, dan menolak memaksakan label

Tanpa chunk itu, penalaran buku teks akan menyimpulkan "tidak ada tekanan" padahal
detak jantung naik 11%. Ini bukti langsung kontribusi knowledge base.

### 4.10 Keyakinan belum terkalibrasi

Segmen S14 mendapat keyakinan **1,0 tiga kali berturut-turut**, tanpa menyebut satu
pun keterbatasan — padahal segmennya 60 detik dan LF/HF diketahui tidak stabil.
Keyakinan sempurna hampir tidak pernah wajar. Perlu diperbaiki di prompt v2, dan
inilah yang akan terukur sebagai kalibrasi keyakinan (T5.7).

### 4.11 Pembanding berbasis aturan sudah memberi bar yang tidak rendah

Dijalankan pada **seluruh 293 segmen** subjek pengembangan, tanpa satu pun panggilan
LLM. Inilah angka yang harus dilampaui sistem RAG agar keberadaannya terbukti
bermanfaat (U3.1).

| Pembanding | Accuracy | Macro-F1 | Kappa |
|---|---|---|---|
| Selalu menjawab "low" | 0,638 | 0,390 | **0,000** |
| Aturan RMSSD saja | 0,775 | 0,742 | 0,487 |
| Aturan RMSSD **atau** detak jantung | **0,840** | **0,828** | **0,656** |

Tiga hal yang terbaca dari tabel ini:

**Accuracy sendirian menyesatkan.** Menjawab "low" untuk semua segmen sudah
menghasilkan 63,8%, semata karena fase kalibrasi hampir dua kali lebih panjang
daripada TSST. Kappa-nya 0,000 — persis menunjukkan tidak ada kesepakatan di atas
kebetulan. Karena itu kappa selalu dilaporkan berdampingan dengan accuracy.

**Menambahkan detak jantung menaikkan kappa 0,169.** Kenaikan yang besar untuk satu
fitur tambahan, dan arahnya persis seperti yang diperkirakan dari temuan 4.3.

**Perbaikannya terpusat di dua subjek berpola terbalik**, sebagaimana seharusnya:

| Subjek | RMSSD saja | + detak jantung | Selisih |
|---|---|---|---|
| S2 | 0,95 | 0,95 | 0,00 |
| S14 | 0,98 | 0,98 | 0,00 |
| S17 | 0,93 | 0,92 | −0,01 |
| **S6** | 0,59 | **0,81** | **+0,22** |
| **S10** | 0,44 | **0,56** | **+0,12** |

Subjek berpola normal tidak berubah sama sekali, sementara S6 dan S10 melonjak. Ini
konfirmasi empiris paling langsung untuk keterbatasan L9. Perhatikan juga bahwa
aturan RMSSD saja pada S10 hanya mencapai 0,44 — **lebih buruk daripada menebak
"low" terus-menerus**.

**Konsekuensi untuk TA:** bar-nya bukan angka rendah. Sistem RAG harus melampaui
macro-F1 0,828 dan kappa 0,656 untuk membuktikan bahwa knowledge base dan LLM memberi
nilai tambah di atas aturan sederhana. Kalau tidak tercapai, itu temuan yang harus
ditulis apa adanya.

### 4.12 Kuota API tier gratis membatasi rancangan eksperimen

Ditemukan saat menjalankan evaluasi: tier gratis Gemini membatasi
**20 permintaan per hari** untuk `gemini-2.5-flash` (bukan hanya 5 per menit).

Dampaknya pada rencana kerja:

| Kebutuhan | Panggilan | Hari (tier gratis) |
|---|---|---|
| 293 segmen pengembangan | 293 | ~15 |
| Set uji (10 subjek) | ~600 | ~30 |
| Konsistensi 3 run | ×3 | ×3 |
| Enam ablasi U3.1–U3.6 | ×6 | ×6 |

Total kebutuhan seluruh rencana validasi mencapai ribuan panggilan — mustahil
diselesaikan pada tier gratis dalam kerangka waktu TA.

**Mitigasi yang sudah dibangun:** hasil tiap segmen disimpan ke
`outputs/assessment_cache.jsonl` begitu selesai, dengan kunci yang mencakup versi KB,
versi prompt, model, temperature, dan status penyematan chunk. Run yang terhenti
karena kuota dapat dilanjutkan keesokan harinya tanpa mengulang panggilan yang sudah
terpakai. Skrip juga berhenti rapi saat kuota habis, bukan gagal dan membuang hasil.

### 4.13 Cabang PPG: detak jantung sepakat, variabilitas tidak

Perbandingan berpasangan ECG dan PPG pada subjek dan segmen yang sama — bukti
terkuat yang tersedia, karena perbedaannya tidak bisa dijelaskan oleh orang berbeda,
hari berbeda, atau stresor berbeda.

**Nilai mutlak (91 segmen berpasangan, 5 subjek):**

| Fitur | ICC | r | Bias (PPG − ECG) |
|---|---|---|---|
| **meanHR** | **+0,936** | +0,967 | −1,7 bpm |
| pNN50 | +0,385 | +0,686 | +28,5 |
| LF/HF | +0,190 | +0,362 | −1,75 |
| SDNN | +0,132 | +0,354 | +61,5 ms |
| **RMSSD** | **+0,103** | +0,522 | **+97,0 ms** |
| HF | +0,091 | +0,363 | +4915 |

**Reaktivitas (persen perubahan terhadap baseline masing-masing):**

| Fitur | ICC |
|---|---|
| **Δ% meanHR** | **+0,925** |
| Δ% RMSSD | +0,513 |
| Δ% SDNN | +0,174 |
| Δ% pNN50 | +0,158 |

Tiga kesimpulan, dan ketiganya penting.

**Detak jantung dari PPG dapat dipercaya; variabilitasnya tidak.** ICC meanHR +0,936
dengan bias hanya −1,7 bpm. RMSSD ICC +0,103 dengan bias **+97 ms** — PPG melebihkan
RMSSD hampir dua kali lipat nilai baseline ECG yang sebenarnya. Ini konsisten dengan
penyebabnya: puncak sistolik yang landai membuat waktu denyut bergetar, dan getaran
itu langsung menggelembungkan selisih antar-denyut yang justru diukur RMSSD.

**Normalisasi terhadap baseline pribadi menyelamatkan sebagian.** RMSSD naik dari
ICC 0,103 (mutlak) menjadi **0,513** (reaktivitas). Sebabnya bias sistematis PPG
sebagian besar tetap konstan dalam satu subjek, sehingga ikut terbagi habis saat
dihitung persen perubahan terhadap baseline orang itu sendiri. Ini pembenaran empiris
langsung untuk Aturan Wajib #2 — dan argumen kuat bahwa memodelkan reaktivitas, bukan
nilai mentah, memang keputusan yang tepat.

**Kesepakatan runtuh saat tertekan, persis seperti diramalkan KB.** Deteksi denyut
PPG dibandingkan ECG: **101–103% saat kalibrasi**, hanya **78–84% saat TSST**. Pada
gerbang mutu produksi (20%), hampir seluruh segmen TSST tertolak — dari 91 pasangan
yang tersisa, hanya 9 berasal dari fase pertanyaan. Inilah `KB-MODAL-02` terkonfirmasi
pada data sendiri.

**Catatan metodologis.** Gerbang ektopik 20% menolak sekitar 98% segmen BVP WESAD.
Untuk studi perbandingan ini gerbangnya sengaja dilonggarkan ke 50% agar ada pasangan
yang bisa dibandingkan sama sekali, dan angka di atas karena itu adalah **batas
atas** — pipeline produksi melihat data yang lebih buruk. Melonggarkan gerbang di
produksi hanya akan menyuapkan derau ke penilaian. Diuji pada ambang 20/30/40/50%,
ICC RMSSD tetap di sekitar nol (0,014–0,103) di semuanya, jadi pelonggaran memang
tidak menyelamatkan apa pun.

**Konsekuensi untuk rencana TA:**

1. Klaim "perbandingan modalitas berpasangan sebagai bukti terkuat" tetap sah, tetapi
   kesimpulannya adalah **negatif untuk variabilitas dan positif untuk detak jantung**
   — bukan hasil yang diharapkan, tetapi hasil yang jelas dan dapat dipertahankan.
2. Aturan Wajib #5 (turunkan keyakinan untuk PPG) kini punya dasar kuantitatif,
   bukan sekadar kehati-hatian.
3. **UBFC-Phys (Tahap 8) berisiko**: dataset itu hanya PPG. Bila keterbatasan yang
   sama berlaku, uji arah perubahan di sana sebaiknya bersandar pada detak jantung,
   bukan RMSSD. Ini perlu diantisipasi sejak sekarang.

---

## 5. Penegakan Aturan Wajib #1

Klaim ilmiah TA ini bertumpu pada "kode yang menghitung, LLM yang menafsirkan".
Menginstruksikan LLM agar tidak menghitung adalah **permintaan, bukan jaminan**.
Karena itu keluaran diperiksa otomatis sesudahnya (`rag/guards.py`):

1. **Angka karangan** — tiap angka di penalaran LLM harus dapat ditelusuri ke
   prompt, baik ke fitur yang diberikan maupun ke isi chunk yang terambil.
   Toleransi pembulatan diberikan, karena menyebut "35%" untuk masukan "−35,2%"
   adalah mengutip, bukan mengarang.
2. **Rujukan palsu** — tiap ID chunk yang disitasi harus benar-benar termasuk yang
   terambil. Menyitasi chunk yang tidak pernah diberikan akan diam-diam merusak
   metrik faithfulness.

Hasil pada tiga segmen uji: **nol angka karangan, nol rujukan palsu**. Segmen S6
menyebut lima angka, seluruhnya cocok dengan masukan.

---

## 6. Status Validasi

**Sudah terverifikasi:**

- 62 uji perangkat lunak lolos, seluruhnya memakai masukan yang jawabannya diketahui
  lebih dulu — bukan data WESAD. Menguji dengan data nyata hanya menunjukkan hasil
  "masuk akal", bukan membuktikan hitungannya benar.
- Fitur domain frekuensi diuji dengan sinyal buatan berfrekuensi diketahui: deret RR
  yang bergoyang 0,25 Hz wajib muncul di pita HF, 0,10 Hz di pita LF.
- Rumus pemulihan terverifikasi terhadap contoh acuan (52,99%). Ini penting karena
  **WESAD tidak bisa mengujinya sama sekali** — tidak ada fase jeda setelah TSST.
- Reaktivitas fase kalibrasi menghasilkan tepat 0,0%, sebagaimana mestinya.

**Belum tervalidasi:**

- Metrik klasifikasi terhadap label (Tahap 5) — belum dikerjakan
- Pemulihan dan ketahanan pada data sesi nyata — WESAD tidak menyediakannya
- Beban kognitif — butuh metadata jenis pertanyaan yang tidak dimiliki WESAD
- Cabang PPG — belum dikerjakan
- Konsistensi antar-run baru diuji pada satu segmen

---

## 7. Keterbatasan yang Harus Ditulis di Laporan

Daftar lengkap L1–L10 ada di `BACKLOG.md`. Yang paling penting:

1. **Baseline pra-wawancara bukan baseline netral sejati.** Pengguna kemungkinan
   sudah cemas antisipatif saat kalibrasi, sehingga reaktivitas yang terukur
   cenderung lebih kecil dari sebenarnya.
2. **Segmen overlap 30 detik tidak saling bebas.** Jendela bertetangga berbagi
   separuh data, sehingga jumlah sampel efektif lebih kecil daripada jumlah baris.
3. **Menyetel prompt dan KB tetap merupakan fitting**, meski tidak ada model
   dilatih. Ditangani dengan menyegel 10 subjek uji.
4. **Beban kognitif dan tekanan sosial punya tanda HRV identik**; pemisahannya
   berbasis konteks pertanyaan, bukan fisiologi.
5. **Sistem bergantung pada layanan pihak ketiga.** Model Gemini dapat diperbarui
   sehingga hasil persis bisa tidak terulang. Ditangani dengan mencatat versi model,
   versi KB, dan versi prompt pada tiap keluaran.

---

## 8. Catatan Reproduksibilitas

Tiap keluaran sistem mencatat: versi knowledge base (`kb_v2.0`), versi prompt
(`v1`), nama model (`gemini-2.5-flash`), temperature, ID chunk yang terambil beserta
skornya, dan hasil kedua pengaman.

Prompt disimpan sebagai berkas berversi di `prompts/`, bukan sebagai string di dalam
kode. Alasannya: dalam desain RAG, prompt berperan setara arsitektur model pada
pendekatan deep learning, sehingga perubahannya harus terlihat, bertanggal, dan
dapat dikembalikan.

**Lubang yang masih terbuka:** `requirements.txt` belum mengunci versi pustaka.
Kalau `neurokit2` diperbarui dan algoritma deteksi puncak R-nya berubah, seluruh
angka di laporan ikut bergeser tanpa satu pun pesan kesalahan. Ini risiko
reproduksibilitas terbesar yang tersisa dan paling murah ditutup.

---

## 9. Langkah Berikutnya

1. Kunci versi pustaka di `requirements.txt`
2. Putuskan T4.7 (menyematkan chunk rubrik) sebelum evaluasi dijalankan
3. Perbaiki kalibrasi keyakinan di prompt v2
4. Tahap 5 — metrik klasifikasi, metrik retrieval, faithfulness, konsistensi
5. Verifikasi 11 sitasi bertanda ⚠ di knowledge base
6. Tahap 6 — cabang PPG, lalu perbandingan modalitas berpasangan
