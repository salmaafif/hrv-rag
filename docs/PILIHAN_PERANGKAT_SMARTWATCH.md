# Perangkat mana yang bisa dipakai, dan mengapa

Kesimpulan singkat: batasannya bukan Web Bluetooth. Batasannya adalah apakah jam
tangan mau **menyiarkan Heart Rate Service 0x180D**. Kalau ia menyiarkan,
pipeline akuisisi yang sudah berjalan menerimanya tanpa perubahan kode sama
sekali, karena dari sisi browser ia tidak berbeda dari HW9.

## Tiga golongan perangkat

**Menyiarkan sebagai fitur bawaan.** Banyak jam Garmin punya menu Broadcast
Heart Rate, dan Garmin menyatakan siaran Bluetooth-nya memang ditujukan untuk
aplikasi pihak ketiga, dengan ANT+ ikut menyala otomatis. Amazfit menambahkan
Heart Rate Push sejak Zepp OS 3.0, dan pihak ketiga menggambarkannya sebagai
perilaku monitor detak jantung Bluetooth standar, sehingga penerima mana pun
bisa membacanya. Model yang disebut mendukung antara lain Balance, Balance 2,
Active, Active 2, GTR 4, GTS 4, T-Rex Ultra, T-Rex 3, dan Bip 6. Zepp OS 2.x ke
bawah tidak.

**Tidak menyiarkan, tapi bisa dipaksa.** Samsung Galaxy Watch dan Wear OS pada
umumnya tidak punya fitur ini secara bawaan. Ada aplikasi di jam tangan seperti
Heart for Bluetooth yang mengubahnya menjadi pemancar 0x180D, dan setelah itu
browser melihatnya seperti chest strap biasa. Sumber pendukung yang kami baca
menyebut aplikasi semacam itu agak rewel dan mensyaratkan jam tangannya tidak
tidur. Cocok untuk uji coba, bukan untuk dipakai penguji sungguhan.

**Tidak mungkin.** Apple Watch tidak menyiarkan dan tidak ada aplikasi pihak
ketiga yang bisa membuatnya menyiarkan. Jalur Android pun tidak menolong.

## Dua catatan yang mengubah keputusan

**Siaran hampir selalu hanya bpm.** Bendera bit 4 pada paket 0x180D menandakan
ada tidaknya RR interval. Kalau jam tangan tidak menyalakannya, RMSSD tidak bisa
dihitung, dan itu berarti pemulihan serta kuadran Ketahanan hilang dari kartu
hasil. Tabel anggaran galat di `HASIL_SIMULASI_SMARTWATCH.md` berlaku persis
untuk keadaan itu. Halaman `uji-siaran-hr.html` memeriksa bendera ini dalam
hitungan detik, jadi pertanyaan ini tidak perlu ditebak untuk perangkat mana pun.

**Sebagian model hanya menyiarkan selama mode olahraga aktif.** Untuk sesi
wawancara yang berlangsung dua puluh menit sambil duduk, ini harus diuji dulu,
bukan diasumsikan. Kalau jam tangan berhenti menyiarkan ketika mode olahraga
dimatikan, penggunanya harus diminta menyalakan mode olahraga sebelum sesi, dan
itu perlu masuk ke instruksi di layar.

## Kalau memang harus beli

Pilihan berisiko paling rendah adalah Amazfit dengan Zepp OS 3.0 ke atas, karena
siarannya fitur resmi pabrikan dan bukan tambalan pihak ketiga. Bip 6 adalah
yang paling murah di daftar yang mendukung. Garmin lebih mahal tetapi fitur
siarannya paling lama ada dan paling terdokumentasi.

Yang perlu diperiksa sebelum membayar, dalam urutan ini: apakah modelnya ada di
daftar yang mendukung siaran, apakah versi Zepp OS-nya 3.0 ke atas, dan apakah
siarannya jalan di luar mode olahraga. Ketiganya bisa dicek di toko dengan
membuka `uji-siaran-hr.html` dari ponsel.

## Jalur berbeda yang layak disebut ke dosen

Samsung Health Sensor SDK memberi IBI secara kontinu di Galaxy Watch4 ke atas.
Itu satu-satunya jalur konsumen yang mengembalikan RMSSD, jadi secara akademis
paling menarik. Ongkosnya adalah aplikasi Wear OS yang harus dibangun dan
dipasang, plus jalur pengiriman dari jam ke ponsel ke server. Itu berminggu-minggu
pekerjaan, dan tidak ada gunanya dimulai sebelum langkah murah di atas terbukti
gagal.

## Sumber

- Garmin, Can Garmin Wearables Broadcast Heart Rate Data?
  https://support.garmin.com/en-US/?faq=Zj1947s6pqAHzBCAhLhrC9
- HypeRate, Amazfit Heart Rate Push: Live Bluetooth Heart Rate Streaming with Zepp OS
  https://blog.hyperate.io/post/amazfit-heart-rate-push-live-bluetooth-heart-rate-streaming-with-zepp-os-hyperate-compatible/
- Amazfit Support, Which devices are supported by the heart rate broadcast function
  https://support.amazfit.com/us/amazfit_helio_strap/docs/ZRrmdW46GoiwizxBLUacJ6XQn4d
- Cadence, Can I use my Samsung Galaxy or WearOS watch for heart rate readings?
  https://getcadence.app/support/can-i-use-my-samsung-galaxy-or-wearos-watch-for-heart-rate-readings/
