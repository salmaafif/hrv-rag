# Seberapa meleset boleh? Anggaran galat detak jantung untuk versi smartwatch

Dokumen ini menjawab satu pertanyaan yang harus dijawab sebelum memilih jam
tangan, merek, atau bentuk aplikasi: **sistem ini masih bekerja sampai detak
jantung meleset berapa?**

Pertanyaan "apakah detak jantung saja cukup" sudah dijawab sebelumnya. Ablasi #9
menahan RMSSD dari sepuluh subjek WESAD yang disegel dan hasilnya justru naik,
macro-F1 0.871 lawan 0.839 saat RMSSD ikut dipakai. Tetapi ablasi itu menahan
satu fitur dari detak jantung yang sempurna, hasil deteksi puncak R pada ECG
dada 700 Hz. Smartwatch tidak memberi detak jantung yang sempurna. Ia memberi
angka yang sudah dihaluskan, terlambat beberapa detik, kadang salah, dilaporkan
tiap beberapa detik, dan tanpa satu pun interval antar-denyut.

Jadi yang diukur di sini bukan "apakah jam tangan cukup akurat", melainkan
berapa besar galat yang masih ditanggung aturannya. Angka itu bisa dibandingkan
dengan apa pun yang tertulis di literatur untuk perangkat kandidat.

## Cara mengukur

Data: sepuluh subjek uji WESAD yang tidak pernah dilihat saat kalibrasi
(S3, S4, S5, S7, S8, S9, S11, S13, S15, S16), 561 jendela 60 detik dengan
lompatan 30 detik. Aturan: versi beku `K16-2026-08-03`, ambang HR +5% dan +15%,
RMSSD diisi NaN persis seperti yang akan terjadi di lapangan.

Nilai detak jantung tiap jendela diganti dengan angka yang akan dilaporkan jam
tangan, lalu **baseline pribadi dihitung ulang dari jendela istirahat yang juga
sudah terkena galat yang sama**. Bagian terakhir itu penting. Kalau baseline
diambil dari sinyal bersih, simulasinya memberi jam tangan sebuah acuan yang
tidak mungkin dimilikinya, dan semua baris di bawah akan terlihat lebih bagus
daripada kenyataannya.

Tiap baris berisik diulang 200 kali dengan benih tetap; yang dilaporkan adalah
rata-rata dan rentang persentil 5 sampai 95.

Titik acuan: pengklasifikasi sepele yang selalu menjawab "rendah" mendapat
macro-F1 0.401 pada data ini. Itu lantainya.

## Hasil 1: salah secara konsisten tidak ada biayanya

| Simpangan tetap | macro-F1 | kappa |
|---|---|---|
| −10% | 0.871 | 0.742 |
| −5% | 0.871 | 0.742 |
| 0% | 0.871 | 0.742 |
| +5% | 0.871 | 0.742 |
| +10% | 0.871 | 0.742 |

Tidak berubah sama sekali, dan memang harus begitu. Jendela yang dinilai dan
baseline pribadi dikalikan faktor yang sama, sedangkan aturannya hanya membaca
rasio keduanya. Ini Aturan Wajib #2 yang sedang membayar dirinya sendiri.

Konsekuensi praktisnya besar untuk pemilihan perangkat: **jam tangan tidak perlu
sepakat dengan monitor klinis, ia perlu salah secara konsisten terhadap dirinya
sendiri selama satu sesi.** Usaha kalibrasi yang diarahkan ke bias tetap adalah
usaha yang dihabiskan untuk satu-satunya galat yang sudah gratis.

Membulatkan ke bpm bulat, yang dilakukan semua jam tangan, memakan 0.008:
macro-F1 turun dari 0.871 ke 0.863. Itu satu-satunya biaya yang muncul sebelum
galat sungguhan ditambahkan.

## Hasil 2: galat acak per jendela

| SD (bpm) | macro-F1 | persentil 5-95 | selisih |
|---|---|---|---|
| 0 | 0.863 | — | −0.008 |
| 1 | 0.859 | 0.846-0.873 | −0.012 |
| 2 | 0.840 | 0.821-0.857 | −0.031 |
| 3 | 0.815 | 0.796-0.836 | −0.056 |
| 5 | 0.769 | 0.751-0.789 | −0.102 |
| 8 | 0.723 | 0.701-0.744 | −0.148 |
| 12 | 0.685 | 0.665-0.706 | −0.186 |

Ini galat yang mahal, dan mahalnya dua kali: sekali di jendela yang sedang
dinilai, sekali lagi di jendela istirahat yang menjadi bahan median baseline.
Baseline lebih terlindungi karena median atas banyak jendela meratakan galatnya,
dan itulah sebabnya penurunannya tidak selinear yang diduga.

## Hasil 3: meleset hanya saat orangnya tertekan

| Bias saat tertekan (bpm) | macro-F1 | selisih |
|---|---|---|
| 0 | 0.863 | −0.008 |
| −2 | 0.848 | −0.023 |
| −4 | 0.839 | −0.032 |
| −6 | 0.825 | −0.046 |
| −8 | 0.818 | −0.053 |
| −12 | 0.795 | −0.076 |

Ini yang berbahaya, karena dua mekanisme nyata mengarah ke arah yang sama.
Rata-rata bergerak selalu tertinggal ketika detak jantung sedang naik, dan
sensor optik memburuk ketika pemakainya bergerak dan berbicara. Sesi wawancara
adalah persis keadaan itu. Uji akurasi statis di meja tidak akan pernah
menangkapnya.

## Hasil 4: kedua galat bersama-sama

| SD (bpm) | Bias saat tertekan | macro-F1 | persentil 5-95 |
|---|---|---|---|
| 2 | −2 | 0.826 | 0.808-0.843 |
| 3 | −4 | 0.788 | 0.768-0.806 |
| 5 | −4 | 0.744 | 0.723-0.763 |
| 5 | −8 | 0.721 | 0.702-0.741 |
| 8 | −8 | 0.675 | 0.653-0.698 |

## Menempelkan angka perangkat nyata ke tabel di atas

Tiga sumber yang relevan, dengan DOI:

**Menghini et al. 2019, *Psychophysiology*, DOI [10.1111/psyp.13441](https://doi.org/10.1111/psyp.13441).**
Empatica E4 di pergelangan tangan lawan ECG, dirancang khusus untuk kondisi
stres. Duduk diam: −0.01 ± 0.1 bpm. Kondisi yang melibatkan gerakan dan bicara:
−2.5 ± 12.5 bpm. Ini studi yang paling dekat dengan skenario kita, dan arah
biasnya negatif, sesuai dugaan pada Hasil 3.

**Bent et al. 2020, *npj Digital Medicine*, DOI [10.1038/s41746-020-0226-6](https://doi.org/10.1038/s41746-020-0226-6).**
MAE saat istirahat: Apple Watch 4 sebesar 4.4 bpm, Xiaomi Mi Band 3 sebesar
10.2 bpm, Empatica E4 sebesar 11.3 bpm, Biovotion Everion sebesar 16.5 bpm.
Rata-rata perangkat konsumen 7.2 ± 5.4 bpm saat istirahat dan 10.2 ± 7.5 bpm
saat beraktivitas. Galat saat aktivitas rata-rata 30% lebih besar daripada saat
istirahat. Warna kulit tidak berpengaruh signifikan.

**Meta-analisis Apple Watch 2025, *npj Digital Medicine*, DOI [10.1038/s41746-025-02238-1](https://doi.org/10.1038/s41746-025-02238-1).**
Gabungan 22 studi, n = 1247. Bias −0.27 bpm, batas kesepakatan −7.19 sampai
+6.64 bpm. Saat istirahat batasnya −8.14 sampai +8.56 bpm. Hanya satu studi yang
memvalidasi HRV, jadi tidak ada dasar untuk mengklaim apa pun soal variabilitas
dari jam tangan ini.

**Satu peringatan sebelum angka-angka itu dimasukkan ke tabel.** Angka MAE di
atas adalah galat per sampel, bukan per jendela 60 detik. Merata-ratakan satu
menit menurunkan komponen acaknya, tetapi galat sensor optik berkorelasi antar
waktu, jadi penurunannya lebih kecil daripada akar jumlah sampel. SD per jendela
2 sampai 5 bpm adalah padanan yang konservatif dan masuk akal untuk perangkat
dengan MAE per sampel 4 sampai 11 bpm.

Artinya, perkiraan terbaik saat ini:

- Jam tangan kelas bagus, dipakai duduk, sedikit bergerak: baris SD 2 dengan
  bias −2, sekitar **macro-F1 0.83**.
- Jam tangan kelas E4 saat orangnya berbicara dan bergerak: baris SD 3 dengan
  bias −4, sekitar **macro-F1 0.79**.

Keduanya masih jauh di atas lantai 0.401, dan berada di sekitar angka aturan
lengkap dengan ECG dada yang memakai RMSSD, yaitu 0.839. Itu jawaban yang bisa
dibawa ke dosen: **memakai smartwatch memang menurunkan akurasi, tetapi
turunnya sekitar 0.04 sampai 0.08 macro-F1, bukan runtuh.**

## Yang belum terjawab dan tidak boleh diklaim

1. **Kelambatan saat transisi.** Blok istirahat dan blok TSST di WESAD tidak
   bersebelahan dalam rekaman, karena ada blok amusement dan meditasi di
   antaranya. Masing-masing diambil sebagai potongan terpisah, sehingga
   penghalusan tidak pernah melewati detik ketika tekanan dimulai. Padahal di
   situlah rata-rata bergerak paling merugikan. Ini hanya bisa diukur dari
   rekaman di mana tenang dan tertekan benar-benar berurutan, yaitu protokol
   tiga blok yang sudah ada, diulang dengan jam tangan di pergelangan satunya.
2. **RMSSD hilang seluruhnya.** Bukan sekadar kurang akurat, memang tidak ada.
   Konsekuensinya kuadran Ketahanan dan angka pemulihan tidak bisa dihitung,
   karena `DynamicsConfig.primary_feature` adalah `rmssd`. Desain kartu di
   website sudah punya keadaan tereduksi ini, jadi tampilannya tidak perlu
   diubah, tetapi laporannya harus menyebut apa yang hilang.
3. **Ini simulasi jam tangan, bukan jam tangan.** Tabel di atas menyatakan
   berapa banyak galat yang ditanggung aturannya. Ia tidak menyatakan berapa
   galat yang dibuat perangkat tertentu. Angka kedua itu harus datang dari
   perangkatnya sendiri.

## Usulan langkah berikutnya, berurutan

1. Jalankan `python scripts/simulate_watch.py --emulate` di laptop yang punya
   WESAD. Mode itu membangun ulang aliran detak jantung gaya jam tangan dari
   denyut aslinya dan menguji sembilan kombinasi interval pelaporan dan lebar
   penghalusan. Hasilnya melengkapi tabel di atas dari sisi yang berbeda.
2. Rekam protokol tiga blok sekali lagi: HW9 di lengan sebagai acuan, jam tangan
   kandidat di pergelangan, keduanya serentak. Dari rekaman itu keluar dua angka
   yang hilang, yaitu SD per jendela dan bias saat tertekan untuk perangkat yang
   benar-benar akan dipakai. Cocokkan ke tabel, dan macro-F1-nya terbaca
   langsung.
3. Baru setelah itu tentukan bentuk aplikasinya. Urutannya penting: menentukan
   arsitektur aplikasi sebelum tahu perangkat mana yang lolos berarti membangun
   untuk perangkat yang mungkin tidak lolos.

## Cara menjalankan

```
python scripts/simulate_watch.py               # tabel anggaran galat di atas
python scripts/simulate_watch.py --trials 500  # rentang lebih rapat, lebih lama
python scripts/simulate_watch.py --selftest    # uji jalur emulasi tanpa WESAD
python scripts/simulate_watch.py --emulate     # emulasi tingkat denyut, butuh WESAD
```

Mode `--selftest` memakai denyut buatan dan sepuluh orang yang tidak ada.
Angkanya tidak boleh dikutip. Gunanya hanya memastikan jalur emulasi berjalan
sebelum memuat ratusan megabyte WESAD.
