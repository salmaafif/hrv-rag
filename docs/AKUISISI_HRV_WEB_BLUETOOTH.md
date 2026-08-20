# Akuisisi HRV Live via Web Bluetooth — Riset & Rancangan

Tugas Akhir Salma Afifa Azis (3123600017) — Teknik Informatika PENS
Disusun 10 Agustus 2026 · **Direvisi 10 Agustus 2026 (rev-2)**

> Melengkapi `BACKLOG.md` (apa yang dikerjakan) dan `CLAUDE.md` (aturan desain).
> Isinya: riset perangkat keras, temuan literatur, rancangan alur akuisisi live, dan
> **posisi modalitas PPG di dalam penelitian ini**.
>
> ID keputusan memakai awalan `HW`. ID keterbatasan melanjutkan seri `L` (BACKLOG berhenti di L12).
>
> **Perubahan pada rev-2:** HW2 dan HW3 dibalik — PPG kini **masuk cakupan penelitian**,
> bukan pengembangan lanjutan, dan perangkat uji pertama adalah armband HW9.
> Ditambahkan §1.1 (rantai konsep), §4 (modalitas PPG), §6 (kriteria uji terkunci),
> serta koreksi penalaran tentang daftar perangkat HypeRate (§3.2).

---

## 0. Ringkasan Keputusan

| # | Keputusan | Alasan singkat |
|---|---|---|
| HW1 | Akuisisi lewat **Web Bluetooth**, bukan aplikasi native atau SDK vendor | Tanpa instalasi, lintas OS, netral-vendor. Membaca profil standar Bluetooth SIG |
| HW2 | **Perangkat uji pertama: Coospo HW9** (armband PPG, Rp 850.000). Chest strap **H808S** (Rp 539.000) sebagai jalur mundur bila HW9 gugur | Anggaran Rp 1,5 jt memuat keduanya (total Rp 1.389.000). Urutan ini menguji hipotesis yang belum dijawab siapa pun lebih dulu |
| HW3 | **PPG masuk cakupan penelitian ini**, bukan pengembangan lanjutan | Proposal sudah menjanjikan sistem dua cabang (Gambar 3.1). Menurunkannya ke future work justru menuntut revisi proposal |
| HW4 | **Smartwatch dicoret** sepenuhnya | Dua sebab bebas: mayoritas tidak bisa jadi BLE peripheral; PPG pergelangan meratakan RR |
| HW5 | **Tiga gerbang mutu** sebelum & selama sesi (perangkat → adaptasi → baseline) | Baseline adalah titik kegagalan tunggal; kegagalannya senyap tanpa gerbang |
| HW6 | Klaim ilmiah dilaporkan **biner** (tervalidasi), tampilan UI **tiga tingkat** (indikatif) | Menyelesaikan T2c.10/L12 tanpa mengorbankan kejujuran maupun kegunaan |
| HW7 | Target platform: **Chrome/Edge desktop + Chrome Android**. iOS di luar cakupan | Web Bluetooth tidak tersedia di Safari/iOS maupun Firefox |
| HW8 | Deteksi **RR sintetis** wajib ada di gerbang perangkat | Sebagian alat mengirim `60000/HR`, bukan jarak antar-denyut sungguhan — gagal senyap |
| HW9 | **Coospo HW706 dan LIVLOV V9 dicoret** | Spesifikasi resmi Coospo: HW706 **"HRV Support: No"** — tidak mengirim field RR. LIVLOV V9 belum terverifikasi (lihat koreksi §3.2) |
| HW10 | Cakupan tingkat produk (satu modalitas atau dua tingkat) **ditentukan oleh hasil uji perangkat**, bukan diputuskan di muka | Keputusan produk menunggu bukti, bukan asumsi |

---

## 1. Prinsip Teknis

### 1.1 Rantai konsep: PPG ≠ RR-interval ≠ HRV

Tiga istilah yang sering tertukar padahal merupakan **tiga tahap berbeda dalam satu rantai**:

- **PPG / ECG** = *cara* alat mengukur
- **RR-interval** = *apa* yang keluar dari alat lewat Bluetooth
- **HRV** = *apa* yang dihitung kode dari deret RR itu

Alur di dalam HW9: LED hijau menyinari kulit → volume darah naik saat sistol → pantulan cahaya
berubah → gelombang PPG terbentuk **di dalam perangkat** → firmware mendeteksi puncak →
menghitung jarak antar puncak → **deret RR (ms)** dikirim lewat BLE. Gelombang PPG mentahnya
**tidak pernah keluar** dari alat.

| Tahap | HW9 (armband) | H808S (chest strap) |
|---|---|---|
| Cara mengukur | Cahaya (PPG) | Listrik (ECG) |
| Di dalam alat | Cari puncak gelombang cahaya | Cari puncak R |
| Dikirim via Bluetooth | **Deret RR (ms)** | **Deret RR (ms)** — sama |
| Dihitung kode | RMSSD, SDNN, … | RMSSD, SDNN, … — sama |

**Konsekuensi penting:** dua baris terakhir identik, sehingga pipeline dan kode Web Bluetooth
**tidak perlu diubah sama sekali** antar modalitas. Yang berbeda hanya dua baris pertama — dan
dari situlah seluruh perbedaan akurasi berasal.

**Analogi:** ECG seperti chip elektronik di sepatu pelari — sinyalnya tajam dan tepat. PPG seperti
berdiri di garis finis memegang stopwatch dan mengamati dengan mata — tetap menghasilkan daftar
waktu, tapi bisa meleset. Daftar yang meleset **tetap terlihat wajar** dan rumusnya tetap jalan;
yang salah adalah jawabannya. Untuk rata-rata kecepatan, meleset sedikit tertutup banyaknya data.
Untuk selisih antar dua pelari berurutan — persis yang diukur RMSSD — meleset sedikit langsung
merusak hasilnya.

**Catatan tentang label "HRV: Yes" pada spesifikasi:** itu **klaim ketersediaan data**, bukan klaim
akurasi. Artinya alat mengirim field RR sehingga HRV *bisa dihitung* — bukan bahwa hasilnya tepat.

### 1.2 Syarat mati: RR-interval, bukan bpm

Seluruh fitur HRV dihitung dari deret RR beat-to-beat. Detak jantung rata-rata tidak cukup.
Syarat nomor satu sebuah sensor bukan mereknya, melainkan apakah ia menyiarkan field RR.

### 1.3 Profil BLE

| Item | Nilai |
|---|---|
| Service | Heart Rate Service — UUID `0x180D` |
| Characteristic | Heart Rate Measurement — UUID `0x2A37`, mode notify |
| Flags byte | bit 0: format HR · bit 3 (`0x08`): Energy Expended · **bit 4 (`0x10`): RR hadir** |
| Satuan RR | 1/1024 detik → ms = `nilai / 1024 * 1000` |
| Resolusi | ±1 ms — Hilbel dkk. (2021): **lebih halus daripada banyak perangkat Holter** |
| Battery (opsional) | Service `0x180F`, characteristic `0x2A19` |

### 1.4 Parsing (JavaScript)

```js
const device = await navigator.bluetooth.requestDevice({
  filters: [{ services: ['heart_rate'] }],        // 0x180D — filter by SERVICE, bukan nama
  optionalServices: ['battery_service']
});
const server = await device.gatt.connect();
const svc    = await server.getPrimaryService('heart_rate');
const ch     = await svc.getCharacteristic('heart_rate_measurement'); // 0x2A37
await ch.startNotifications();

ch.addEventListener('characteristicvaluechanged', (e) => {
  const dv    = e.target.value;
  const flags = dv.getUint8(0);
  let   idx   = 1;
  const hr = (flags & 0x01) ? dv.getUint16(idx, true) : dv.getUint8(idx);
  idx += (flags & 0x01) ? 2 : 1;
  if (flags & 0x08) idx += 2;                 // lewati Energy Expended
  const rr = [];
  if (flags & 0x10) {                         // bit 4: RR hadir
    for (; idx + 1 < dv.byteLength; idx += 2) {
      rr.push(dv.getUint16(idx, true) / 1024 * 1000);   // -> ms
    }
  }
});
```

Satu paket dapat memuat lebih dari satu RR — loop di atas menanganinya.

**Web Bluetooth mendukung banyak perangkat sekaligus.** Panggil `requestDevice()` dua kali; tiap
perangkat punya koneksi GATT sendiri, tetapi keduanya dibaca **satu halaman dengan satu jam**.
Ini menghapus secara struktural kelas bug penjodohan yang membatalkan angka T6.4 versi lama
(selisih median 210 dtk, 74 dari 91 pasangan tidak bertumpang tindih).

### 1.5 Deteksi RR sintetis (HW8)

Sebagian perangkat menyalakan bit RR tetapi mengisinya dengan `60000 / HR`. Sistem tetap
"berjalan", angka tetap keluar, RMSSD **tidak bermakna**, dan tidak ada pesan galat.
Rutenberg (2026) menemukan ini pada monitor Decathlon.

Deret sintetis itu **mulus**, sehingga persentase outliernya justru rendah dan akan lolos
gerbang mutu berikutnya. Karena itu pemeriksaan ini harus dijalankan **sebelum** gerbang
outlier, bukan sesudahnya.

Tiga tanda, salah satu saja sudah cukup menghukum:

1. **Cocok dengan `60000 / hr_dilaporkan`.** Lebih dari 90% RR jatuh dalam 2 ms dari nilai itu.
   RR sungguhan hanya sesekali kebetulan sama dengan laju rata-rata.
2. **Deret nyaris datar.** Di bawah delapan nilai berbeda dalam satu blok berarti sensor rusak,
   apa pun penyebabnya.
3. **Jarak antar nilai melebar seiring RR².** Ini tanda yang menentukan, dan ia bekerja karena
   aritmetika, bukan karena ambang yang disetel. Alat yang mengirim `60000 / bpm` hanya bisa
   mengeluarkan nilai yang diizinkan bpm bulat, dan jaraknya **tidak seragam**: dua nilai
   bertetangga berjarak `60000/b − 60000/(b+1)`, yang tumbuh sebanding RR². Pada 110 bpm anak
   tangganya 5 ms, pada 69 bpm 12 ms. Alat berjam kasar tetapi jujur mengkuantisasi **waktu**,
   sehingga jaraknya sama di seluruh rentang dan korelasinya runtuh ke nol.

**Koreksi metode — 20 Agustus 2026.** Tanda ke-3 menggantikan aturan lama "nilai berbeda <
8% sampel". Aturan lama itu diam-diam mengandaikan resolusi ~1 ms sebagaimana disiratkan
field BLE, dan **menghukum rekaman HW9 yang sungguhan** (§3.3): 36 nilai berbeda dari 502
denyut, di bawah ambang `max(8; 40,2)`. Menghitung nilai berbeda mengukur **jam alat**, dan
jam bukan pertanyaannya. Tanda ke-3 mengukur **bentuk** jarak, yang memang pertanyaannya, dan
tidak peduli sekasar apa jamnya.

Tanda ke-1 sendirian juga tidak cukup: alat yang memalsukan RR dari bpm tetapi melaporkan bpm
yang sudah dihaluskan di paketnya akan lolos, karena hampir tidak ada RR yang jatuh dalam 2 ms.
Tanda ke-3 menangkapnya, sebab nilai palsunya tetap duduk di kisi bpm yang tidak seragam.

Pemisahan kedua populasi diukur, bukan ditebak. Korelasi jarak terhadap RR²: deret sungguhan
berhenti di sekitar **+0,32**, deret `60000/bpm` mulai dari **+0,97**. Ambang **0,7** duduk di
ruang kosong di antaranya. Minimum **60 denyut** sebelum putusan dikeluarkan — korelasi di atas
segelintir anak tangga hanyalah derau.

Implementasi: `classifyRrSource()` dan `bpmGridCorrelation()` di
`frontend/uji-protokol-hrv.logic.js`, dipakai bersama oleh halaman uji sensor dan halaman
protokol tiga blok agar keduanya tidak pernah memberi putusan berbeda untuk perangkat sama.

### 1.6 Kendala Web Bluetooth

| Aspek | Ketentuan |
|---|---|
| Browser | Chrome, Edge, Opera. **TIDAK**: Safari, Firefox |
| OS | Windows, macOS, Linux, ChromeOS, Android. **TIDAK**: iOS/iPadOS |
| HTTPS | Wajib `https://` atau `http://localhost`. `file://` diblokir |
| Gestur pengguna | `requestDevice()` hanya dari klik/tap |
| Mitigasi iOS | Bluefy (WebBLE) atau app native — di luar cakupan TA |

---

## 2. Temuan Literatur

### 2.1 Validitas chest strap — Protzen dkk. (2025)

*Universidad de León* — ECSS Rimini, Book of Abstracts hlm. 268. Versi jurnal di *IJSPP*:
"Limited Validity of the Low-Cost Coospo H808S…" (PMID 40615117).

16 pelari rekreasional (25±5 th), Polar H10 **dan** Coospo H808S bersamaan, posisi strap diacak,
direkam via **HRV Logger**, dianalisis **Kubios** (mentah & tersaring), 3 kondisi × 5 menit
(4 menit terakhir dianalisis), ICC + Bland-Altman.

| Kondisi | RR | RMSSD | HR |
|---|---|---|---|
| Telentang (pra-saring) | > 0,967 | > 0,967 | > 0,967 |
| Telentang (pasca-saring) | 0,917 | 0,930 | 0,911 |
| **Duduk (pra & pasca)** | **> 0,990** | **> 0,990** | **> 0,990** |
| Berlari (pra-saring) | 0,930 | **−0,244** (+17,6 ms; LoA −73,8–109,0) | 0,944 |
| Berlari (pasca-saring) | 0,917 | **0,132** (−5,1 ms; LoA −40,4–30,1) | 0,909 |

**Judul "Limited Validity" merujuk kondisi berlari.** Skenario wawancara adalah **duduk** —
kondisi dengan kesepakatan tertinggi. Makalah ini **mendukung** pilihan H808S, bukan mengancamnya.

> Kalimat siap pakai: *Protzen dkk. (2025) melaporkan kesepakatan ICC > 0,990 antara Coospo H808S
> dan Polar H10 untuk RR, RMSSD, dan HR pada posisi duduk — posisi yang digunakan dalam penelitian ini.*

Catatan tambahan: penyaringan justru **menurunkan** kesepakatan; penulis menduga ada perbedaan
pemrosesan sinyal internal antar-perangkat (relevan untuk L13).

**Schaffarczyk dkk. (2022)**, *Sensors* 22(17):6536 — Polar H10 untuk HRV: r = 0,95–1,00 saat
istirahat, bias absolut < 1 ms. Dipakai sebagai acuan tervalidasi yang **disitasi tanpa dibeli**.

### 2.2 Validitas PPG pada kondisi bicara-di-bawah-tekanan — Sinichi dkk. (2025)

*Psychophysiology* 62:e70004. Empat perangkat PPG — Kyto2935 (daun telinga, 1024 Hz),
Schone Rhythm 24 (lengan, 125 Hz), HeartMath Inner Balance (daun telinga, 125 Hz),
**Empatica EmbracePlus** (pergelangan, 64 Hz, "research-grade") — melawan ECG kriteria
VU-AMS 5fs (1000 Hz). 40 partisipan, 8 kondisi.

Kondisi **arithmetic** = duduk, gerakan minimal, mengurangi 13 dari 1022 **sambil bersuara** di
hadapan eksperimenter — profil identik dengan menjawab pertanyaan wawancara.

| Perangkat (lokasi) | mean HR: duduk → aritmetika | LnRMSSD: duduk → aritmetika | MAAPE RMSSD aritmetika |
|---|---|---|---|
| HeartMath (daun telinga) | 1,00 → **1,00** | 0,95 → **0,63** | 40,9% |
| Kyto (daun telinga) | 1,00 → **0,99** | 0,98 → **0,70** | 25,4% |
| Rhythm 24 (lengan) | 0,87 → **0,88** | 0,84 → **0,58** (tidak signifikan) | 68,1% |
| Empatica (pergelangan) | 0,99 → **0,75** | 0,79 → **0,31** (tidak signifikan) | 88,0% |

Gradien penempatan: **daun telinga > lengan > pergelangan.** (Catatan kejujuran: laju cuplik juga
berbeda — 1024/125/125/64 Hz — jadi penempatan bukan satu-satunya faktor.)

**Kutipan kunci:**
> "Sitting, recovery, breathing, and neurotask shared mutual characteristics, as in all these
> laboratory conditions participants remained seated **with no movement or speech**."

> "PPG devices, even those advertised and designed for research purposes, may pose validity
> concerns for HRV measurement in conditions other than those similar to resting states."

**Tiga konsekuensi:** (1) yang merusak PPG **bukan gerakan** melainkan **bicara + tekanan** —
persis yang diciptakan produk ini; (2) Empatica "research-grade" **tidak mengungguli** perangkat
konsumen, menguatkan L11 secara independen; (3) detak jantung **tetap andal** bahkan pada kondisi
itu — dasar untuk tingkat PPG berbasis HR.

**Bonus:** protokol aritmetika mereka (1022 − 13, ulang bila salah) menjadi **sitasi peer-reviewed**
untuk protokol uji §6. Mereka juga mencatat tugas itu *"contains other components such as speech,
and potential muscle contraction, that can all change HR and HRV and affect the signal quality"* —
sitasi siap pakai untuk L9 dan T3a.10.

**Tinjauan sistematis sensor dada** — *Sensors* 25(19):6049 (2025): Polar H10/H7 paling sering
diteliti; Zephyr BioHarness 3.0 satu-satunya ber-FDA 510(k) (tetap bukan untuk diagnosis);
Movesense r > 0,95, galat < 1%. **Tidak satu pun berizin CE/FDA untuk penggunaan klinis.**

### 2.3 Arsitektur akuisisi pada penelitian lain

| Arsitektur | Contoh | Real-time | Web Bluetooth |
|---|---|---|---|
| Aplikasi vendor → ekspor → Kubios | Schaffarczyk dkk. 2022 | Tidak | Tidak |
| Polar BLE SDK (app native) | Standar riset Polar | Ya | Tidak |
| **Python + Bleak (BLE dari PC)** | **Gellisch & Burr 2025** | Ya | Tidak |
| **App Android jembatan → DB → web dashboard** | **De Palma dkk. 2022** | Ya | **Tidak** |
| **Web Bluetooth (browser)** | Hilbel dkk. 2021 (usul); `pure-blue-heart`, Web HR Monitor, HypeRate (implementasi) | Ya | **Ya** |
| Mikrokontroler custom (ESP32) | Mayoritas jurnal Indonesia | Ya | Umumnya via WiFi/IoT |

**De Palma dkk. (2022)**, IEEE MeMeA, Politecnico di Bari — meski judulnya *"web-based system for
interfacing a portable Bluetooth vital sign monitor"*, arsitekturnya **Android app (Bluetooth
SPP/SPPLE) → MariaDB → web app (HTML/PHP/XAMPP)**. Profil Bluetooth **serial**, bukan GATT HRS.

> Kontras berguna: makalah IEEE 2022 yang eksplisit menargetkan *web-based interfacing* **masih
> membutuhkan aplikasi native di tengah**.

**Hilbel dkk. (2021)**, *Cardiovascular Digital Health Journal* — membahas Web Bluetooth API
sebagai jalur membaca RR untuk HRV tanpa aplikasi vendor; mencatat resolusi 1/1024 dtk lebih baik
daripada banyak Holter.

### 2.4 HRV + LLM / RAG — posisi TA ini

**Gellisch & Burr (2025)**, *Frontiers in Digital Health*.

| Aspek | Gellisch & Burr | TA ini |
|---|---|---|
| Sensor | Polar H10 | HW9 / H808S |
| Akuisisi | Python 3.11 + Bleak 0.20.2 di Raspberry Pi | **Web Bluetooth di browser** |
| Fitur | HR, RMSSD, SDNN, pNN50, LF/HF · jendela geser 60 dtk | **sama persis** |
| Backend | FastAPI (Render.com) | FastAPI |
| LLM | GPT-4 via API | Gemini 2.5 Flash |
| **RAG** | **Tidak ada** | **KB 23 chunk terkurasi, ID stabil, rujukan** |
| **Penentu label** | LLM ikut menghitung statistik | **Aturan skor (K16); LLM hanya menarasikan** |
| **Pengaman halusinasi** | **Tidak ada** | `rag/guards.py` — angka wajib tertelusur, rujukan wajib terambil |
| Validasi | Demo kecil (65,50 vs 58,42 bpm) | WESAD holdout 10 subjek tersegel, 561 segmen, acc 0,852 / macro-F1 0,839 / κ 0,678 |

**Kelemahan yang mereka akui:** dalam 2 jam, koneksi API dibangun ulang **enam kali**, dan
**nilai fabrikasi teramati satu kali**.

> *Pendekatan serupa telah diusulkan, namun penulisnya melaporkan LLM mengarang nilai fisiologis;
> penelitian ini menutup celah tersebut dengan pengaman otomatis dan dengan memindahkan penentuan
> label dari LLM ke aturan skor terkalibrasi.*

**Ha dkk. (2026)**, *Bioengineering* 13:58 (Korea University & Ewha) — Xiaomi Smart Band 9,
297 partisipan (237/60), 9.543 jendela 7-hari, LR/XGBoost/LSTM, LLM **Llama 3.3 70B lokal via
Ollama** (temp 0,1) diaktifkan hanya untuk zona ambang (0,45 ≤ p ≤ 0,55), RAG menarik 5 sampel
latih termirip (all-MiniLM-L6-v2, 384-dim), aturan didistilasi GPT-5.
Zona ketidakpastian: 0,556/0,684/0,635/0,659 → 0,617/0,703/0,748/0,725. Uji penuh:
0,707/0,739/0,918/0,819 → 0,718/0,741/0,937/0,827 (McNemar p < 0,05). Inferensi 910 → 162 menit.

**Perbedaan yang menjaga kebaruan:** (1) RAG mereka mengambil *contoh pelatihan* (few-shot),
TA ini mengambil *pengetahuan domain terkurasi* berujukan; (2) LLM mereka **ikut menentukan label**
lewat convex combination, di TA ini tidak sama sekali; (3) tidak ada verifikasi keterlacakan angka;
(4) domain & resolusi berbeda (kelelahan 7-hari vs tekanan akut 60 detik).
**Layak diadopsi:** LLM lokal via Ollama demi reproduksibilitas — mitigasi untuk L8.

### 2.5 rPPG (webcam) — di luar cakupan

**Cara kerja:** hemoglobin menyerap hijau (520–580 nm) → deteksi wajah (BlazeFace/FaceMesh) →
ROI dahi & pipi → rata-rata RGB per frame → pisahkan AC dari DC → deteksi puncak → IBI.
Metode: GREEN, ICA, PCA, CHROM, **POS**; deep learning: DeepPhys, HR-CNN, Meta-rPPG, transformer.

**Woelk dkk. (2026)**, *Behavior Research Methods* — webcam Trust GXT 1160, 25–30 fps, POS via
**pyVHR**, 77 partisipan, 2.436 rekaman (678 untuk HRV), tugas **tanpa bicara**:
HR andal; SDNN |Δ| = **11,45 ± 14,34 ms**; RMSSD |Δ| = **11,02 ± 10,43 ms**.

> "rPPG reliably captures average HR, but the accuracy of individual-level HRV estimates remains limited."

**Kenapa HR bisa tapi RMSSD tidak:** webcam 30 fps → jarak antar-sampel **33 ms**; chest strap
**1 ms**. Selisih **33×**. Ambang TA ini (RMSSD −20% pada baseline 30 ms) = perubahan **6 ms**,
sedangkan galat **11 ms** — hampir dua kali sinyal, dan bukan bias tetap.

**Pembunuh lain:** pencahayaan (optimal 500–700 lux), **kompresi video merusak sinyal** (McDuff dkk.),
bias warna kulit, dan bicara. UBFC-Phys (Tahap 8) adalah dataset video + BVP pada tugas stres
sosial — bahan tepat bila arah ini dikejar setelah TA.

### 2.6 Bukti kompatibilitas perangkat non-Polar

**HypeRate Web Bluetooth:** *"Any BLE heart rate monitor that implements the standard `heart_rate`
GATT service is supported."* Perangkat yang mereka uji: Polar H10/H9, Garmin HRM-Dual, Wahoo TICKR,
**COOSPO H808s**. Daftar lengkap mencakup CooSpo H808S, H8, H6, HW706, HW807.

Bukti independen: Rutenberg (2026) menyambungkan monitor **Decathlon** lewat Web Bluetooth —
tersambung tanpa masalah; yang bermasalah RR-nya yang sintetis.

**Yang eksklusif Polar:** layanan berpemilik **PMD** untuk PPG/ECG mentah. TA ini tidak membutuhkannya.

> Klaim arsitektural: *sistem mengakses sensor melalui Heart Rate Service standar (0x180D) alih-alih
> SDK berpemilik, sehingga bersifat netral-vendor dan dapat menerima berbagai sensor tanpa perubahan kode.*

### 2.7 Smartwatch — jalan buntu di dua lapis

| Perangkat | Siaran BLE? | Menyertakan RR? | Bukti |
|---|---|---|---|
| Samsung Galaxy Watch (incl. Ultra) | **Tidak** | — | Masih *feature request* di forum resmi Samsung |
| Apple Watch | Tidak bawaan | **Tidak** | App jembatan (Echo, BlueHeart, HRM) hanya BPM |
| Garmin (jam tangan) | Ya | **Tidak** | Forum Garmin: tidak ada HRV ke Elite HRV / HRV4Training |
| Garmin HRM-Dual / HRM Pro (sabuk dada) | Ya | **Ya** | Terdaftar kompatibel Elite HRV |

Elite HRV mencantumkan smartwatch **tidak kompatibel**: sensor LED "are not accurate enough yet to
capture the exact R-wave peak"; banyak perangkat "simply smooth out, or average, the R-R intervals".

---

## 3. Perangkat: Perbandingan & Keputusan

### 3.1 Tabel perangkat (harga Tokopedia, Agustus 2026)

| Model | Tipe | RR / Web BT | Harga | Catatan |
|---|---|---|---|---|
| **Coospo HW9** | Armband PPG | Ya / Ya | **Rp 850.000** | **DIPILIH untuk uji pertama.** Spek resmi: **HRV Yes**, sensor optik generasi ke-3 ±1 bpm, BLE 5.0, 2 koneksi, baterai 35 jam. Diuji Altini vs Polar H10 (kondisi tenang) |
| **Coospo H808S** | Chest strap ECG | Ya / Ya | **Rp 539.000** | **Jalur mundur.** ICC > 0,990 duduk vs Polar H10 (Protzen dkk.) |
| Magene H64 | Chest strap ECG | Ya (standar) / Ya | Rp 502.500 | Termurah; COD tersedia; RR belum terkonfirmasi studi |
| ~~Coospo HW706~~ | Armband PPG | **TIDAK** | Rp 641.000 | **DICORET** — spek resmi Coospo: **"HRV Support: No"**. Baterai 20 jam, generasi sensor tidak disebutkan |
| ~~LIVLOV V9~~ | Armband PPG | **Belum terverifikasi** | ~Rp 420.000 | **DICORET** — lihat koreksi §3.2 |
| Magene H803 | Armband PPG | Ya / Ya | Rp 849.000 | Tanpa rekam jejak uji pihak ketiga |
| Magene H303 | Chest strap ECG | Ya / Ya | Rp 817.300 | Lebih mahal tanpa keunggulan jelas |
| ~~Coospo H6~~ | Chest strap ECG | Ya / Ya | ~Rp 1.600.000 | **DICORET** — model 2018, langka, harga kelangkaan |
| ~~Kalenji/Decathlon~~ | Chest strap | **RR sintetis** | ~Rp 500.000 | **DICORET** — Rutenberg: RR = 60000/HR |
| Polar H10 | Chest strap ECG | Ya / Ya | Rp 1,3–1,9 jt | Di luar rencana; tetap disitasi sebagai acuan |
| Polar Verity Sense | Armband PPG | Ya + PPG mentah | ~Rp 1,5 jt+ | Satu-satunya jalur PPG mentah via Web Bluetooth |

**HW9 vs HW706 — pembanding langsung dari spesifikasi resmi Coospo:**

| | HW9 | HW706 |
|---|---|---|
| **HRV Support** | **Yes** | **No** |
| Sensor optik | Generasi ke-3, ±1 bpm | Tidak disebutkan |
| Bluetooth | 5.0, dua koneksi sekaligus | Versi tidak disebutkan |
| Baterai | 35 jam | 20 jam |
| Harga resmi | $54,89 | $37,29 |

Selisih Rp 200 ribu itu **membeli satu-satunya fitur yang membuat perangkat berguna** untuk TA ini.

**Anggaran:** HW9 Rp 850.000 + H808S Rp 539.000 = **Rp 1.389.000** (batas Rp 1,5 juta).
Ditambah baterai CR2032 cadangan (~Rp 20.000) dan gel/air elektroda (≤ Rp 50.000).

### 3.2 Koreksi penalaran — daftar perangkat HypeRate

**Penalaran yang keliru dan sudah dicabut:** sebelumnya HW706 dan LIVLOV V9 dianggap layak karena
terdaftar di HypeRate. Itu **kesimpulan yang terlalu jauh**.

HypeRate hanya membutuhkan **bpm** — layanannya menampilkan detak jantung untuk streamer. Dan
Heart Rate Service standar dapat mengirim bpm **tanpa** field RR; field RR bersifat **opsional**
dalam profil tersebut. Jadi "terdaftar di HypeRate" membuktikan perangkat mengimplementasikan HRS,
**bukan** membuktikan ia mengirim RR.

Spesifikasi resmi Coospo mengonfirmasi: HW706 **"HRV Support: No"**.

**Yang tetap sah dari HypeRate:** bukti bahwa perangkat **non-Polar dapat tersambung** lewat
Web Bluetooth. Klaim kompatibilitas masih berlaku; klaim dukungan RR tidak.

**Pelajaran umum:** dukungan RR hanya boleh disimpulkan dari (a) spesifikasi resmi yang menyebut
HRV/R-R, (b) penggunaan terdokumentasi dengan aplikasi HRV yang membaca RR (mis. HRV Logger,
Elite HRV, HRV4Training), atau (c) **pengujian langsung**. HW706 adalah contoh nyata jebakan
"tersambung normal, tampil rapi, tapi RR tidak ada".

---

### 3.3 Sifat terverifikasi HW9 — uji 20 Agustus 2026

Diukur langsung, bukan dari spesifikasi vendor. Rekaman: duduk diam, 502 interval, RMSSD
32,11 ms, outlier 1,0%, HR rata-rata 85,8 bpm. Berkas mentah `rr_uji_sensor.json` disimpan
sebagai bukti.

**Gerbang 1 — field RR: LOLOS.** Bit RR (0x10) menyala; perangkat mengirim interval, bukan
hanya bpm rata-rata.

**Gerbang 2 — sumber RR: ASLI.** Awalnya perkakas memutuskan "sintetis"; putusan itu **salah**
dan sudah dikoreksi (§1.5). Bukti bahwa RR-nya sungguhan:

| RR | Jarak antar nilai **seandainya** `60000/bpm` | Jarak yang **terukur** |
|---|---|---|
| 549 ms | 5,00 ms | 7,8125 ms |
| 709 ms | 8,40 ms | 7,8125 ms |
| 855 ms | 12,07 ms | 7,8125 ms |

Datar sepanjang rentang. Korelasi jarak terhadap RR² = **−0,09**; simulasi deret `60000/bpm`
menghasilkan **+0,97**. Selain itu 36 dari 43 slot kisi terisi (**84%**) — deret asli mengisi
kisinya rapat, deret palsu meninggalkannya bolong (simulasi: 32%).

**Sifat instrumen yang harus dilaporkan.** HW9 mendeteksi denyut pada **tepat 128 Hz**,
sehingga RR jatuh di kisi **7,8125 ms** (= 1/128 detik = 8 satuan 1/1024 detik) — bukan ~1 ms
sebagaimana disiratkan satuan field BLE. Nilai RR yang mungkin di rentang 549–869 ms karena itu
hanya sekitar empat puluh buah. Ini **bukan** cacat dan **bukan** alasan menolak perangkat; ia
properti alat yang harus ikut ditulis, sebagaimana L13 menuntut merek/model/firmware dicatat.

> **Koreksi 20 Agustus 2026, sore.** Angka pertama yang tercatat di sini adalah 7,62 ms /
> ≈131 Hz. Itu **salah**, dan penyebabnya perkakas sendiri: halaman uji sensor membulatkan RR
> ke satu desimal sebelum mengekspor, sehingga kisi 7,8125 ms terbaca sebagai campuran 7,8 dan
> 6,9 dan rata-ratanya meleset. Rekaman protokol tiga blok menyimpan presisi penuh dan
> memperlihatkan kisi yang bersih: 40 dari 58 jarak antar nilai unik **tepat** 7,8125 ms,
> mediannya 7,8125 ms, dan 1000/7,8125 = 128,00 Hz — angka bulat yang wajar untuk laju
> pencuplikan. Pembulatan di halaman uji sensor sudah dihapus.

**Harga kuantisasinya, dihitung.** Kuantisasi seragam berlangkah `q` menambah varians `q²/6`
pada selisih antar denyut, yaitu **9,69 ms²** (σ = 3,11 ms) yang bertambah secara kuadratik:

- RMSSD terukur 32,11 ms → setelah dikoreksi **31,95 ms**. Selisih **0,16 ms**.
- Efek ke persen perubahan terhadap baseline selalu ke arah **meremehkan** reaktivitas, dan
  kecil. Dengan baseline 40 ms: penurunan sebenarnya −75,0% terbaca −73,9%; −87,5% terbaca
  −85,3%. Bias maksimum di bawah **2,2 poin persen**.

Kesimpulan: aman untuk fitur domain waktu. Untuk domain frekuensi lihat L20.

**Yang masih terbuka — cakupan waktu.** Pada rekaman pertama (347 interval, timer 5:24) jumlah
RR hanya menutupi ≈243 detik dari 324 detik yang berjalan, sementara outlier hanya 1,2%
sehingga **tidak ada RR ganda** yang menandai lubangnya. Bila interval ternyata tidak
benar-benar berurutan, RMSSD menghitung selisih antara dua denyut yang tidak bersebelahan.
Perkakas sekarang mencatat `paket_dengan_rr` dan `paket_tanpa_rr` pada ekspornya; periksa ini
di rekaman berikutnya sebelum protokol tiga blok dijalankan. Lihat L21.


### 3.4 Uji protokol tiga blok — 20 Agustus 2026

Rekaman lengkap 1.068 denyut, 15 menit. Berkas `uji_protokol_rr.json`. Putusan terkunci §6.1
mengembalikan **LULUS** untuk perangkatnya, dengan peringatan tafsir yang memang sudah ditulis
di muka — dan peringatan itu ternyata yang paling penting.

| Blok | n RR | Cakupan waktu | Outlier | Segmen layak | mean HR | RMSSD median |
|---|---|---|---|---|---|---|
| Istirahat (5 mnt) | 377 | 88,6% | 4,5% | 8/8 | 85,6 bpm | 38,8 ms |
| Tertekan (3 mnt) | 234 | 90,4% | 4,3% | 4/4 | 86,9 bpm | 32,7 ms |
| Pemulihan (3 mnt) | 193 | **75,4%** | 11,4% | **2/4** | 86,2 bpm | 47,8 ms |

**Perangkatnya lolos.** Outlier 4,5% dan 4,3% di dua blok pertama setara mutu ECG dada pada
WESAD (0,0–4,2%), seluruh segmen layak, dan RMSSD istirahat 38,8 ms berada di tengah rentang
wajar 20–60 ms. Gerbang 1 (§3.3) selesai.

**Stresornya tidak bekerja.** HR hanya naik **+1,5%** (85,6 → 86,9). RMSSD median turun 15,8%.
Peringatan tafsir §6.1 — "bila HR tidak naik di blok 2, jangan menyalahkan sensor" — berbunyi
persis sebagaimana dirancang. Ini contoh kriteria terkunci bekerja: kalau peringatannya baru
ditulis setelah melihat angka ini, ia tidak akan berarti apa-apa.

**Temuan terpenting: blok istirahat bukan istirahat.** RMSSD per segmen 60 detik sepanjang lima
menit "istirahat" berturut-turut 38,8 · 30,4 · 32,2 · 35,5 · 38,9 · 41,0 · 47,4 · 46,1 ms.
Paruh pertama rata-rata 34,2 ms, paruh kedua **43,3 ms** — naik **26,5%**, dengan kemiringan
+1,97 ms per segmen. Subjek masih terus menenang selama seluruh blok baseline.

Konsekuensinya berlapis dan semuanya buruk untuk penafsiran:

1. **Baseline-nya bukan baseline.** Ia rata-rata dari sebuah tren, bukan tingkat yang mapan.
2. **Reaktivitas jadi tidak terbaca ke arah mana pun.** Terhadap median blok istirahat,
   penurunannya −15,8%. Terhadap dua segmen terakhir istirahat (47,4 dan 46,1 ms) — yaitu
   tingkat yang paling dekat dengan keadaan sesaat sebelum stresor — penurunannya jauh lebih
   besar. Angka mana yang benar tidak bisa ditentukan dari data ini.
3. **Pemulihan jadi tidak bermakna.** RMSSD pemulihan 47,8 ms berada **di atas** median
   istirahat (+23,1%), dan masih di atas paruh kedua istirahat (+10,4%). Tidak ada yang pulih
   ke mana-mana; yang terlihat adalah tren menenang yang sama, berjalan terus.

Ini mereproduksi keterbatasan #1 di `development_journey.md` §7 — baseline pra-wawancara bukan
baseline netral sejati — pada tubuh dan sensor sendiri, bukan pada WESAD. Dan ia sejalan dengan
temuan `analyse_baseline_duration.py`: 0 dari 15 subjek WESAD stabil dalam 2 menit, median baru
stabil di 4 menit. Di sini bahkan 5 menit belum menunjukkan dataran.

**Lubang rekaman — L21 terkonfirmasi dan terukur.** Sepanjang sesi ada **30 lubang** dengan
total **150,7 detik** tanpa denyut. Dari 30 lubang itu, hanya **8 (27%)** kebetulan ikut
tertandai gerbang outlier T1.5; **22 sisanya lewat sebagai data bersih**. Ini bukan kelemahan
implementasi melainkan sifat kriterianya: denyut yang datang sesudah hening empat belas detik
tetap berupa interval ~700 ms di sebelah interval ~700 ms lain, tidak di luar rentang dan tidak
berbeda 20% dari pendahulunya.

Kabar baiknya, harganya kecil dan sudah dihitung: membuang setiap pasangan yang melangkahi
lubang menggeser RMSSD paling banyak **0,53 ms** (istirahat +0,06 ms, tertekan +0,52 ms,
pemulihan +0,53 ms). **Yang hilang adalah jumlah sampel, bukan ketepatan.** Bahayanya berupa
blok yang diam-diam berdiri di atas tiga perempat denyut yang disiratkan durasinya — persis
yang terjadi pada blok pemulihan, dan itu pula sebab 2 dari 4 segmennya gugur.

Perkakas sekarang melaporkan cakupan waktu per blok berdampingan dengan outlier, karena
keduanya menjawab pertanyaan berbeda: outlier menilai denyut yang **masuk**, cakupan menilai
denyut yang **hilang**.

**Cacat perkakas yang ditemukan lewat rekaman ini** (semuanya sudah diperbaiki):

| Cacat | Akibat |
|---|---|
| Label fase `'pra'` dipakai untuk sebelum **dan** sesudah protokol | 264 denyut pasca-protokol (t 663–898 dtk, ±4 menit) terlabel `'pra'`. Analisis per label akan membaca akhir sesi sebagai baseline sebelum sesi. Sekarang ada label `'pasca'` |
| `d.uniq.add(Math.round(v))` membulatkan RR ke ms bulat | Menghancurkan kisi 7,8125 ms sebelum diperiksa; `resolusi_ms` melaporkan 8 dan korelasi kisi ikut terdistorsi |
| Halaman uji sensor membulatkan RR ke 1 desimal saat ekspor | Sumber angka 7,62 ms / 131 Hz yang keliru (lihat koreksi §3.3) |

**Yang harus dilakukan sebelum G2 ditutup:** ulangi protokol dengan (a) baseline lebih panjang
atau berkriteria berhenti otomatis, (b) stresor yang benar-benar menuntut, dan (c) pemasangan
di lengan atas sesuai §6.2. Sampai baseline berhenti melayang, tidak ada angka reaktivitas dari
perangkat ini yang layak masuk laporan.


## 4. Modalitas PPG di Dalam Penelitian Ini (HW3)

PPG **bukan pengembangan lanjutan**. Proposal sudah menjanjikan sistem dua cabang (Gambar 3.1
"Diagram Blok Sistem Dua-Cabang (ECG dan PPG)", berkas `dual_branch_ecg_ppg.svg`).

**Prinsip pengunci:** *"PPG masuk penelitian" berarti PPG **diukur**, bukan PPG **berhasil**.*
Hasil negatif tetap sah — preseden ada di bab SWELL (T7.3, κ = −0,207) yang ditangani lewat
analisis sebab (L12).

### 4.1 Tiga lapis bukti

Pertanyaan penelitian: *sejauh mana modalitas PPG dapat menggantikan ECG untuk penilaian tekanan
dalam konteks wawancara?*

| Lapis | Isi | Status | Biaya |
|---|---|---|---|
| **1 — Dataset** | T6.4: perbandingan berpasangan ECG–PPG di WESAD, 90 segmen, 5 subjek | **Selesai** | nol |
| **2 — Fitur** | Aturan skor dengan **HR saja** pada WESAD; laporkan macro-F1 berdampingan dengan RMSSD-saja (0,742) dan RMSSD-atau-HR (0,828) | **Belum** | ~1 hari, tanpa API/perangkat |
| **3 — Perangkat** | Uji HW9 dengan protokol tiga blok; bila H808S dibeli, jalankan berpasangan | **Belum** | ~1 sore setelah perangkat tiba |

Lapis 3 **orisinal** — belum ada yang menguji armband optik modern pada kondisi bicara-di-bawah-tekanan.

### 4.2 Keandalan per fitur pada PPG

Semua fitur **dihitung sama** (§1.1); yang berbeda adalah keandalannya.

| Fitur | Status | Bukti |
|---|---|---|
| **meanHR / meanRR** | **Andal** | ICC +0,986 (T6.4); r 0,99–1,00 saat aritmetika-bersuara (Sinichi) |
| **Reaktivitas HR** | **Andal** | L9: HR naik pada **kelima** subjek dev (+5,1% s.d. +74%) — penanda paling konsisten |
| **Linimasa HR** | **Andal** | Turunan HR |
| **Pemulihan berbasis HR** | **Andal** | *Heart rate recovery* adalah ukuran mapan tersendiri di kardiologi |
| Reaktivitas RMSSD | Menengah | ICC **+0,620** (T6.4) — jauh di atas nilai absolutnya |
| SDNN | Menengah–lemah | Secara teori lebih tahan (ragam total, bukan hanya selisih berurutan); tidak ada angka per perangkat |
| **RMSSD absolut** | **Tidak andal** | ICC +0,109, bias **+95 ms** (T6.4); r 0,31–0,70 saat bicara-tertekan (Sinichi) |
| **pNN50** | **Tidak andal** | Hitungan ambang pada selisih berurutan — derau langsung jadi hitungan palsu |
| **HF power** | **Tidak andal** | Digerakkan variasi antar-denyut; berkorelasi tinggi dengan RMSSD |
| **LF/HF** | **Tidak andal** | Ketidakstabilan LF pada segmen 60 dtk (L3) + ketidakandalan HF |
| **SD1** | **Tidak andal** | SD1 ≈ RMSSD/√2 — mewarisi persis masalahnya |

**Pola tunggal:** semua yang rapuh berasal dari **selisih antar-denyut berurutan**. Satu denyut
salah deteksi langsung merusaknya. Rata-rata detak jantung dihitung dari banyak denyut, sehingga
kesalahan tunggal terserap.

### 4.3 Batas kalibrasi

| Bisa dikoreksi | Tidak bisa dikoreksi |
|---|---|
| **Bias tetap** — offset konstan tinggal dikurangi | **Sebaran (LoA)** — Protzen berlari: bias +17,6 ms tapi LoA −73,8…109,0. Mengoreksi bias menyisakan ±90 ms |
| **Normalisasi baseline** — sudah terbukti bekerja | **Data yang hilang** — bila gerbang membuang segmen (outlier 16–37%), tidak ada yang bisa dikalibrasi |

**Kalibrasi yang sudah bekerja:** normalisasi baseline menaikkan RMSSD dari ICC **+0,109**
(absolut) ke **+0,620** (reaktivitas). Ini kalibrasi yang sudah diterapkan dan sudah terukur.

**Bingkai yang benar:** hasil PPG bukan lulus/gagal melainkan **bergradasi** — HR sangat baik,
reaktivitas HR baik, reaktivitas RMSSD menengah, RMSSD absolut buruk.

### 4.4 Kerangka konseptual bertahan dengan substrat HR

Tiga konstruk utama tidak hilang, hanya ganti substrat:

- **Reaktivitas** → dihitung dari HR
- **Pemulihan** → *heart rate recovery*, ukuran mapan tersendiri
- **Indeks ketahanan** (T2.8) → kuadran 2×2 reaktivitas × pemulihan tetap berfungsi dengan kedua sumbu berbasis HR; **kode tidak perlu diubah**, hanya masukannya

**Yang hilang dan harus jujur disebut:** dimensi parasimpatis — kemampuan membedakan "tegang tapi
terkendali" dari "tegang dan kewalahan". HR hanya menunjukkan besar rangsangan, bukan kualitas rem vagal.

**Yang PPG punya tapi tidak dapat dipakai:** amplitudo gelombang PPG itu sendiri adalah sinyal
stres (vasokonstriksi menurunkannya), begitu pula morfologi gelombang dan indeks perfusi. Semuanya
butuh **gelombang mentah**, sedangkan armband konsumen hanya mengirim interval.

---

## 5. Rancangan Alur Sesi

```
[Sensor: HW9 (armband) atau H808S (chest strap)]
        │  BLE GATT 0x180D / 0x2A37 (RR, 1/1024 s)
        ▼
[Browser — Web Bluetooth]
        │  GERBANG 1: RR hadir? bukan sintetis?
        ▼
[Fase adaptasi 1 mnt]  ── GERBANG 2: outlier ≤ 10%? ──┐ gagal → perbaiki, ulangi
        ▼                                              │
[Kalibrasi 2 mnt] ───── GERBANG 3: baseline layak? ────┘ gagal → ulangi kalibrasi
        │  → baseline per subjek (2-4 segmen, hop 15 dtk)
        ▼
[Pengarahan 2 mnt]  (tidak dianalisis — L1)
        ▼
[Tanya-jawab: 90 dtk jawab + jeda 60 dtk (sulit) / 20 dtk (biasa)]
        ▼
[POST JSON → FastAPI]
        ▼
[Pipeline hrv-rag: koreksi ektopik → segmentasi 60/30 → fitur →
 baseline/reaktivitas/pemulihan → aturan skor (LABEL) →
 retrieval KB → 1× LLM (NARASI) → guards → simpan mentah]
        ▼
[Dashboard bahasa awam (K4), metrik digerbang menurut modalitas]
```

### 5.1 Tiga gerbang mutu (HW5)

**Gerbang 1 — Perangkat (±30 dtk).** Field RR menyala; bukan sintetis (§1.5); paket stabil.
Gagal → tidak bisa lanjut.

**Gerbang 2 — Adaptasi (menit ke-1, tanpa disadari pengguna).** Outlier menurut T1.5.
Acuan: ECG WESAD **0,0–4,2%**; PPG saat TSST **16–37%**. > 10% → perbaiki, ulangi.

**Gerbang 3 — Baseline (kalibrasi 3 mnt), PALING KETAT.** Baseline adalah **titik kegagalan
tunggal**: Aturan Wajib #2 membuat seluruh reaktivitas relatif terhadapnya, dan kegagalannya
**tidak memunculkan pesan galat**. Gagal → ulangi kalibrasi sebelum wawancara, bukan sesudah.

**Prinsip pengikat:** sesi tidak boleh gagal total. Segmen yang tidak lolos ditandai, bukan
membatalkan sesi. Laporkan cakupan di akhir ("12 dari 14 segmen layak dianalisis").

### 5.2 Skema JSON ke backend

```json
{
  "sesi_id": "uuid",
  "perangkat": { "merek": "Coospo", "model": "HW9", "modalitas": "PPG", "firmware": "…" },
  "kb_versi": "kb_v2.0",
  "fase": [
    { "nama": "adaptasi",   "mulai_dtk": 0,   "akhir_dtk": 60  },
    { "nama": "kalibrasi",  "mulai_dtk": 60,  "akhir_dtk": 180 },
    { "nama": "pengarahan", "mulai_dtk": 180, "akhir_dtk": 300 },
    { "nama": "jawab_q1",   "mulai_dtk": 300, "akhir_dtk": 390, "sulit": true },
    { "nama": "jeda_q1",    "mulai_dtk": 390, "akhir_dtk": 450 }
  ],
  "rr_ms":    [812.5, 798.8],
  "rr_t_dtk": [0.81, 1.61],
  "gerbang":  { "g1_rr_asli": true, "g2_outlier_persen": 2.4, "g3_baseline_layak": true }
}
```

Anonimisasi (T2b.4): tidak ada nama, NRP, atau email ke backend maupun LLM.
Field `modalitas` menggerakkan Aturan Wajib #5 dan penggerbangan metrik di dashboard.

### 5.3 Integrasi dengan pipeline

| Tahap | Perlakuan untuk data live |
|---|---|
| Pra-pemrosesan sinyal mentah (filter, notch, deteksi puncak) | **Dilewati** — sensor sudah melakukannya di firmware |
| Koreksi ektopik (T1.5) | Tetap |
| Gerbang outlier > 10% (T1.6) | Tetap; sekaligus gerbang 2 & 3 |
| Segmentasi 60/30 (T2.1) | Tetap, memakai `rr_t_dtk` |
| Fitur (T2.2–T2.4) | Tetap; penggerbangan tampilan menurut §4.2 |
| Baseline per subjek (T2.5) | Dari fase kalibrasi, 5 segmen |
| Reaktivitas & pemulihan (T2.6–T2.7) | Tetap; substrat HR bila modalitas PPG |
| Aturan skor → label (T2c.1) | Tetap; LLM tidak menyentuh label |
| Retrieval + narasi (T4.x) | Satu panggilan per sesi (K16) |
| Guards (T4.6) | Tetap; hasilnya dilaporkan sebagai temuan |

---

## 6. Protokol Uji Perangkat & Kriteria Terkunci

Protokol mengikuti kondisi baku Sinichi dkk. (2025) agar sebanding dengan literatur.
Perangkat dipasang sekali dan tidak dilepas selama tiga blok.

| Blok | Durasi | Kegiatan | Yang dibaca |
|---|---|---|---|
| 1 — Istirahat | 5 mnt | Duduk diam, napas normal, **tidak bicara** | Outlier dasar (%) |
| **2 — Tertekan** | 3 mnt | **Kurangi 13 dari 1022 berulang, BERSUARA; salah → ulang dari 1022.** Tubuh diam, hanya mulut bergerak | **Outlier tertekan (%)**, hasil segmen |
| 3 — Pemulihan | 3 mnt | Duduk diam kembali | Outlier pemulihan (%) |

### 6.1 Kriteria putusan (dikunci sebelum uji dijalankan)

| Hasil | Tindakan |
|---|---|
| Field RR tidak ada, atau terdeteksi **sintetis** | **Retur perangkat segera** |
| Blok 2 outlier ≤ 10%, sebagian besar segmen layak, **dan** RMSSD istirahat masuk akal (20–60 ms) | **Lolos** — lanjut memakai HW9 |
| Blok 2 outlier 10–20% | **Ulangi sekali** setelah membetulkan posisi & kekencangan |
| Blok 2 outlier > 20%, **atau** nol segmen layak, **atau** RMSSD melompat liar antar segmen sefase | **Beralih ke H808S** — sekaligus mereplikasi L11 pada perangkat modern |

**Peringatan tafsir:** bila **HR tidak naik** di blok 2, jangan menyalahkan sensor — kemungkinan
besar peserta belum benar-benar tertekan. Ulangi dengan stresor lebih menuntut lebih dulu.

**Batas penafsiran dengan satu perangkat:** outlier rendah **belum** membuktikan RMSSD akurat —
bias sistematis dapat lolos gerbang. Uji satu-perangkat dapat **membantah**, tidak dapat
**memastikan**. Kepastian menuntut pembanding chest strap (slot perangkat B).

### 6.2 Persiapan praktis

- **Pakai di lengan atas** (bisep/trisep), bukan lengan bawah dekat pergelangan
- **Pastikan lengan hangat.** Ruangan ber-AC → vasokonstriksi → amplitudo PPG turun; mekanismenya sama dengan stres, sehingga bisa menghasilkan "kegagalan" palsu
- Kencang cukup agar tidak bergeser, tidak sampai menekan
- Kulit bersih, tanpa losion
- Lengan **diam** di paha/meja; hanya mulut bergerak saat blok 2
- **Lengan dan posisi yang sama** di ketiga blok — konsistensi lebih penting daripada optimalitas
- Uji pada diri sendiri dulu sebelum melibatkan orang lain

---

## 7. Keterbatasan & Solusi

Melanjutkan seri `L` di BACKLOG.md.

| ID | Keterbatasan | Solusi | Jenis |
|---|---|---|---|
| L13 | **Deteksi puncak terjadi di firmware tertutup**, bukan oleh kode proyek ini. Protzen dkk. menemukan penyaringan menurunkan kesepakatan antar-perangkat — indikasi perbedaan pemrosesan internal | (a) catat merek/model/firmware tiap sesi (sejajar U4.4); (b) gerbang outlier sebagai QC empiris; (c) nyatakan Tahap 1 divalidasi di WESAD sedangkan sesi live memakai RR sensor | ukur + tulis |
| L14 | **Web Bluetooth tidak tersedia di iOS/Safari maupun Firefox** | Batasi cakupan; sebut Bluefy/app native sebagai mitigasi | tulis |
| L15 | **Mutu RR bergantung kontak sensor**; elektroda kering atau lengan dingin menaikkan outlier | Gerbang 2 di fase adaptasi + persiapan §6.2 | bangun |
| L16 | **Sebagian perangkat mengirim RR sintetis**; gagal senyap | Deteksi otomatis di Gerbang 1 (§1.5) | bangun |
| L17 | **Baseline rusak merusak seluruh sesi tanpa pesan galat** | Gerbang 3 khusus baseline | bangun |
| L18 | **PPG tidak sanggup RMSSD pada kondisi bicara-di-bawah-tekanan** (Sinichi dkk.; L11) | Penggerbangan metrik menurut §4.2; **ukur harganya** lewat ablasi HR-saja | ukur |
| L19 | **Sebagian perangkat mengimplementasikan HRS tanpa field RR** (mis. Coospo HW706, spek resmi "HRV: No"). Terdaftar di layanan pihak ketiga **bukan** bukti dukungan RR | Verifikasi hanya dari spek resmi, penggunaan terdokumentasi dengan aplikasi HRV, atau uji langsung | tulis |
| L20 | **HW9 mengkuantisasi RR pada 7,8125 ms** (deteksi denyut tepat 128 Hz), bukan ~1 ms seperti disiratkan field BLE. Derau kuantisasi berspektrum lebar sehingga menambah daya di pita HF dan berpotensi menggeser LF/HF | Domain waktu: dampaknya terhitung dan kecil — RMSSD bergeser 0,16 ms pada tingkat istirahat (§3.3) — cukup dilaporkan. Domain frekuensi: **jangan bandingkan LF/HF HW9 dengan LF/HF WESAD** tanpa menyebut perbedaan resolusi ini | ukur + tulis |
| L21 | **Rekaman kehilangan denyut tanpa jejak di gerbang outlier.** Terukur pada uji protokol: 30 lubang, 150,7 dtk, cakupan per blok 88,6% / 90,4% / **75,4%**; hanya 8 dari 30 lubang ikut tertandai T1.5. Kriteria outlier secara struktural buta terhadap lubang waktu | Cakupan waktu kini dihitung `dropouts()` dan ditampilkan per blok berdampingan dengan outlier. Harga terhadap RMSSD terukur ≤ 0,53 ms — yang hilang jumlah sampel, bukan ketepatan. **Tolak blok dengan cakupan < 90%** sebelum menafsirkannya | bangun + ukur |
| L22 | **Baseline melayang sepanjang blok istirahat.** Terukur: RMSSD naik 26,5% dari paruh pertama ke paruh kedua blok istirahat 5 menit (+1,97 ms per segmen), sehingga reaktivitas dan pemulihan sama-sama tidak terbaca (§3.4). Sejalan dengan `analyse_baseline_duration.py` pada WESAD | Perpanjang baseline dan/atau pakai kriteria berhenti otomatis berbasis kestabilan, bukan durasi tetap. **Keputusan ini harus diambil sebelum pengambilan data subjek** — sesudahnya tidak ada perbaikan yang mungkin | putuskan |

**Keterbatasan lama, solusi diperbarui:**

| ID | Solusi |
|---|---|
| L5 (LLM stokastik) | `--consistency` sudah ada — 3 run, laporkan variasi (U4.3) |
| L8 (ketergantungan Gemini) | Catat versi model (U4.4), simpan keluaran mentah (U4.5). **Llama lokal via Ollama** sebagai arah, sitasi Ha dkk. (2026) |
| L12 / T2c.10 (ambang sedang-tinggi) | **HW6** — klaim ilmiah **biner** (tervalidasi, κ 0,678); tiga tingkat tetap di UI sebagai gradasi indikatif berbasis literatur |
| T5.8 (kuota Gemini) | **Aktifkan billing.** ~1.500 token/sesi; 1.000 panggilan ≈ 1,5 juta token ≈ belasan ribu rupiah. Kuota 20/hari menahan U3.2, U3.3, U3.6, T5.6 |

---

## 8. Rencana Kerja

| # | Pekerjaan | Blokir? | Catatan |
|---|---|---|---|
| 1 | **Ablasi HR-saja di WESAD** (lapis 2 §4.1) | Tidak | Tanpa API/perangkat. Kerjakan **sambil menunggu paket** |
| 2 | Beli HW9; jalankan protokol §6 hari perangkat tiba | Ya | Kriteria §6.1 sudah dikunci |
| 3 | Bila HW9 gugur → beli H808S, ulangi protokol; jalankan berpasangan bila keduanya ada | — | Slot perangkat B sudah siap di alat uji |
| 4 | Halaman akuisisi sesi + tiga gerbang | **Ya** | Jalur kritis demo |
| 5 | Endpoint FastAPI → pipeline (skema §5.2) | Ya | |
| 6 | Dashboard bahasa awam + penggerbangan metrik per modalitas | Ya | K4, §4.2 |
| 7 | **Aktifkan billing Gemini** | — | Membuka U3.2, U3.3, U3.6, T5.6 |
| 8 | Ablasi U3.2 (LLM tanpa KB) & U3.3 (chunk acak) | — | Nyaris wajib: judul menyebut RAG |
| 9 | Konsistensi 3 run (U4.3), versi model (U4.4), keluaran mentah (U4.5) | — | |

**Opsional bila tersisa 1–2 minggu — pilot 5–8 orang.** Sesi lengkap, lalu kuesioner dua bagian:
(a) ketegangan yang dirasakan per pertanyaan (skala 1–5) → validasi sistem; (b) kenyamanan
perangkat (skala 1–5 + pertanyaan terbuka) → **bukti empiris untuk argumen dua tingkat**.
Menutup celah terbesar TA: seluruh validasi berasal dari WESAD (TSST laboratorium), sedangkan
produknya orang duduk di kamar menghadap webcam (K17).

**Keputusan terbuka:**

| ID | Pertanyaan |
|---|---|
| HW-Q1 | Aktifkan billing Gemini sekarang? (rekomendasi: ya) |
| HW-Q3 | Pilot kecil dijalankan atau tidak, tergantung sisa waktu |
| HW-Q4 | Ambil teks lengkap versi IJSPP Protzen dkk. — abstrak ECSS sudah cukup untuk angka, tetapi versi jurnal perlu dicek kesamaan kesimpulannya |

---

## 9. Perkakas

| Berkas | Fungsi |
|---|---|
| `frontend/uji-sensor-hrv.html` | Uji cepat satu perangkat: field RR ada/tidak, persentase outlier, tachogram, ekspor CSV/JSON |
| `frontend/uji-protokol-hrv.html` | **Pelaksana protokol tiga blok §6.** Timer + instruksi di layar, deteksi RR sintetis, statistik per blok (outlier, hasil segmen, meanHR, RMSSD), delta istirahat→tertekan, **slot 2 perangkat** dengan satu sumber waktu, ekspor berlabel fase |

Jalankan lewat `python -m http.server` lalu buka via `localhost` — Web Bluetooth menolak `file://`.

---

## 10. Daftar Pustaka

**Validitas perangkat**
1. Protzen, G., Riesco-Villar, J., González-Fernández, A., Escribano-Pascual, A., & Boullosa, D. (2025). *Is the low-cost Coospo H808S as reliable as the Polar H10 chest strap HR monitor?* ECSS Rimini, Book of Abstracts, hlm. 268. Versi jurnal: *Limited Validity of the Low-Cost Coospo H808S Heart-Rate Monitor Compared to the Polar H10*, IJSPP. PMID 40615117.
2. Schaffarczyk, M., dkk. (2022). *Validity of the Polar H10 Sensor for HRV Analysis during Resting State and Incremental Exercise*. Sensors, 22(17), 6536. https://www.mdpi.com/1424-8220/22/17/6536
3. Sinichi, M., Gevonden, M. J., & Krabbendam, L. (2025). *Quality in Question: Assessing the Accuracy of Four Heart Rate Wearables and the Implications for Psychophysiological Research*. Psychophysiology, 62, e70004.
4. *A Systematic Review of Chest-Worn Sensors in Cardiac Assessment* (2025). Sensors, 25(19), 6049. https://www.mdpi.com/1424-8220/25/19/6049

**Arsitektur akuisisi**
5. Hilbel, T., dkk. (2021). *Analysis and postprocessing of ECG or heart rate data from wearable devices beyond the proprietary cloud and app infrastructure of the vendors*. Cardiovascular Digital Health Journal. https://pmc.ncbi.nlm.nih.gov/articles/PMC8890040/
6. De Palma, L., dkk. (2022). *Development of a web-based system for interfacing a portable Bluetooth vital sign monitor*. IEEE MeMeA. https://ieeexplore.ieee.org/document/9856526/

**HRV + LLM / RAG**
7. Gellisch, M., & Burr, B. (2025). *Establishing a real-time biomarker-to-LLM interface*. Frontiers in Digital Health. https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1670464/full
8. Ha, S., Lee, T., Seo, H., Yoon, S., & Lee, H. (2026). *A Selective RAG-Enhanced Hybrid ML-LLM Framework for Efficient and Explainable Fatigue Prediction Using Wearable Sensor Data*. Bioengineering, 13, 58. https://doi.org/10.3390/bioengineering13010058

**rPPG**
9. Woelk, dkk. (2026). *Advancing remote photoplethysmography (rPPG) to facilitate cardiac monitoring in naturalistic settings using webcam technology*. Behavior Research Methods. https://link.springer.com/article/10.3758/s13428-026-02953-x
10. *A comprehensive review of heart rate measurement using remote photoplethysmography and deep learning* (2025). BioMedical Engineering OnLine. https://link.springer.com/article/10.1186/s12938-025-01405-5

**Sumber teknis & implementasi**
11. Web Bluetooth CG — Heart Rate Sensor Demo. https://webbluetoothcg.github.io/demos/heart-rate-sensor/
12. HypeRate Web Bluetooth. https://webbluetooth.hyperate.io/ · https://www.hyperate.io/supported-devices
13. Rutenberg, G. (2026). *Web HR Monitor: Heart Rate and HRV in the Browser*. https://www.guyrutenberg.com/2026/04/04/web-hr-monitor-heart-rate-and-hrv-in-the-browser/
14. `pure-blue-heart` — Polar H10 ECG & HRV dengan HTML5 + Web Bluetooth. https://github.com/benwrk/pure-blue-heart
15. Elite HRV — Compatible Monitors. https://elitehrv.com/heart-variability-monitors-and-elite-hrv-compatible-monitors
16. Coospo — spesifikasi resmi HW9. https://www.coospo.com/products/hw9-armband-heart-rate-monitor
17. Coospo — spesifikasi resmi HW706 ("HRV Support: No"). https://www.coospo.com/products/hw706-armband-heart-rate-monitor
18. Altini, M. — *Coospo HW9 for Heart Rate Variability (HRV) Analysis*. https://marcoaltini.substack.com/p/coospo-hw9-for-heart-rate-variability

**Catatan akses:** butir 3, 6, 8, 9 sudah dibaca teks lengkapnya. Butir 1 baru tersedia sebagai
abstrak konferensi — versi IJSPP masih perlu diambil (HW-Q4).
