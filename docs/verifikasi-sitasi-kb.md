# Verifikasi Sitasi Knowledge Base (`kb_v2.0`) — Rujukan 4–14

**Tanggal pengerjaan:** 2 September 2026
**Objek:** 11 rujukan bertanda ⚠ di bagian "## Sources" `knowledge_base/knowledge_base_HRV.md` (nomor 4–14), belum pernah diverifikasi terhadap teks aslinya.

> **Peringatan jujur.** Ini verifikasi **berbantuan** (dikerjakan lewat penelusuran
> daring oleh agen AI, terutama abstrak dan — bila open access — teks penuh).
> Salma **tetap wajib membuka sendiri** setiap rujukan yang vonisnya **bukan
> SUPPORTS** sebelum dipakai di laporan TA, dan sebaiknya membaca sekilas semua
> rujukan sebelum sidang. Untuk rujukan berbayar (paywall), hanya abstrak yang
> terbaca — hal itu dicatat eksplisit di vonisnya.
>
> Sumber verifikasi utama: Europe PMC REST API (metadata + abstrak MEDLINE),
> Crossref API (metadata), Semantic Scholar API, dan halaman penerbit yang
> terbuka. Semua diakses 2 September 2026. Beberapa halaman gagal diambil dan
> dicatat apa adanya:
> - `internationaljournalofcardiology.com` → HTTP 403 (diganti Europe PMC)
> - `pubmed.ncbi.nlm.nih.gov` → terblokir dinding cookie (diganti Europe PMC)
> - `link.springer.com` → redirect 303 ke halaman otorisasi cookie (diganti Europe PMC)
> - Europe PMC REST sempat 502/503 berulang → berhasil setelah diulang

**Cara membaca vonis:**
- **SUPPORTS** — semua klaim penting di chunk pengutip terkonfirmasi pada teks yang terbaca.
- **PARTIAL** — sebagian klaim terkonfirmasi; sisanya tidak ada di teks yang terbaca (dijelaskan bagian mana).
- **MISMATCH** — isi paper bertentangan dengan klaim chunk.
- **NOT FOUND** — paper tidak ditemukan / metadata tidak cocok dengan paper mana pun.

Catatan pemetaan: di `kb_v2.0` semua sitasi berada di baris header
`**References:**` tiap chunk (tidak ada sitasi inline di badan chunk).
Pemetaan chunk pengutip di bawah ini hasil pembacaan seluruh 23 chunk.

---

## 4. Schäfer & Vagedes (2013) — PRV vs HRV

**Metadata terverifikasi:**
Schäfer, A., & Vagedes, J. (2013). *How accurate is pulse rate variability as an
estimate of heart rate variability? **A review on studies comparing
photoplethysmographic technology with an electrocardiogram.*** International
Journal of Cardiology, 166(1), 15–29.
**DOI:** 10.1016/j.ijcard.2012.03.119 · PMID 22809539
Sumber: Europe PMC (https://europepmc.org/article/MED/22809539), diakses 2 Sep 2026.

**Koreksi metadata:** KB memotong subjudul ("A review on studies comparing
photoplethysmographic technology with an electrocardiogram"). Volume, nomor,
halaman, tahun semuanya benar.

**Chunk pengutip:** `KB-MODAL-01`, `KB-MODAL-02`.

**Vonis: PARTIAL** (klaim arah utama terdukung eksplisit di abstrak; detail
mekanisme belum terverifikasi karena teks penuh berbayar — hanya abstrak yang terbaca).

**Bukti (abstrak, Europe PMC, 2 Sep 2026):**
- ECG sebagai acuan (KB-MODAL-01): "The gold standard technique comprises
  analyzing time series of RR intervals" (dari sinyal elektrokardiografik).
- Kesetaraan saat diam (KB-MODAL-02): "sufficient accuracy when subjects are at rest".
- Degradasi saat bergerak/tertekan (KB-MODAL-02): "Physical activity and some
  mental stressors seem to impair the agreement" — bahkan "often to an
  inacceptable extent".

**Yang TIDAK terverifikasi dari abstrak:**
- Klaim KB-MODAL-01 soal bentuk puncak ("systolic peaks with a gentle shape",
  ketepatan waktu detak lebih rendah) — fisiologi standar, tetapi tidak ada di abstrak.
- Klaim mekanisme KB-MODAL-02 bahwa divergensi saat tertekan disebabkan
  perubahan tekanan darah/tonus vaskular yang mengubah *pulse transit time* —
  abstrak hanya menyebut "coupling effects between respiration and the
  cardiovascular system" untuk overestimasi saat istirahat. Mekanisme PTT
  kemungkinan besar dibahas di teks penuh, tapi itu harus dicek langsung.

---

## 5. Bernardi et al. (2000) — efek bicara pada HRV

**Metadata terverifikasi:**
Bernardi, L., Wdowczyk-Szulc, J., Valenti, C., Castoldi, S., Passino, C.,
Spadacini, G., & Sleight, P. (2000). *Effects of controlled breathing, mental
activity and mental stress with or without verbalization on heart rate
variability.* Journal of the American College of Cardiology, 35(6), 1462–1469.
**DOI:** 10.1016/S0735-1097(00)00595-7 · PMID 10807448
Sumber: Europe PMC (https://europepmc.org/article/MED/10807448); juga terindeks
di https://pubmed.ncbi.nlm.nih.gov/10807448/ dan JACC
(https://www.jacc.org/doi/abs/10.1016/s0735-1097(00)00595-7). Diakses 2 Sep 2026.

**Koreksi metadata:** tidak ada — semua cocok.

**Chunk pengutip:** `KB-CONF-02`, `KB-INTERP-02`.

**Vonis: PARTIAL — INI RUJUKAN YANG PALING PERLU DIPERIKSA SALMA.**

**Yang terdukung:** klaim inti bahwa bicara mengubah pola napas dan mengacaukan
tafsir HRV. Abstrak: aktivitas mental dan verbal sederhana "markedly affect HRV
through changes in respiratory frequency", dan bicara membuat frekuensi napas
bergeser lebih lambat (masuk pita LF) — konsisten dengan "breaths become
deeper, slower, and irregular" di KB-CONF-02.

**Yang TIDAK terdukung (dan ini serius):** KB-CONF-02 menulis bahwa perubahan
napas saat bicara "can **increase** HF power and RMSSD". Abstrak Bernardi
melaporkan arah yang justru sebaliknya untuk HF ternormalisasi: bicara bebas,
membaca keras, dan aritmetika lisan "shifted the respiratory frequency into the
LF band, thus increasing LF%" dan "decreasing HF%" — HF% **turun**, LF% naik,
mean RR turun (jantung lebih cepat), dengan "minor differences in crude RR
variability". RMSSD tidak dilaporkan di abstrak sama sekali.

**Implikasi untuk KB:** skenario "RMSSD dan HF naik saat bicara" di KB-CONF-02
dan KB-INTERP-02 mungkin masih bisa dipertahankan lewat literatur RSA (napas
lambat-dalam memperbesar RSA; lihat Grossman & Taylor), tetapi **tidak bisa
disitasikan ke Bernardi (2000)** tanpa membaca teks penuhnya — abstraknya
menunjuk arah lain (bicara membuat pola spektrum justru MENIRU stres: LF% naik,
HF% turun). Kalau teks penuh tidak menyelamatkan klaim ini, kalimat di
KB-CONF-02 harus direvisi atau sitasi diganti. Jangan pakai di laporan TA
sebelum ini dituntaskan.

**Catatan tambahan:** abstrak juga menyebut membaca dalam hati "increased the
speed of breathing" — sekali lagi bukan "slower". Yang melambat adalah napas
saat bicara bersuara.

---

## 6. Laborde, Mosley & Thayer (2017) — rekomendasi metodologi HRV

**Metadata terverifikasi:**
Laborde, S., Mosley, E., & Thayer, J. F. (2017). *Heart Rate Variability and
Cardiac Vagal Tone in Psychophysiological Research — Recommendations for
Experiment Planning, Data Analysis, and Data Reporting.* Frontiers in
Psychology, 8, 213.
**DOI:** 10.3389/fpsyg.2017.00213 · PMID 28265249 · PMC5316555 (open access)
Sumber: Europe PMC + teks penuh PMC
(https://pmc.ncbi.nlm.nih.gov/articles/PMC5316555/), diakses 2 Sep 2026.

**Koreksi metadata:** tidak ada — semua cocok.

**Chunk pengutip:** `KB-REACT-01`, `KB-RECOV-01`, `KB-RECOV-02`, `KB-RESIL-01`,
`KB-CONF-01`, `KB-INTERP-02`, `KB-ETHIC-01`. (Rujukan yang paling banyak
dikutip di KB — 7 chunk.)

**Vonis: PARTIAL** (konsep-konsep inti terdukung kuat oleh teks penuh; tetapi
rumus recovery, ambang validitas 10%, dan taksonomi resiliensi empat kategori
adalah konstruksi KB sendiri, TIDAK ada di paper).

**Yang terdukung (teks penuh, diakses 2 Sep 2026):**
- Kerangka reactivity/recovery (KB-REACT-01, KB-RECOV-01): paper memperkenalkan
  "the three Rs of HRV: resting, reactivity, recovery" — reactivity = perubahan
  baseline→event, recovery = perubahan task→post-event.
- Perubahan boleh dinyatakan persentase (KB-REACT-01): "reported in absolute
  values, or in percentage".
- Daftar confounder (KB-CONF-01): teks penuh memuat daftar variabel stabil dan
  transien — "Age and gender", "Smoking", "Habitual levels of alcohol
  consumption", obat kardioaktif, larangan kopi/teh 2 jam sebelum eksperimen,
  dan pembahasan panjang soal postur saat baseline. Usia, jenis kelamin, napas,
  postur, kafein/nikotin di KB-CONF-01 semuanya tercakup.
- Bonus yang relevan untuk KB-RMSSD-01: "RMSSD is relatively free of
  respiratory influences".

**Yang TIDAK ada di paper:**
- **Rumus recovery** (S−R)/(S−B) × 100% di KB-RECOV-02 — paper hanya bilang
  perubahan bisa absolut atau persentase; rumus spesifik itu desain sistem ini
  sendiri.
- **Ambang "deviasi < 1/10 baseline → recovery tidak bisa dihitung"** di
  KB-RECOV-02 — tidak ada di paper.
- **Taksonomi resiliensi empat kategori** di KB-RESIL-01 — kata "resilience"
  bahkan tidak muncul sekali pun di teks penuh (0 hit).

**Implikasi:** konstruksi-konstruksi itu sah sebagai keputusan desain, tetapi di
laporan TA harus ditulis sebagai **desain sendiri yang diturunkan dari kerangka
Laborde**, bukan sebagai sesuatu yang bersumber dari Laborde. Kalau penguji
membuka papernya dan tidak menemukan rumus itu, kredibilitas sitasi lain ikut
dipertanyakan.

---

## 7. Billman (2013) — kritik rasio LF/HF

**Metadata terverifikasi:**
Billman, G. E. (2013). *The LF/HF ratio does not accurately measure cardiac
sympatho-vagal balance.* Frontiers in Physiology, 4, 26.
**DOI:** 10.3389/fphys.2013.00026 · PMID 23431279 · PMC3576706 (open access)
Sumber: halaman Frontiers
(https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2013.00026/full)
+ Crossref, diakses 2 Sep 2026.

**Koreksi metadata:** tidak ada — semua cocok.

**Chunk pengutip:** `KB-LFHF-02`.

**Vonis: SUPPORTS.**

**Bukti (teks artikel Frontiers, 2 Sep 2026):**
- LF bukan penanda simpatis murni (klaim KB "LF does not purely reflect
  sympathetic activity"): LF power "reflects a complex and not easily
  discernible mix of sympathetic, parasympathetic" dan faktor lain.
- Masalah rasio (klaim KB "hard to tell whether the numerator or the
  denominator moved"): nilai LF/HF serupa bisa muncul via "exclusive changes in
  the numerator (i.e., LF), or the denominator".

Kedua kalimat kunci KB-LFHF-02 praktis parafrase langsung dari argumen inti
paper ini. Ini sitasi yang paling bersih di antara kesebelasnya.

---

## 8. Kirschbaum, Pirke & Hellhammer (1993) — TSST

**Metadata terverifikasi:**
Kirschbaum, C., Pirke, K.-M., & Hellhammer, D. H. (1993). *The 'Trier Social
Stress Test' — a tool for investigating psychobiological stress responses in a
laboratory setting.* Neuropsychobiology, 28(1–2), 76–81.
**DOI:** 10.1159/000119004 · PMID 8255414
Sumber: Europe PMC (https://europepmc.org/article/MED/8255414), diakses 2 Sep 2026.

**Koreksi metadata:** tidak ada — semua cocok (judul asli memakai tanda kutip
pada 'Trier Social Stress Test'; kosmetik saja).

**Chunk pengutip:** `KB-STRESS-01`.

**Vonis: SUPPORTS** (untuk klaim yang memang disandarkan padanya).

**Bukti (abstrak, Europe PMC, 2 Sep 2026):**
- Deskripsi protokol (klaim KB "combines speaking in front of evaluators with
  an arithmetic task"): subjek harus "deliver a free speech and perform mental
  arithmetic in front of an audience".
- Respons fisiologis: TSST memicu "significant increases in heart rate" dan
  kenaikan kortisol 2–4 kali lipat — mendukung frasa "heart rate increases"
  dalam pola KB-STRESS-01.

**Catatan:** paper ini TIDAK mengukur HRV (yang diukur: ACTH, kortisol, GH,
prolaktin, heart rate). Pola HRV lengkap di KB-STRESS-01 (RMSSD↓, HF↓, SDNN↓,
LF/HF↑) bersandar pada dua rujukan pendampingnya, Castaldo (2015) dan Kim
(2018) — dan keduanya memang mendukung (lihat nomor 13 dan 14). Jadi pembagian
beban sitasi di chunk ini sehat.

---

## 9. Thayer & Lane (2009) — neurovisceral integration

**Metadata terverifikasi:**
Thayer, J. F., & Lane, R. D. (2009). *Claude Bernard and the heart–brain
connection: **further elaboration of a model of neurovisceral integration.***
Neuroscience & Biobehavioral Reviews, 33(2), 81–88.
**DOI:** 10.1016/j.neubiorev.2008.08.004 · PMID 18771686
Sumber: Europe PMC (https://europepmc.org/article/MED/18771686), diakses 2 Sep 2026.

**Koreksi metadata:** KB memotong subjudul ("further elaboration of a model of
neurovisceral integration"). Volume, nomor, halaman, tahun benar.

**Chunk pengutip:** `KB-LEVEL-01` (sebagai "Thayer & Lane (2009)") dan
`KB-COGN-01` (sebagai "**Thayer et al.** (2009)" — bentuk penulis tidak
konsisten; lihat catatan).

**Vonis: SUPPORTS** (dengan catatan konsistensi sitasi).

**Bukti (abstrak, Europe PMC, 2 Sep 2026):**
- Untuk KB-LEVEL-01 (HRV tinggi = kapasitas adaptif, HRV rendah = buruk):
  paper mengulas peran vagally mediated HRV dalam regulasi proses fisiologis,
  afektif, kognitif, dan "Low HRV is a risk factor for pathophysiology and
  psychopathology".
- Untuk KB-COGN-01 (jalur kontrol kortikal prefrontal ke jantung): paper
  mengulas "inhibitory GABAergic pathways from the prefrontal cortex to the
  amygdala" yang bermuara pada modulasi heart rate dan HRV.

**Catatan koreksi:**
1. KB-COGN-01 menulis "Thayer et al. (2009)" padahal penulisnya dua orang —
   harus "Thayer & Lane (2009)", ATAU memang yang dimaksud paper lain: Thayer
   et al. (2009), *Heart rate variability, prefrontal neural function, and
   cognitive performance...*, Annals of Behavioral Medicine 37(2), 141–153 —
   yang untuk konteks beban kognitif justru lebih tepat. Salma perlu memutuskan
   paper mana yang dimaksud, lalu menyeragamkan; saat ini daftar Sources hanya
   memuat versi Thayer & Lane.
2. Daftar Sources KB menulis nama jurnal "Neuroscience & Biobehavioral
   Reviews" — nama resmi memakai "and"; sesuaikan dengan gaya selingkung PENS.

---

## 10. Quintana & Heathers (2014) — pertimbangan asesmen HRV

**Metadata terverifikasi:**
Quintana, D. S., & Heathers, J. A. J. (2014). *Considerations in the assessment
of heart rate variability in biobehavioral research.* Frontiers in Psychology,
5, 805.
**DOI:** 10.3389/fpsyg.2014.00805 · PMID 25101047 · PMC4106423 (open access)
Sumber: Crossref + Semantic Scholar + teks penuh PMC
(https://pmc.ncbi.nlm.nih.gov/articles/PMC4106423/), diakses 2 Sep 2026.

**Koreksi metadata:** tidak ada — semua cocok.

**Chunk pengutip:** `KB-CONF-01`, `KB-AROUS-01`, `KB-ETHIC-01`.

**Vonis: PARTIAL.**

**Yang terdukung (abstrak + teks penuh, 2 Sep 2026):**
- KB-CONF-01 (confounder napas, keunggulan perbandingan dalam-diri): paper
  menekankan "superior utility of within-subjects designs" serta "importance of
  establishing an appropriate baseline and monitoring respiration". Teks penuh:
  desain within-subjects "offers optimal experimental control".
- KB-ETHIC-01 (hasil dipengaruhi kualitas metodologi → butuh kehati-hatian):
  terdukung secara umum sebagai paper kehati-hatian metodologis.

**Yang TIDAK terdukung:**
- **KB-AROUS-01** — klaim bahwa arousal bersifat *valence-neutral* (gembira,
  antusias, dan marah sama-sama menaikkan arousal dan menurunkan HRV) **tidak
  ada di paper ini**. Kata "arousal" tidak muncul sekali pun di teks penuh
  (0 hit); "valence" hanya muncul sekali dalam konteks lain (variabilitas napas
  pada tugas sosial-emosional). Konsep arousal–valence itu dari literatur emosi
  (model sirkumpleks Russell), bukan dari Quintana & Heathers. KB-AROUS-01 juga
  mengutip Shaffer & Ginsberg (2017) — di luar lingkup verifikasi ini — tetapi
  klaim valence-neutrality kemungkinan butuh sitasi tambahan yang tepat.
- Isi etika spesifik KB-ETHIC-01 (bukan diagnosis klinis, umpan balik sebagai
  perilaku yang bisa dilatih) adalah framing sistem ini sendiri, bukan isi paper.

---

## 11. Grossman & Taylor (2007) — respiratory sinus arrhythmia

**Metadata terverifikasi:**
Grossman, P., & Taylor, E. W. (2007). *Toward understanding respiratory sinus
arrhythmia: **relations to cardiac vagal tone, evolution and biobehavioral
functions.*** Biological Psychology, 74(2), 263–285.
**DOI:** 10.1016/j.biopsycho.2005.11.014 · PMID 17081672
Sumber: Europe PMC (https://europepmc.org/article/MED/17081672) + Crossref,
diakses 2 Sep 2026.

**Koreksi metadata:** KB memotong subjudul ("relations to cardiac vagal tone,
evolution and biobehavioral functions"). Volume, nomor, halaman, tahun benar.

**Chunk pengutip:** `KB-CONF-02`.

**Vonis: SUPPORTS** (klaim yang disandarkan padanya terkonfirmasi langsung di
abstrak; teks penuh berbayar, tidak dibuka).

**Bukti (abstrak, Europe PMC, 2 Sep 2026):**
- Klaim KB "the HF band is driven by respiration" / napas mengacaukan tafsir
  vagal: caveat #1 paper — "Respiratory parameters can confound relations
  between RSA and cardiac vagal tone."
- Paper juga mencatat RSA dan tonus vagal "can dissociate under certain
  circumstances" — sejalan dengan kehati-hatian KB-CONF-02.

**Catatan:** klaim spesifik tentang *bicara* (bukan sekadar napas) di
KB-CONF-02 bersandar pada Bernardi (2000), yang vonisnya PARTIAL — lihat
nomor 5. Grossman & Taylor menanggung bagian "napas mengendalikan HF/RSA",
dan bagian itu aman.

---

## 12. Hjortskov et al. (2004) — stres mental saat kerja komputer

**Metadata terverifikasi:**
Hjortskov, N., Rissén, D., Blangsted, A. K., Fallentin, N., Lundberg, U., &
Søgaard, K. (2004). *The effect of mental stress on heart rate variability and
blood pressure during computer work.* European Journal of Applied Physiology,
92(1–2), 84–89.
**DOI:** 10.1007/s00421-004-1055-z · PMID 14991326
Sumber: Europe PMC (https://europepmc.org/article/MED/14991326) + Crossref,
diakses 2 Sep 2026. (Halaman Springer redirect ke dinding cookie; tidak dibuka.)

**Koreksi metadata:** tidak ada — semua cocok.

**Chunk pengutip:** `KB-COGN-01`.

**Vonis: PARTIAL** (klaim "menurunkan HRV" terdukung eksplisit; klaim "menaikkan
heart rate" tidak muncul di abstrak — hanya abstrak yang terbaca).

**Bukti (abstrak, Europe PMC, 2 Sep 2026):**
- HRV turun saat stres mental (klaim KB "lowers HRV"): terjadi "a reduction in
  the high-frequency component of HRV" dan "an increase in the low- to
  high-frequency ratio" pada kondisi stres dibanding kontrol.
- Kesimpulan paper: "HRV is a more sensitive and selective measure of mental
  stress" (dibanding tekanan darah).

**Yang TIDAK terverifikasi dari abstrak:**
- Bagian "raises heart rate" di KB-COGN-01 — abstrak tidak melaporkan heart
  rate; yang naik adalah tekanan darah. Perlu cek teks penuh, atau sandarkan
  kenaikan heart rate pada rujukan lain (Kirschbaum 1993 eksplisit soal ini).
- Perhatikan pula: "No changes were seen in the low-frequency component" —
  yang naik adalah **rasio** LF/HF (karena HF turun), bukan LF sendiri. Ini
  malah amunisi bagus untuk KB-LFHF-02 (masalah pembilang vs penyebut), layak
  disebut di pembahasan TA.
- Klaim jalur prefrontal di kalimat yang sama ditanggung sitasi pendampingnya
  (Thayer — lihat nomor 9), bukan Hjortskov.

---

## 13. Castaldo et al. (2015) — meta-analisis HRV & stres mental akut

**Metadata terverifikasi:**
Castaldo, R., Melillo, P., Bracale, U., Caserta, M., Triassi, M., & Pecchia, L.
(2015). *Acute mental stress assessment via short term HRV analysis in healthy
adults: A systematic review **with meta-analysis.*** Biomedical Signal
Processing and Control, 18, 370–377.
**DOI:** 10.1016/j.bspc.2015.02.012
Sumber: Crossref + Semantic Scholar
(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.bspc.2015.02.012);
teks penuh green OA tersedia di repositori Warwick:
http://wrap.warwick.ac.uk/69425/. Diakses 2 Sep 2026.
(Jurnal ini tidak terindeks MEDLINE, jadi tidak ada PMID.)

**Koreksi metadata:** KB memotong "with meta-analysis" dari judul. Catatan
kecil: Semantic Scholar menulis penulis ketiga "M. Bracale", Crossref
"U. Bracale" — versi penerbit (Crossref/ScienceDirect) yang dipegang: U. Bracale.

**Chunk pengutip:** `KB-STRESS-01`, `KB-INTERP-01`.

**Vonis: SUPPORTS.**

**Bukti (abstrak lengkap via Semantic Scholar, 2 Sep 2026):**
- Fitur domain waktu turun saat stres (klaim KB "RMSSD decreases... SDNN
  decreases"): empat ukuran domain waktu/non-linear "resulted significantly
  depressed during stress".
- HF turun, LF/HF naik: "The power of HRV fluctuations at high frequencies was
  significantly depressed", dan rasio LF/HF "resulted significantly increased".
- Interpretasi arah (dasar KB-INTERP-01): pergeseran keseimbangan otonom
  menuju "the sympathetic activation and the parasympathetic withdrawal".

Meta-analisis atas 12 studi / 758 subjek — landasan yang kuat persis untuk pola
karakteristik yang dituliskan KB-STRESS-01 dan panduan penilaian KB-INTERP-01.

---

## 14. Kim et al. (2018) — meta-analisis stres & HRV

**Metadata terverifikasi:**
Kim, H.-G., Cheon, E.-J., Bai, D.-S., Lee, Y. H., & Koo, B.-H. (2018). *Stress
and Heart Rate Variability: A Meta-Analysis and Review of the Literature.*
Psychiatry Investigation, 15(3), 235–245.
**DOI:** 10.30773/pi.2017.08.17 · PMID 29486547 · PMC5900369 (open access)
Sumber: Europe PMC (https://europepmc.org/article/MED/29486547), diakses 2 Sep 2026.

**Koreksi metadata:** tidak ada — semua cocok. (KB menulis "Kim, H. G., et al."
— penulis lengkap: Kim HG, Cheon EJ, Bai DS, Lee YH, Koo BH.)

**Chunk pengutip:** `KB-STRESS-01`, `KB-INTERP-01`.

**Vonis: SUPPORTS.**

**Bukti (abstrak, Europe PMC, 2 Sep 2026):**
- HF turun saat stres (klaim KB "HF decreases"): faktor yang paling sering
  dilaporkan adalah aktivitas parasimpatis rendah, "a decrease in the
  high-frequency band and an increase in the low-frequency band".
- HRV sebagai indikator stres yang sah (dasar KB-INTERP-01): "HRV is impacted
  by stress and supports its use" untuk asesmen objektif stres psikologis.

**Catatan kecil:** Kim melaporkan **LF naik** saat stres, sementara KB-FREQ-01
(chunk lain, tidak mengutip Kim) menahan diri menafsirkan LF karena sifatnya
campuran. Ini bukan konflik sitasi — chunk yang mengutip Kim hanya memakai
klaim HF dan LF/HF — tetapi bagus disadari kalau penguji menanyakan LF.

---

## Tabel Rekap

| # | Rujukan | Chunk pengutip | Vonis |
|---|---|---|---|
| 4 | Schäfer & Vagedes (2013), Int J Cardiol 166(1) | KB-MODAL-01, KB-MODAL-02 | **PARTIAL** — arah utama terdukung; mekanisme PTT & bentuk puncak tak ada di abstrak (paywall) |
| 5 | Bernardi et al. (2000), JACC 35(6) | KB-CONF-02, KB-INTERP-02 | **PARTIAL** — bicara memang mengacaukan HRV, tapi abstrak melaporkan HF% TURUN, bukan naik seperti klaim KB |
| 6 | Laborde, Mosley & Thayer (2017), Front Psychol 8 | KB-REACT-01, KB-RECOV-01, KB-RECOV-02, KB-RESIL-01, KB-CONF-01, KB-INTERP-02, KB-ETHIC-01 | **PARTIAL** — three Rs & confounder terdukung penuh; rumus recovery, ambang 10%, taksonomi resiliensi TIDAK ada di paper |
| 7 | Billman (2013), Front Physiol 4 | KB-LFHF-02 | **SUPPORTS** |
| 8 | Kirschbaum et al. (1993), Neuropsychobiology 28(1–2) | KB-STRESS-01 | **SUPPORTS** (protokol TSST + kenaikan HR; paper tidak mengukur HRV — pola HRV ditanggung Castaldo & Kim) |
| 9 | Thayer & Lane (2009), Neurosci Biobehav Rev 33(2) | KB-LEVEL-01, KB-COGN-01 | **SUPPORTS** (rapikan "Thayer et al." → "Thayer & Lane", atau tambahkan Thayer et al. 2009 Ann Behav Med) |
| 10 | Quintana & Heathers (2014), Front Psychol 5 | KB-CONF-01, KB-AROUS-01, KB-ETHIC-01 | **PARTIAL** — metodologi terdukung; klaim arousal/valence di KB-AROUS-01 TIDAK ada di paper |
| 11 | Grossman & Taylor (2007), Biol Psychol 74(2) | KB-CONF-02 | **SUPPORTS** (klaim confound napas eksplisit di abstrak; teks penuh paywall) |
| 12 | Hjortskov et al. (2004), Eur J Appl Physiol 92(1–2) | KB-COGN-01 | **PARTIAL** — HRV turun terdukung; "raises heart rate" tak ada di abstrak (paywall) |
| 13 | Castaldo et al. (2015), Biomed Signal Process Control 18 | KB-STRESS-01, KB-INTERP-01 | **SUPPORTS** |
| 14 | Kim et al. (2018), Psychiatry Investig 15(3) | KB-STRESS-01, KB-INTERP-01 | **SUPPORTS** |

**Rekap vonis:** 6 SUPPORTS · 5 PARTIAL · 0 MISMATCH · 0 NOT FOUND.
Semua 11 paper **benar-benar ada** dan metadata bibliografinya (jurnal, volume,
nomor, halaman, tahun, DOI) cocok; selisih hanya pemotongan subjudul pada
nomor 4, 9, 11, 13.

**Prioritas untuk Salma (urutan kepentingan):**
1. **Bernardi (2000)** — buka teks penuhnya; klaim arah HF/RMSSD di KB-CONF-02
   berlawanan dengan abstraknya. Ini satu-satunya kasus yang berpotensi jadi
   MISMATCH betulan.
2. **Laborde (2017)** — di laporan TA, tulis rumus recovery, ambang 10%, dan
   taksonomi resiliensi sebagai desain sendiri, bukan hasil sitasi.
3. **Quintana & Heathers (2014)** — cari sitasi yang tepat untuk klaim
   arousal/valence di KB-AROUS-01 (paper ini bukan sumbernya).
4. **Hjortskov (2004)** dan **Schäfer & Vagedes (2013)** — cek teks penuh untuk
   detail yang belum terverifikasi (kenaikan HR; mekanisme pulse transit time).
