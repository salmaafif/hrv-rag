# Arsitektur Modul HRV untuk KARIRLINK — Rancangan Jangka Panjang

**Interpretasi Tingkat Tekanan dari HRV dengan RAG**
Salma Afifa Azis (3123600017) — Teknik Informatika PENS

Ditulis 20 Agustus 2026.

Dokumen ini menjawab pertanyaan yang tidak dijawab dokumen lain di repo ini:
**modul ini akan jadi apa setelah PA selesai**, dan keputusan mana yang harus
diambil sekarang supaya jawabannya masih mungkin nanti.

Bedanya dengan dokumen yang sudah ada:

| Dokumen | Menjawab |
|---|---|
| `BACKLOG.md` | apa yang dikerjakan dan statusnya |
| `development_journey.md` | kenapa keputusannya diambil |
| `frontend_plan.md` | bentuk web demo dan kontrak API-nya |
| `handover.md` | posisi terakhir, buat lanjut sesi |
| `AKUISISI_HRV_WEB_BLUETOOTH.md` | perangkat keras dan cara mengambil datanya |
| **dokumen ini** | **bentuk produknya, dan gerbang mutu yang belum lewat** |

Kode keputusan baru dipakai di sini: **A** untuk arsitektur, **G** untuk gerbang
mutu. Kode lama (`K`, `T`, `L`, `HW`) merujuk ke `BACKLOG.md` dan
`AKUISISI_HRV_WEB_BLUETOOTH.md`.

---

## 0. Soal "shift left, tapi sudah terlambat"

Terlambat itu diukur terhadap **langkah termahal yang masih di depan**, bukan
terhadap kalender.

Shift left artinya memindahkan pemeriksaan mutu ke sedekat mungkin dengan saat
cacatnya dibuat, karena biaya memperbaiki cacat naik seiring jaraknya dari titik
itu. (Angka pengali yang sering dikutip — 10×, 100× — sebenarnya lemah dasarnya
dan sebaiknya tidak dikutip di laporan. Yang kokoh adalah arahnya, bukan
besarannya.) Di rekayasa perangkat lunak, titik termahal itu produksi. **Di
sebuah PA, titik termahal itu bukan deployment — melainkan pengambilan data
subjek.**

Kalau protokolnya cacat, kode bisa ditulis ulang dalam sehari. Dua puluh subjek
yang sudah pulang tidak bisa dipanggil ulang. Dan pengambilan data itu **belum
terjadi**. Jadi langkah paling mahal di seluruh proyek ini justru masih di depan,
dan shift left masih sepenuhnya berlaku terhadapnya.

Lebih dari itu: shift left sudah kamu praktikkan berkali-kali, cuma belum
dinamai.

- **Menyegel 10 subjek uji sebelum menyetel prompt** (K10, `development_journey`
  §3.6). Ini shift left dalam bentuk paling murni — keputusan yang mencegah
  optimisme palsu diambil *sebelum* ada hasil yang bisa memancing kompromi.
- **`guards.py` menegakkan Aturan Wajib #1 secara otomatis** (T4.6), bukan lewat
  instruksi ke LLM. Verifikasi berpindah dari waktu-tinjau ke waktu-jalan.
- **Aturan uji mutasi** di `handover.md` §6: rusak perbaikannya, pastikan tesnya
  gagal. Ini menutup cacat kelas "tes yang tidak menggigit" yang sudah tiga kali
  terjadi.
- **Tiga percakapan terakhir soal layar hasil** — menyelesaikan bentrok penamaan
  dan mencari bukti psikologi *sebelum* layarnya dikunci, bukan sesudah.

Yang memang sudah lewat dan tidak bisa digeser lagi, supaya jujur: perangkat
keras sudah dibeli; keputusan K1–K17 sudah beku dan 325 uji Python berdiri di
atasnya; arsitektur gabungan aturan+LLM sudah divalidasi dan tidak layak dibongkar.

Dan ada satu contoh nyata cacat yang **ketahuan terlambat**, yang justru
memperjelas kenapa gerbang di §5 penting: temuan bahwa **baseline 2 menit terlalu
pendek** (`handover.md` §5 — meleset 43% median, 102% terburuk, 0 dari 15 subjek
stabil dalam 2 menit) baru muncul setelah protokolnya dirancang. Kalau itu
ketahuan setelah pengambilan data, seluruh angka reaktivitas PA ini cacat dan
tidak ada perbaikan yang mungkin. Sekarang masih bisa.

**Kesimpulan: tidak terlambat. Tapi jendelanya sempit, dan sebagiannya punya
tenggat yang bukan tenggatmu** — masa pengembalian HW9 (§5, G1).

---

## 1. Batas modul

Yang paling sering merusak modul dalam produk orang lain bukan mutu modulnya,
melainkan batas yang tidak pernah ditulis. Jadi ditulis di sini.

**A1 — Modul ini memiliki satu tanggung jawab: mengubah deret interval RR menjadi
indikasi tekanan per pertanyaan, beserta narasi yang bisa ditindaklanjuti oleh
orang yang direkam.**

Yang **bukan** milik modul ini, sekarang maupun nanti:

- menjalankan wawancaranya (itu milik platform)
- menilai jawaban, isi, atau kualitas performa kandidat
- menyimpan identitas kandidat — modul menerima ID buram, bukan nama
- memutuskan siapa yang lolos

**A2 — Modul harus opsional dan bisa gagal tanpa menjatuhkan platform.**
Mayoritas pengguna KARIRLINK tidak akan punya sensor. Kalau modul HRV mati,
kehabisan kuota LLM, atau sensornya tidak terhubung, latihan wawancara harus
tetap jalan penuh dan hasilnya tetap keluar — hanya tanpa lapisan HRV. Ini
menentukan bentuk integrasinya: **pemanggilan terpisah setelah sesi selesai**,
bukan sisipan di jalur utama.

**A3 — Keluaran HRV tidak boleh pernah sampai ke perekrut.**
Ini pagar etis, bukan preferensi. Aturan Wajib #4 menyatakan keluarannya indikasi
tekanan dan bukan diagnosis. Begitu angka yang sama dipakai untuk memeringkat
pelamar, framing itu runtuh — dan yang dipakai memeringkat adalah sinyal yang,
menurut MASI (McCarthy & Goffin 2004), berkorelasi dengan penilaian pewawancara
cuma −0,07 sampai −0,28. Memeringkat orang dengan sinyal selemah itu bukan cuma
tidak etis, tapi juga tidak sahih.

Konsekuensi teknisnya konkret: **hasil HRV disimpan di ruang milik kandidat, tidak
di ruang lowongan.** Kalau nanti ada fitur "bagikan hasil", yang membagikan harus
kandidat, dan yang dibagikan bukan level tekanannya.

---

## 2. Tiga tingkat produk

Modalitas masukan tidak setara, jadi keluarannya tidak boleh setara. Temuan
§4.13 `development_journey` — **PPG sepakat soal detak jantung tapi tidak soal
variabilitas** — bukan catatan kaki, melainkan penentu bentuk produk.

**A4 — Permukaan keluaran ditentukan oleh mutu masukan, dan penurunannya
eksplisit.**

| | **T0 — Tanpa sensor** | **T1 — PPG (armband/jam)** | **T2 — ECG (chest strap)** |
|---|---|---|---|
| Perangkat | — | Coospo HW9 | Coospo H808S / Polar H10 |
| Fitur dasar | — | turunan **HR** saja | HR + RMSSD + domain frekuensi |
| Satuan keluaran | — | **per fase sesi** | **per pertanyaan** |
| Reaktivitas | — | ya (berbasis HR) | ya |
| Pemulihan | — | ya, kasar | ya |
| Ketahanan (kuadran) | — | tidak | ya |
| Pemicu teratas | — | ya, sebagai perkiraan | ya |
| Keyakinan dinyatakan | — | **diturunkan** | penuh |
| Latihan wawancara | penuh | penuh | penuh |

Yang membuat tabel ini bisa dipertanggungjawabkan bukan tabelnya, melainkan
percobaan yang belum dijalankan: **#9 ablasi HR-saja** (`handover.md` §4). Murah,
tidak butuh LLM, dan hasilnya menentukan apakah baris T1 di atas jujur. Kalau
aturan skor dengan fitur HR saja tetap di atas macro-F1 yang layak, T1 punya
dasar. Kalau jatuh, T1 harus dipangkas lagi atau dihapus.

**Naikkan prioritas #9.** Sekarang dia nomor sembilan dari dua belas; padahal
dialah satu-satunya yang menentukan apakah perangkat yang sudah dibeli bisa jadi
produk.

**A5 — Modalitas ikut di setiap keluaran, sampai ke layar.**
Aturan Wajib #5 sudah memasukkan modalitas ke prompt. `formatModality()` di
`frontend/src/lib/format.ts` sudah menampilkannya. Yang harus ditambahkan: **field
`tier` di respons API**, supaya klien tahu bagian mana yang boleh dirender tanpa
harus menebak dari ada-tidaknya field.

---

## 3. Kontrak API — yang sebenarnya diserahkan

`frontend_plan.md` §1 sudah menyatakan ini dengan tepat: yang diserahkan ke tim
web KARIRLINK adalah **kontrak API, bukan tampilan**. Bagian ini melanjutkannya ke
hal-hal yang baru muncul kalau frontend-nya dibangun orang lain.

### 3.1 Cacat arsitektur yang paling penting diperbaiki sekarang

Komentar di `frontend/src/components/SessionResult.tsx` menuliskannya sendiri:

> *"The rule cannot be enforced by the API — it can only be enforced here, on the
> screen that renders it."*

Untuk web demo, itu benar dan tidak masalah. **Untuk produk, itu cacat.** Tim web
akan membangun ulang frontend-nya. Begitu berkas itu diganti, satu-satunya tempat
K4 ditegakkan lenyap, dan tidak ada yang gagal — layarnya cuma mulai menampilkan
`delta_rmssd_pct` ke kandidat, diam-diam, dan tidak ada tes yang merah.

**A6 — K4 ditegakkan oleh bentuk respons, bukan oleh kesantunan klien.**

Perbaikannya murah karena API-nya **belum dibangun**:

```
POST /api/v1/analyze/session          -> hanya lapisan pengguna
POST /api/v1/analyze/session?debug=1  -> + data_teknis, butuh scope terpisah
```

Angka teknis tidak lagi "ada di respons tapi jangan ditampilkan". Angka teknis
**tidak dikirim** kecuali diminta oleh pemanggil yang memang berhak. Klien yang
ceroboh jadi tidak mungkin melanggar K4, bukan sekadar tidak seharusnya.

Ini contoh shift left paling bersih yang tersedia di proyek ini sekarang:
memindahkan penegakan aturan dari waktu-tinjau-kode ke waktu-desain-kontrak,
dengan biaya nyaris nol karena kontraknya belum jadi.

### 3.2 Yang stabil dan yang boleh berubah

Tim web perlu tahu apa yang boleh mereka andalkan. Tanpa ini mereka akan
mengandalkan semuanya, lalu rusak.

| Bagian respons | Janji |
|---|---|
| `level` (`low`/`moderate`/`high`) | **stabil** — ditetapkan aturan, deterministik, sama untuk masukan sama |
| `recovery_pct` termasuk `null`-nya | **stabil** — dan `null` tidak akan pernah berubah makna jadi nol |
| `summary.resilience` (kuadran) | **stabil** |
| `tier`, `modality` | **stabil** |
| `narrative.*` | **tidak stabil** — teks dari LLM, berubah kalau model atau KB berganti |
| `meta.*` | **stabil sebagai bentuk**, isinya memang berubah tiap versi |
| `data_teknis.*` | **tanpa janji** — internal, boleh berubah kapan saja |

**A7 — Yang deterministik dijanjikan; yang dihasilkan LLM tidak pernah
dijanjikan.** Ini perpanjangan langsung K16: aturan yang memberi label, LLM yang
menulis kalimat. Kalau kontraknya menjanjikan kalimat, K16 bocor ke luar sistem.

### 3.3 Versi dan reproduksibilitas

`meta` sudah membawa `kb_version` dan `model`. Yang perlu ditambahkan sebelum
diserahkan: **versi prompt** dan **versi aturan skor**. Alasannya sama dengan
alasan prompt disimpan sebagai berkas berversi (`development_journey` §8) — dalam
desain ini prompt setara arsitektur model. Hasil yang tidak bisa ditelusuri ke
versi prompt tidak bisa direproduksi saat sidang maupun saat ada keluhan pengguna.

### 3.4 Pintu masuk interval RR

Masih belum ada (`frontend_plan` §5, §7). Ini pekerjaan kecil — lewati deteksi
puncak, langsung ke koreksi ektopik — tapi dia **prasyarat untuk seluruh jalur
Bluetooth**, artinya prasyarat untuk pengambilan data subjek. Posisinya di jalur
kritis lebih tinggi daripada yang terlihat dari ukurannya.

---

## 4. Layar hasil — aturan yang mengikat, bukan saran

Bagian ini mengunci hasil tiga diskusi terakhir. Dasarnya sudah ditelusuri ke
literatur; sitasi lengkapnya di `docs/` terpisah kalau nanti dibuat.

**A8 — Tiga keluaran, dan tepat tiga.**
Dokumen menjanjikan Reaktivitas, Pemulihan, Ketahanan. Layar sempat punya empat
karena sumbu radar ketiga (`Endurance`) lahir untuk mengisi lubang bentuk grafik,
bukan karena ada yang perlu disampaikan. Keluaran yang tidak ada di dokumen tidak
boleh ada di layar.

**A9 — Reaktivitas ditampilkan dalam bentuk positifnya.**
Sumbu grafik harus searah "besar = baik", jadi yang tampil adalah *berapa
pertanyaan yang lewat dengan tenang*, bukan besar reaksinya. Pembalikan ini benar,
tapi harus tertulis di dokumen supaya penguji tidak menganggapnya
ketidakcocokan.

**A10 — Ketahanan adalah kesimpulan, bukan bahan.**
Ia diturunkan dari reaksi × pemulihan, jadi tidak boleh sesumbu dengan
komponennya sendiri. Tempatnya sesudah keduanya, dan namanya harus muncul —
sekarang kata "Ketahanan" tidak ada di layar sama sekali.

**A11 — Grafik radar tidak dipakai.**
Dua alasan yang saling bebas sampai di kesimpulan sama. Secara geometri, cuma ada
dua besaran yang jujur di data ini, dan radar dua sumbu itu garis. Secara
psikologi, bentuk radar dibaca sebagai profil kepribadian apa pun nama sumbunya —
komentar di `ResponseRadar.tsx` sudah mengakuinya sendiri — dan Feedback
Intervention Theory (Kluger & DeNisi 1996) menempatkan isyarat yang mengarahkan
perhatian ke diri sebagai asal dari 38% efek umpan balik yang **negatif**.
Penggantinya: plot kuadran reaksi × pemulihan, yang memang Ketahanan itu sendiri.

Kalau radar tetap dipertahankan karena alasan lain, satu-satunya isi yang bisa
dibela adalah **jenis pertanyaan** — itu menunjuk ke tugas, bukan ke orangnya, dan
itu yang direkomendasikan literatur visualisasi stres (mencocokkan intervensi ke
*sumber* stres). Konsekuensinya protokol harus menjamin minimal dua pertanyaan per
jenis.

**A12 — Tanpa label stres pada orangnya.**
Badge `Rendah`/`Sedang`/`Tinggi` adalah elemen paling berisiko di layar. Bukan
angkanya — angkanya sudah disembunyikan — melainkan katanya. Umpan balik detak
jantung memang memperbaiki kecocokan antara stres yang dirasakan dan fisiologi
sebenarnya, tapi orang dengan kepekaan cemas tinggi melaporkan stres **lebih
tinggi** justru ketika umpan baliknya diberi label stres. Ganti dengan deskripsi
perilaku: "tubuhmu bereaksi kuat di pertanyaan 4".

**A13 — Kalimat pembingkaian ulang (reappraisal) muncul lebih dulu, bukan
terakhir.**
Memberi tahu orang bahwa lonjakan tubuh saat tegang adalah sumber daya yang
membantu — bukan tanda bahaya — meningkatkan kinerja ujian (d = 0,55) dan
menurunkan kecemasan evaluasi (d = 0,53), dan efeknya bertahan sampai ujian
sungguhan berbulan-bulan kemudian (rangkaian studi Jamieson dkk). Ini
satu-satunya bagian layar yang punya bukti eksperimental mengubah apa yang terjadi
berikutnya, jadi ia pantas dibaca pertama. Kartu `penyemangat` sudah ada; isinya
yang harus diarahkan, dan posisinya yang harus naik.

**A14 — Ada baris rekonsiliasi.**
Studi CHI 2021 atas 17 pengguna arloji dengan fitur stress tracking menemukan
penyebab utama mereka berhenti memakainya bukan akurasi, melainkan ketidakcocokan
model mental: pengguna memahami stres secara psikologis, alat mengukurnya secara
fisiologis. Satu kalimat di layar mendahului itu — "kalau ini terasa tidak cocok
dengan yang kamu rasakan, itu wajar; alat ini membaca reaksi tubuh, yang tidak
selalu sama dengan perasaan."

**A15 — Ada satu pertanyaan balik ke kandidat.**
Umpan balik asesmen berkhasiat (d = 0,42) hanya kalau personal dan melibatkan;
versi standar tanpa itu tidak. Satu pertanyaan — "ini cocok tidak dengan yang kamu
rasakan tadi?" — memenuhi syarat itu **dan** memanen label subjektif yang bisa
dipakai validasi. Dua urusan, satu komponen.

**A16 — Ruang lingkup dinyatakan.**
HRV menyentuh satu dari lima dimensi kecemasan wawancara (MASI: Communication,
Appearance, Social, Performance, **Behavioral/autonomic**). Layar tidak boleh
menyiratkan ia mengukur "kecemasan wawancara" secara utuh, dan tidak boleh
menyiratkan tegang berarti tampil buruk.

Sisi baiknya juga layak ditulis di laporan: di studi yang sama, pengamat hampir
tidak bisa mendeteksi kecemasan pelamar. **Sensor ini memberi tahu kandidat
sesuatu yang tidak terlihat oleh pewawancara mana pun.** Itu proposisi nilai modul
ini, dan ada rujukannya.

---

## 5. Gerbang mutu — shift left yang masih bisa dijalankan

Diurutkan bukan berdasarkan waktu, melainkan berdasarkan **berapa mahal kalau
ketahuan setelahnya**.

### G1 — Sensor: uji RR di hari pertama · TENGGAT: masa pengembalian HW9

Yang diperiksa: perangkat benar-benar menyiarkan interval RR, dan bukan RR
sintetis (`60000/HR`). Alatnya sudah ada: `frontend/uji-sensor-hrv.html`.

Kalau lolos terlambat: uang hilang, dan seluruh cabang PPG PA ini kehilangan
perangkatnya. **Ini satu-satunya gerbang yang tenggatnya ditentukan pihak lain.**
Kerjakan lebih dulu dari apa pun di dokumen ini.

### G2 — Protokol: dry run pada diri sendiri sebelum menyentuh subjek

Yang diperiksa: durasi baseline, panjang jeda, urutan blok, dan posisi tangan.

Satu keputusan **harus** diambil di gerbang ini: **baseline 2 menit sudah terbukti
tidak cukup** — 0 dari 15 subjek WESAD stabil dalam 2 menit, median baru stabil di
4 menit, kesalahan median 43%. Temuan ini sudah ada di `handover.md` §5 dengan
status "belum diputuskan mau diapakan". Kalau ia masih "belum diputuskan" saat
subjek pertama datang, seluruh angka reaktivitas PA ini berdiri di atas acuan yang
diketahui keliru, dan tidak ada perbaikan pascahoc yang mungkin.

Kalau lolos terlambat: seluruh data subjek terbuang. **Gerbang termahal di
dokumen ini.**

### G3 — Pilot: satu sampai dua subjek, dianalisis sampai tuntas, baru lanjut

Yang diperiksa: bukan hasilnya, melainkan apakah pipeline-nya utuh dari sensor
sampai layar. Rekaman masuk, fitur keluar, label keluar, narasi keluar, gerbang
mutu jalan, ekspor terbaca.

Kalau lolos terlambat: cacat format atau cacat pipeline mengalikan dirinya ke
seluruh subjek. Analisis satu subjek sampai selesai jauh lebih murah daripada
mengulang dua puluh.

### G4 — Kontrak: bekukan API sebelum tim web menulis baris pertama

Yang diperiksa: A6 (pemisahan lapisan di tingkat respons), A7 (mana yang
dijanjikan), A5 (`tier` ada di respons), versi prompt dan versi aturan di `meta`.

Kalau lolos terlambat: perubahan kontrak setelah tim web membangun berarti
merusak pekerjaan orang lain, dan biasanya berakhir dengan kontraknya yang
mengalah — biasanya dengan cara membiarkan K4 bocor.

### G5 — Aturan keluaran jadi tes, bukan jadi konvensi

Yang diperiksa: A8–A16 punya tes yang menggigit. `find_k4_violations` sudah ada
dan sudah membuktikan nilainya — ia lahir justru karena `deepseek-r1:latest`
menulis "RMSSD, SDNN, dan pNN50" langsung ke teks pengguna sementara guards
melaporkan nol pelanggaran.

Perluas ke: tidak ada perbandingan antar-orang di teks, tidak ada label sifat,
tidak ada angka teknis di lapisan pengguna, `null` tidak pernah dirender sebagai
nol. Dan sesuai aturan di `handover.md` §6 — **uji mutasinya**: rusak
perbaikannya, pastikan tesnya gagal.

### G6 — Reproduksibilitas: kunci versi pustaka

`requirements.txt` belum mengunci versi. Kalau `neurokit2` diperbarui dan
algoritma deteksi puncak R-nya berubah, seluruh angka di laporan bergeser tanpa
satu pun pesan kesalahan. `development_journey` §8 sudah menyebutnya "risiko
reproduksibilitas terbesar yang tersisa dan paling murah ditutup". Masih terbuka.

---

## 6. Jalur setelah PA

Ditulis supaya keputusan hari ini tidak menutup pintunya, bukan supaya
dikerjakan sekarang.

**Kemandirian dari layanan pihak ketiga.** L8 baru termitigasi separuh: narasi
sudah bisa lokal lewat Ollama (`gpt-oss:20b`), tapi **embedding retrieval masih
Gemini**. Untuk produk, ketergantungan ini masalah biaya dan ketersediaan;
untuk laporan, ia harus ditulis apa adanya dan tidak diklaim sebagai swa-inang
penuh. Jalan keluarnya: embedding lokal, lalu ukur ulang skor retrieval — bukan
diasumsikan setara.

**rPPG lewat webcam.** Sudah diriset (POS/CHROM, pyVHR). Menarik karena
menghapus kebutuhan perangkat keras sama sekali, artinya menghapus hambatan
adopsi terbesar. Tapi resolusinya 30 fps = 33 ms, lawan 1 ms chest strap, dan
Woelk dkk. melaporkan |Δ| SDNN 11,45 ± 14,34 ms. Itu bukan tingkat T1 — kalau
suatu saat dibangun, ia tingkat tersendiri di bawah T1, dan permukaan keluarannya
harus lebih sempit lagi.

**Sesi berulang dan tren antar-waktu.** Secara teknis ini yang paling diinginkan
pengguna. Tapi ia mengubah model privasi secara mendasar: menyimpan riwayat
fisiologis seseorang lintas waktu adalah kategori data yang berbeda dari
menampilkan satu sesi lalu melupakannya. **Jangan dibangun sebelum ada kebijakan
retensi dan penghapusan yang eksplisit.** Dan tren antar-waktu tetap harus
perbandingan orang dengan dirinya sendiri — Aturan Wajib #2 tidak melonggar
hanya karena sumbunya jadi waktu.

**Yang tidak akan pernah dibangun.** Ditulis supaya tidak perlu diperdebatkan
ulang tiap ada permintaan fitur: peringkat antar kandidat; ambang lulus/gagal
berbasis HRV; tampilan apa pun ke sisi perekrut; klaim diagnostik. Keempatnya
melanggar A3, Aturan Wajib #2, atau Aturan Wajib #4.

---

## 7. Ringkasan tindakan

Urut berdasarkan biaya kalau ditunda, bukan berdasarkan besar pekerjaannya.

| # | Tindakan | Gerbang | Kenapa sekarang |
|---|---|---|---|
| 1 | Uji RR HW9 | G1 | tenggat pihak lain, tidak bisa digeser |
| 2 | Putuskan durasi baseline | G2 | data subjek tidak bisa diulang |
| 3 | Ablasi HR-saja (#9) | — | menentukan apakah tingkat T1 jujur |
| 4 | Pisahkan lapisan di kontrak API (A6) | G4 | murah sekarang, mahal setelah tim web mulai |
| 5 | Pintu masuk interval RR | G3 | prasyarat seluruh jalur Bluetooth |
| 6 | Perbaiki layar hasil (A8–A16) | G5 | sedang dikerjakan, tinggal dikunci |
| 7 | Kunci versi pustaka | G6 | paling murah dari semuanya |
| 8 | Pilot 1–2 subjek | G3 | sebelum pengumpulan penuh |

---

## 8. Yang tidak dibahas ulang

K1–K17 di `BACKLOG.md` tetap berlaku dan tidak dibuka lagi oleh dokumen ini.
Dokumen ini menambah A1–A16 dan G1–G6; kalau ada yang bertabrakan dengan K, yang
K menang, dan tabrakannya dicatat sebagai temuan.

Satu penajaman yang perlu dicatat: **A6 memperkuat K4**, tidak menggantikannya.
K4 menetapkan keluaran dua lapis. A6 memindahkan penegakannya dari klien ke
bentuk respons — supaya K4 tetap berlaku waktu frontend-nya ditulis orang yang
belum pernah membaca `BACKLOG.md`.
