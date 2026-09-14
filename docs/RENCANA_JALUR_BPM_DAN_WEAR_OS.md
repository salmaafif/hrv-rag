# Rencana jalur bpm dan aplikasi Wear OS

Dokumen kerja untuk dikerjakan di Claude Code. Isinya keputusan yang sudah
diambil, urutan pengerjaan, daftar tempat yang bisa bocor, dan mitigasinya.
Tidak ada kode di sini. Yang ada adalah hal-hal yang kalau dilewatkan akan
menghasilkan laporan lengkap yang menceritakan hal yang salah.

Garis dasar saat ini: `hrv-rag` dijalankan ulang di lingkungan bersih, 215 tes
lewat semua. Jadi setiap kegagalan setelah ini adalah akibat perubahan, bukan
warisan.

Diagram alurnya ada di `docs/images/alur-web.svg` dan
`docs/images/alur-android.svg`, sumber Mermaid-nya di `.mmd` sebelahnya.

## Jalur bpm melayani web DAN Android, bukan hanya Android

Ini bingkai yang paling mudah salah dibaca, jadi disebut paling depan.

Sambungkan Garmin atau Amazfit yang sedang menyiarkan ke halaman akuisisi hari
ini, dan ia akan **tersambung lalu tidak menghasilkan apa-apa**. Siaran 0x180D
dari jam tangan hanya membawa bpm, sedangkan `submission.ts` membatalkan
kiriman saat `rrIntervals.length === 0`, dan kandidat mendapat pesan "aliran
denyutnya kosong saat sesi ditutup".

Jadi yang menghalangi smartwatch bukan Web Bluetooth dan bukan jam tangannya.
Yang menghalangi adalah pipeline kita sendiri, yang sampai hari ini hanya tahu
RR interval. Itu kode milik sendiri, bukan batas fisika, dan tahap satu sampai
tiga di bawah ada untuk menghapusnya.

Konsekuensinya: **begitu tahap tiga selesai, jam tangan yang menyiarkan langsung
jalan lewat web tanpa satu baris kode Android.** Tahap empat hanya menambah jam
tangan yang menolak menyiarkan, yaitu Galaxy Watch dan kebanyakan Wear OS. Kalau
perangkat yang dipakai boleh Amazfit atau Garmin, tahap empat bisa tidak
dikerjakan sama sekali.

## Dua tier, satu jalur kode, keputusan diambil dari rekaman

Sistem tidak memilih perangkat, ia membaca apa yang perangkat itu berikan.
Kalau RR interval ada, semuanya berjalan seperti sekarang. Kalau tidak ada,
sesi itu turun ke tier detak jantung. Satu pipeline, satu aturan beku, yang
berbeda hanya fitur mana yang punya suara.

**Diputuskan di akhir, bukan saat tersambung.** Bendera bit 4 bisa menyala di
sebagian paket saja, dan perangkat yang mulai bersih bisa memburuk di tengah
sesi ketika orangnya bergerak atau talinya longgar. Tier yang dikunci di detik
pertama membuat sesi yang kehilangan RR di menit kelima tetap dilaporkan sebagai
tier penuh, dengan separuh denyut yang tidak pernah ada.

**Tempat keputusannya sudah ada: `signal_fitness.assess_signal`.** Fungsi itu
ditulis persis untuk menjawab apakah RMSSD sebuah rekaman layak diberi suara,
dan docstring-nya sudah berargumen bahwa penilaiannya harus per sinyal dan bukan
per kelas perangkat. Tier smartwatch karena itu bukan konsep baru, melainkan
satu alasan tambahan di fungsi yang sama: perangkatnya tidak pernah mengirim
interval antar denyut. Konsekuensinya tidak ada percabangan baru di hilir,
karena `Prepared.scoring_reactivity` sudah tahu cara menanggapi
`rmssd_trusted` yang false.

**Kiriman membawa keduanya.** Aplikasi web mengirim `rrMs` apa adanya, sampel
bpm, dan angka cakupan RR. Ukurannya kecil, sesi dua puluh menit pada 1 Hz hanya
seribu dua ratus angka. Yang dibeli dengan itu: keputusan tier dibuat di modul
yang beku dan tertes, bukan di peramban, dan arsip lama bisa dinilai ulang kalau
ambangnya berubah.

**Kasus tengah tidak dicampur.** Kalau RR hanya ada sebagian, godaannya
menghitung RMSSD di jendela yang denyutnya cukup saja. Jangan. Sensor optik
paling buruk justru ketika orangnya berbicara, jadi pola yang paling mungkin
adalah RR lengkap selama menit tenang dan hilang selama menjawab. Membandingkan
RMSSD istirahat yang nyata dengan RMSSD menjawab yang dihitung dari beberapa
detik bersih menghasilkan bias yang arahnya tidak diketahui. Satu ambang
cakupan, di bawahnya seluruh sesi turun ke tier detak jantung.

**Jalur HW9 tidak berubah sedikit pun.** RR lengkap berarti aturan beku yang
sama dan angka yang sama, sehingga tidak ada risiko regresi terhadap hasil yang
sudah masuk laporan. Itu juga yang membuat perubahan ini aman dikerjakan dekat
tenggat.

## Keputusan yang sudah diambil

Jam tangan mengirim langsung ke backend, tanpa aplikasi pendamping di ponsel.
Versi pertama memakai sensor Wear OS biasa, `Sensor.TYPE_HEART_RATE`, jadi
hanya bpm. Jalur Samsung Health Sensor SDK yang memberi IBI ditunda, bukan
dibatalkan. Backend dikerjakan lebih dulu, lengkap dengan tes, baru aplikasi
jam tangannya.

Di jalur Android yang diolah hanya detak jantung. Bukan hanya RMSSD yang
ditiadakan, melainkan seluruh fitur variabilitas termasuk SDNN, pNN50, dan
ranah frekuensi. Ini keputusan yang menyederhanakan, asal diterjemahkan
sebagai daftar putih dan bukan sebagai daftar hitam; lihat bagian berikutnya.

Layanan HRV tetap proses terpisah dari NestJS. Alasannya tertulis di
`pyproject.toml` sendiri: `hrv_rag` harus bisa dijalankan, diuji, dan dikutip
tanpa FastAPI di dekatnya, dan degradasi anggun di `HeartRateService` baru
benar secara fisik kalau prosesnya memang terpisah.

## Bahaya utama, disebut lebih dulu

Seluruh rantai karirlink sampai hrv-service berjalan di atas RR interval. Jam
Wear OS biasa tidak punya RR. Godaan terbesarnya adalah menyulap bpm jadi RR
dengan `60000/bpm` diulang-ulang. Jangan.

Deret seperti itu semua selisihnya nol, sehingga RMSSD-nya tepat nol, deltanya
minus seratus persen terhadap baseline, `_score_feature` memberinya dua poin
penuh, dan setiap kandidat akan diberi tahu bahwa dia sangat tertekan. Tidak
ada error, tidak ada peringatan, laporannya lengkap dan meyakinkan. Ini
kegagalan paling mahal yang mungkin terjadi di proyek ini, karena ia terlihat
seperti keberhasilan.

Rekonstruksi denyut tetap dipakai, tapi dengan syarat yang tidak boleh
ditawar: setiap fitur variabilitas **dihapus**, bukan diisi NaN.

## Mengapa tetap merekonstruksi denyut

Ada dua cara memasukkan bpm ke pipeline.

Cara pertama, bangun jalur jendela sendiri khusus bpm. Kelihatan bersih, tapi
artinya menyalin ulang panjang jendela, lompatan, `min_beats`, gerbang mutu,
`split_baseline_and_task`, dan aritmetika `question_shift_sec`. Itu persis
kumpulan kode yang sudah dua kali menggigitmu, 28 Agustus soal jam dan 1
September soal jendela. Dua salinan berarti dua tempat untuk salah dengan cara
yang sama halusnya.

Cara kedua, rekonstruksi deret denyut dari kurva bpm dengan menahan tiap
sampel sampai sampel berikutnya, lalu memancarkan denyut tiap `60/bpm` detik.
Hasilnya deret interval yang durasi kumulatifnya benar dan rata-rata per
jendelanya mendekati rata-rata bpm sebenarnya. Seluruh mesin yang sudah
tervalidasi jalan tanpa diubah.

Ambil cara kedua. Harganya adalah kewajiban memblokir setiap angka
variabilitas, dan itu harga yang bisa dibayar sekali di satu tempat.

## Daftar putih satu fitur, bukan daftar hitam panjang

Keputusan "di Android olah detak jantung saja, tidak perlu RMSSD maupun yang
lain" menyederhanakan pekerjaan ini lebih banyak daripada kelihatannya, asal
diterjemahkan dengan benar.

Cara yang salah adalah menyebutkan satu per satu fitur yang harus diblokir.
Daftar itu panjang, mudah kurang satu, dan akan kurang satu lagi setiap kali
ada fitur baru ditambahkan tahun depan.

Cara yang benar adalah satu konstanta berisi fitur yang BOLEH ada, dan jalur
bpm membuang seluruh sisanya dari `baseline.values`. Isinya cukup satu:
`mean_hr`.

Bukan dua. `mean_rr` memang bukan angka variabilitas dan secara aritmetika
cuma kebalikan dari `mean_hr`, tapi melaporkannya mengundang orang menyangka
kita punya denyut per denyut, padahal denyutnya hasil rekonstruksi.
Menyimpannya tidak menambah informasi apa pun dan menambah satu cara untuk
salah paham.

Dengan daftar putih itu, semua yang berbasis variabilitas lenyap sendirinya
dalam satu langkah: RMSSD, SDNN, pNN50, dan seluruh fitur ranah frekuensi LF,
HF, dan LF/HF. Yang terakhir ini penting dan mudah terlewat, karena
`extract_features` tetap menghitung LF dan HF dari denyut rekonstruksi dan
angkanya akan terlihat wajar padahal tidak berarti apa-apa. Daftar putih
menahan semuanya di satu tempat.

Fitur-fitur itu tetap menjadi kolom di `task_table`, hanya tidak pernah jadi
reaktivitas karena setiap pembacanya menyusun daftar fiturnya dari
`baseline.values`. Konsekuensinya satu aturan yang perlu dipegang ke depan:
jangan pernah menulis kode yang memutari kolom `task_table` secara langsung.
Yang menentukan apa yang diukur adalah `baseline.values`, dan hanya itu.

## Kenapa dihapus, bukan diisi NaN

Kalau fitur variabilitas dihapus dari `baseline.values`, tiga hal terjadi
sendirinya karena kode yang ada memang sudah menulisnya begitu.
`BaselineProfile.reactivity` hanya memutari `self.values`, jadi
`delta_pct_rmssd` tidak pernah lahir. `measure_question` menyusun
`feature_names` dari `baseline.values.keys()`, jadi ia tidak mencarinya.
`session_level` melakukan hal yang sama.

NaN akan tetap berbentuk angka. Angka bisa dibulatkan, dicetak, dan
dijumlahkan oleh kode yang ditulis enam bulan lagi oleh orang yang tidak tahu
asal-usulnya. Ketiadaan tidak bisa.

## Tempat-tempat yang akan bocor, satu per satu

Ini daftar periksa untuk Claude Code. Setiap baris adalah tempat yang, kalau
dibiarkan, mengeluarkan angka variabilitas palsu atau kalimat yang tidak benar.

**`baseline_block()` di `analysis.py`.** Menulis
`round(values.get("rmssd", nan), 2)`. Kalau kuncinya hilang, hasilnya NaN, dan
**NaN bukan JSON yang sah**. FastAPI akan mengirim token `NaN` telanjang yang
ditolak `JSON.parse` di peramban. Ini bug laten yang sudah ada sekarang,
terlepas dari jalur bpm, dan pantas diperbaiki sekalian. Lewatkan lewat
`_clean`.

**`assess_signal()`.** Kalau diberi denyut hasil rekonstruksi, ia akan
memeriksa sinyal yang terlalu bersih dan menyimpulkan `rmssd_trusted=True`.
Persis kebalikan dari kebenaran. Jalur bpm harus **melewati** fungsi ini dan
menyusun `SignalFitness` langsung dengan `rmssd_trusted=False` dan alasan yang
menyebut sebabnya, yaitu perangkatnya melaporkan bpm dan bukan interval antar
denyut. Angka-angka turunannya, `quantization_step_ms` dan kawan-kawan,
dikosongkan, bukan dihitung dari denyut palsu.

**Alasan pemulihan di `measure_question`.** Dengan rmssd hilang, penjaga
`key in baseline.values` membuat pemulihan tidak terhitung. Itu benar. Tapi
`RecoveryResult` yang tersisa masih membawa alasan awalnya, "no quiet gap
followed this question", dan itu **bohong** untuk sesi yang jedanya ada.
Alasannya harus diganti jadi pernyataan yang benar, bahwa perangkatnya tidak
memberi bahan untuk menghitung pemulihan.

**`most_triggering_question`.** Daftar `reactivities` hanya diisi kalau
`d_rmssd == d_rmssd`. Dengan bpm daftarnya kosong, jadi tidak ada pertanyaan
yang dinobatkan paling memicu dan `median_reactivity_pct` jadi null. Kartu
hasil kehilangan bintang di grafiknya.

DIPUTUSKAN: jatuhkan ke `delta_pct_mean_hr` saat RMSSD tidak ada. Detak
jantung memang satu-satunya yang diukur di tier ini, dan menamai pertanyaan
dengan lonjakan detak terbesar adalah pernyataan yang jujur. Syaratnya kartu
hasil menyebut dasarnya, karena bintang yang dasarnya berubah diam-diam lebih
buruk daripada bintang yang hilang.

**`resilience_quadrant`.** Dengan `median_reactivity` NaN ia mengembalikan
None, jadi kuadran Ketahanan jadi null dengan sendirinya. Tidak perlu diapa-apakan,
tapi perlu ditesi supaya tetap begitu.

**`rank_by_reactivity` di `dynamics.py`.** Melempar `KeyError` kalau kolom
`delta_pct_rmssd` tidak ada. Periksa apakah ia pernah dipanggil di jalur
layanan. Kalau hanya dipakai skrip offline, cukup dicatat. Kalau ternyata ada
di jalur layanan, ia harus diberi jalan keluar yang eksplisit.

**Narasi V1, `write_timeline_narrative`.** Barisnya
`reactivity = {"delta_pct_rmssd": float(median)}` mengasumsikan median
reaktivitas selalu RMSSD. Di jalur bpm mediannya None, jadi fungsinya pulang
dengan "nothing measurable to describe" dan rekaman tanpa struktur pertanyaan
kehilangan narasinya sama sekali. Karirlink memakai V3, jadi dampaknya kecil,
tapi jangan sampai ketahuan saat sidang tanpa pernah disebut.

**Prompt ke LLM.** Model tidak boleh diam-diam mengisi kekosongan variabilitas
dengan kalimat yang enak dibaca. Pola `note_for_model` yang sudah ada di
`baseline.py` sudah tepat bentuknya; tambahkan satu kalimat yang menyatakan
variabilitas tidak diukur pada rekaman ini. Penjaga angka-karangan yang sudah
ada tetap jadi jaring terakhir, bukan pertahanan pertama.

**Asal-usul di respons.** Tambahkan penanda sumber, misalnya `"source"`
bernilai `bpm` atau `beat_intervals`. Tanpa itu, dua pengukuran yang sangat
berbeda tersimpan di arsip dengan bentuk yang sama persis, dan enam bulan lagi
tidak ada cara membedakannya.

## Satu tes yang menangkap seluruh kelas bug ini

Serialisasi seluruh badan respons dengan `json.dumps(..., allow_nan=False)`.
Kalau ada satu NaN yang lolos ke mana pun di dalam payload, tes ini gagal.
Satu baris, menutup semua kebocoran sekaligus, dan tetap berguna lama setelah
jalur bpm selesai.

Tes lainnya yang perlu ada: setiap pertanyaan, `session_level`, dan timeline
mengembalikan `delta_rmssd_pct` bernilai null; `baseline_block()["rmssd_ms"]`
null; `signal_fitness.rmssd_trusted` false dengan alasan yang menyebut kelas
perangkatnya; `resilience` null dan pemulihan tidak terhitung dengan alasan
yang benar; rata-rata detak per jendela hasil rekonstruksi sama dengan
rata-rata aritmetik sampel bpm dalam toleransi satu bpm.

## Yang terlewat kalau hanya melihat Python

**`submission.ts` menghitung panjang rekaman dari jumlah interval.**
`recordedBeforeFirstSec` diturunkan dari `anchor.offsetSec + firstStartSec`,
dan `offsetSec` sendiri berasal dari jumlah RR dibagi seribu. Untuk jam
tangan, panjang rekaman harus datang dari cap waktu sampel bpm. Kalau tidak,
`baselineMinutes` dihitung dari bahan yang salah, dan seluruh penggeseran jam
ikut salah. Ini bug yang sudah menunggu, bukan kemungkinan.

**Siapa yang merakit kiriman.** Kalau jam tangan mengirim langsung ke backend,
jam tangan tidak tahu linimasa pertanyaan. Linimasa itu dipegang aplikasi web.
Jadi bentuknya bukan jam tangan mengirim kiriman lengkap, melainkan jam tangan
mengalirkan sampel selama sesi, backend menahannya dengan kunci kode
pemasangan, dan saat sesi ditutup aplikasi web mengirim linimasanya lalu
backend menggabungkan keduanya.

Konsekuensinya backend berubah lebih banyak daripada kelihatan di awal. Perlu
tempat menahan sampel, entah tabel Prisma atau penyimpanan sementara, dan
perlu aturan retensi. Data biometrik yang ditahan sebelum sesi ditutup adalah
pemrosesan sementara, bukan pengarsipan, tapi tetap harus punya aturan
penghapusan yang tertulis: terhapus saat sesi ditutup, dan punya batas waktu
untuk sampel yatim dari sesi yang tidak pernah selesai. Jangan digabung dengan
`storeConsented`, itu soal yang berbeda dan menggabungkannya akan membuat
keduanya sulit dijelaskan.

## Penyelarasan jam, risiko terbesar kedua

Ini kelas bug yang sudah dua kali memakan sesi uji. Jam tangan punya jamnya
sendiri, aplikasi web punya jamnya sendiri, dan `at_sec` yang dikirim jam
tangan harus bisa diterjemahkan ke jam sesi.

Bentuk paling sederhana yang benar: jam tangan mengirim detik monotonik sejak
alirannya dimulai, backend mencatat waktu dinding saat paket pertama tiba, dan
patokan sesi di aplikasi web juga waktu dinding. Sisa galatnya tinggal satu
lompatan jaringan, puluhan milidetik, yang tidak berarti apa-apa terhadap
jendela enam puluh detik.

Yang harus dihindari: memakai cap waktu jam tangan secara langsung sebagai
waktu sesi. Jam di arloji bisa meleset menit-menitan dan tidak ada yang akan
menyadarinya sampai laporannya keluar.

`test_session_clock.py` sudah punya bentuk tes yang tepat untuk ini. Tiru
polanya dengan offset sintetis.

## Aplikasi Wear OS, hal yang menentukan berhasil atau tidak

Pemasangannya lewat ADB, bukan Play Store. Di jam tangan, Settings lalu About
lalu ketuk Build number tujuh kali, nyalakan ADB debugging dan Debug over
Wi-Fi, lalu `adb connect` dari laptop. Setelah itu Android Studio
memperlakukannya seperti perangkat biasa.

Yang paling sering merusak percobaan pertama adalah jam tangan yang tidur.
Pembacaan sensor harus berjalan di foreground service dengan notifikasi
berjalan, bukan di activity biasa. Tanpa itu alirannya berhenti begitu layar
mati dan datanya bolong di tengah sesi.

Izin yang dibutuhkan `BODY_SENSORS`. Jaringan dari jam tangan diandalkan lewat
Wi-Fi; saat jam tangan hanya tertambat Bluetooth ke ponsel, akses jaringannya
tidak dijamin. Untuk demo sidang ini bukan masalah karena kandidat duduk di
depan laptop dan jam tangannya bisa disambungkan ke Wi-Fi yang sama, tapi itu
asumsi yang harus ditulis, bukan didiamkan.

Kode pemasangan enam digit ditampilkan di halaman web dan diketik sekali di
jam tangan. Layar pengetikan di arloji sempit, jadi rancang dengan angka besar
dan tanpa keyboard penuh.

Backend harus melaporkan cakupan, bukan menambal lubang. Kalau alirannya putus
tiga puluh detik, yang benar adalah menyebutnya tidak terukur, bukan
menginterpolasinya. Kolom `coverage` yang sudah ada di respons adalah tempat
yang tepat.

## Di repo mana, di branch mana

Dua repo, dan batasnya sudah ada sejak awal. Semua yang ada di `src/hrv_rag`
dan `backend/hrv_api` dikerjakan di **hrv-rag**. Semua yang ada di `apps/web`,
`apps/backend`, dan aplikasi jam tangan dikerjakan di **karirlink**.
`apps/hrv-service` tidak pernah disunting dengan tangan; ia hasil
`scripts/export_service.py`.

Aplikasi Wear OS masuk monorepo karirlink sebagai `apps/wear-app`, di branch,
bukan fork. Ongkosnya nol untuk tim: karirlink tidak punya build tooling di
akar, tidak ada workspace npm, dan `apps/*` masing-masing berdiri sendiri, jadi
folder Gradle baru tidak menyentuh perkakas siapa pun. Android Studio dibuka
langsung di `apps/wear-app`, bukan di akar monorepo.

Yang perlu ditambahkan ke `.gitignore`: `.gradle/`, `local.properties`,
`*.apk`, `captures/`. `build/` dan `.idea/` sudah ada.

Urutan branch-nya mengikuti urutan tahap. Branch di hrv-rag lebih dulu sampai
pytest hijau, lalu ekspor, lalu branch di karirlink yang isinya perubahan
`apps/web` dan `apps/backend` plus hasil ekspor. Sebutkan di pesan commit bahwa
isi `apps/hrv-service` adalah hasil ekspor dari commit hrv-rag tertentu;
PROVENANCE.md sudah mencantumkan nomornya.

Dua hal yang sudah ada di `CLAUDE.md` karirlink dan sebaiknya dipakai, bukan
ditemukan ulang. Pertama, kontraknya sudah punya field `tier` yang menentukan
panel mana yang boleh dirender, jadi tier detak jantung adalah nilai baru pada
field yang sudah ada, bukan konsep baru. Kedua, aturan tampilan sudah menyatakan
`recovery_pct: null` dirender "belum terukur" dan bukan 0%, yang persis keadaan
tier jam tangan. Periksa nilai `tier` yang sudah didefinisikan di
`docs/module-design/rancangan-rag-hrv.md` sebelum menambah nilai baru.

Satu hal yang perlu diklarifikasi sebelum menaruh endpoint aliran. `CLAUDE.md`
menyatakan modul HRV dipanggil server-ke-server lewat AI Gateway, sedangkan kode
yang berjalan memanggilnya langsung dari NestJS lewat `HrvModuleService`. Salah
satunya sudah usang. Penampungan sampel dan kode pemasangan jelas milik NestJS
karena butuh Prisma dan pemeriksaan kepemilikan sesi, tapi jalur panggilan ke
hrv-service sebaiknya diselaraskan dulu supaya dokumen dan kode tidak makin
berbeda.

## Urutan pengerjaan

Tahap satu, hrv-rag. Skema masuk yang baru, rekonstruksi denyut, penghapusan
fitur variabilitas, penambalan semua titik bocor di daftar di atas, dan
tesnya. Bisa didemokan sendiri lewat pytest tanpa menyentuh karirlink sama
sekali. Setelah hijau, ekspor ulang ke `apps/hrv-service` dengan
`scripts/export_service.py`, jangan pernah menyunting salinannya.

Tahap dua, gerbang NestJS. Field baru di `SubmitHeartRateDto`, penerjemahan
snake_case di `HrvModuleService`, dan baris log yang menghitung interval harus
diganti menghitung sampel. Tesnya satu kiriman bpm menghasilkan satu baris
tersimpan.

Tahap tiga, penampungan sampel dan kode pemasangan. Endpoint penerima aliran,
tempat menahan, aturan retensi, dan penggabungan dengan linimasa saat sesi
ditutup.

Tahap empat, aplikasi Wear OS. Paling akhir, karena sampai tahap tiga selesai
tidak ada tempat untuk mengirim datanya, dan menguji aplikasi jam tangan
tanpa penerima berarti menguji dua hal yang belum pasti sekaligus. Tahap ini
juga OPSIONAL: ia hanya dibutuhkan untuk jam tangan yang menolak menyiarkan.

Rute termurah menuju demo smartwatch yang benar-benar jalan adalah berhenti di
tahap tiga, dengan jam tangan yang menyiarkan. Tanpa Android, tanpa ADB, tanpa
developer mode, dan tanpa persetujuan pabrikan mana pun.

Tiap tahap bisa ditunjukkan ke dosen sendiri-sendiri. Itu disengaja: kalau
waktunya habis di tengah, yang sudah jadi tetap bisa dipertanggungjawabkan.

## Utang yang sudah ada dan sebaiknya ditutup sekalian

`scripts/export_service.py` belum punya mode pemeriksaan. Tambahkan `--check`
yang mengekspor ke folder sementara lalu membandingkan dengan salinan di
karirlink dan keluar dengan kode error kalau berbeda. Salinan itu pernah
menyimpang lima kali tanpa ketahuan, dan satu perintah sebelum demo menutup
seluruh kelas masalah itu.

Komentar di `settings.py` yang berbunyi bahwa nilai ambangnya berasal dari
literatur masih perlu diperbaiki, karena nilainya berasal dari kalibrasi grid
pada lima subjek pengembangan, bukan dari jurnal. Itu kalimat yang akan
ditanya penguji.

## Yang harus ditulis di laporan, apa pun hasilnya

Tier jam tangan adalah tier detak jantung saja. RMSSD tidak diukur, bukan
diukur dengan buruk. Akibatnya pemulihan dan kuadran Ketahanan tidak ada, dan
itu ditampilkan sebagai tidak terukur, bukan sebagai nol.

Angka ketelitiannya sudah diukur, bukan ditebak: pada sepuluh subjek WESAD
tersegel dengan aturan beku, menahan RMSSD memberi macro-F1 0.871, dan dengan
galat perangkat yang wajar untuk jam tangan konsumen angkanya turun ke kisaran
0.79 sampai 0.83. Lantai pengklasifikasi sepele di data yang sama 0.401.

Mode developer di Health Sensor Service, kalau jalur Samsung kelak dipakai,
adalah batasan distribusi yang harus disebut, bukan disembunyikan.
