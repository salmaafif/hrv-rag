"""
settings.py — Seluruh parameter numerik proyek, terpusat di satu tempat.

Aturan CLAUDE.md: setiap parameter numerik harus punya alasan yang bisa
dijelaskan saat sidang. Karena itu tiap nilai di bawah diberi komentar
alasannya, bukan sekadar angkanya.
"""

from dataclasses import dataclass, field
from pathlib import Path

# ===========================================================================
# JALUR
# ===========================================================================
REPO_DIR = Path(__file__).resolve().parents[3]      # .../hrv-rag
DATA_RAW = REPO_DIR / "data" / "raw"
DATA_PROCESSED = REPO_DIR / "data" / "processed"
KB_DIR = REPO_DIR / "kb"
OUTPUTS_DIR = REPO_DIR / "outputs"

# Dataset WESAD masih tersimpan di luar repo pada komputer Salma.
# Loader mencoba data/raw dulu, baru jatuh ke lokasi ini.
WESAD_FALLBACK = Path.home() / "Documents" / "WESAD"


# ===========================================================================
# SEGMENTASI
# ===========================================================================
@dataclass(frozen=True)
class SegmentationConfig:
    """Parameter pembagian deret interval menjadi segmen analisis."""

    # 60 detik: kompromi standar untuk HRV ultra-short-term. Cukup panjang agar
    # RMSSD stabil, cukup pendek untuk memisahkan respons antar pertanyaan.
    length_sec: int = 60

    # Overlap 30 detik (jendela geser). Menggandakan resolusi waktu menjadi
    # 30 detik tanpa memperpendek jendela analisis. KONSEKUENSI: segmen
    # bertetangga berbagi separuh data, jadi TIDAK independen — ini harus
    # disebut saat melaporkan metrik (lihat BACKLOG L2).
    overlap_sec: int = 30

    # Segmen dengan denyut lebih sedikit dari ini dibuang. 30 denyut per
    # 60 detik setara HR 30 bpm — di bawah itu hampir pasti gagal deteksi,
    # bukan kondisi fisiologis nyata.
    min_beats: int = 30

    @property
    def hop_sec(self) -> int:
        """Jarak geser antar segmen (detik)."""
        return self.length_sec - self.overlap_sec


# ===========================================================================
# KUALITAS SINYAL & KOREKSI EKTOPIK
# ===========================================================================
@dataclass(frozen=True)
class QualityConfig:
    """Ambang penolakan sinyal dan denyut bermasalah."""

    # Batas fisiologis RR. 0,3 dtk = 200 bpm, 2,0 dtk = 30 bpm. Di luar
    # rentang ini hampir pasti artefak, bukan denyut sungguhan.
    rr_min_sec: float = 0.30
    rr_max_sec: float = 2.00

    # Selisih maksimum terhadap interval sebelumnya yang masih dianggap
    # wajar. HRV normal berubah bertahap; lompatan >20% menandakan denyut
    # ektopik atau puncak R yang salah terdeteksi. (Kriteria Malik.)
    max_rel_diff: float = 0.20

    # Bila lebih dari 10% denyut dalam satu segmen bermasalah, segmen itu
    # dibuang seluruhnya. Menginterpolasi terlalu banyak denyut berarti
    # fitur HRV lebih banyak berasal dari tebakan daripada dari pengukuran.
    max_outlier_ratio: float = 0.10

    # --- Quality check pada sinyal mentah ---
    # Proporsi sampel yang menempel di nilai ekstrem (clipping ADC).
    max_clipping_ratio: float = 0.01
    # Panjang jendela (detik) untuk mendeteksi sinyal datar/lepas elektroda.
    flatline_window_sec: float = 2.0
    # Proporsi durasi flat-line yang masih ditoleransi.
    max_flatline_ratio: float = 0.05


# ===========================================================================
# FILTER PER MODALITAS
# ===========================================================================
@dataclass(frozen=True)
class ECGFilterConfig:
    """
    Filter cabang ECG.

    Bandpass 0,5-40 Hz: membuang drift baseline akibat napas/gerakan (<0,5 Hz)
    dan derau otot/frekuensi tinggi (>40 Hz), sambil mempertahankan kompleks
    QRS yang energinya terpusat di 10-25 Hz.
    """

    lowcut_hz: float = 0.5
    highcut_hz: float = 40.0
    # Orde 2 sesuai CLAUDE.md. Orde rendah = respons fase lebih landai dan
    # lebih stabil secara numerik; ketajaman transisi tidak kritis di sini.
    order: int = 2
    # Notch 50 Hz: frekuensi jala-jala listrik Indonesia (PLN).
    notch_hz: float = 50.0
    # Faktor kualitas notch. Q=30 memberi pita henti sempit, sehingga
    # komponen sinyal di sekitar 50 Hz tidak ikut terpangkas.
    notch_q: float = 30.0


@dataclass(frozen=True)
class PPGFilterConfig:
    """
    Filter cabang PPG (dipakai Tahap 6).

    Pita 0,5-8 Hz jauh lebih sempit daripada ECG karena gelombang PPG
    berbentuk landai dan tidak punya komponen setajam QRS. Melewatkan
    frekuensi tinggi hanya akan memasukkan derau.
    """

    lowcut_hz: float = 0.5
    highcut_hz: float = 8.0
    order: int = 2


# ===========================================================================
# FITUR DOMAIN FREKUENSI
# ===========================================================================
@dataclass(frozen=True)
class FrequencyConfig:
    """
    Pita frekuensi standar Task Force ESC/NASPE (1996).

    Keputusan K2: LF/HF dihitung DUA cara berdampingan (Welch setelah
    interpolasi 4 Hz, dan Lomb-Scargle langsung pada deret tak seragam),
    lalu dibandingkan sebagai bahan pembahasan sidang.
    """

    lf_band: tuple[float, float] = (0.04, 0.15)
    hf_band: tuple[float, float] = (0.15, 0.40)

    # 4 Hz: laju resampling lazim untuk HRV. Jauh di atas Nyquist pita HF
    # (0,4 Hz) sehingga tidak terjadi aliasing, tapi tidak boros.
    resample_hz: float = 4.0


# ===========================================================================
# DINAMIKA: PEMULIHAN & KETAHANAN
# ===========================================================================
@dataclass(frozen=True)
class DynamicsConfig:
    """Parameter perhitungan pemulihan dan pengelompokan ketahanan."""

    # Pemulihan hanya dihitung bila simpangan saat pertanyaan cukup berarti.
    # Rumus pemulihan membagi dengan (nilai_tertekan - baseline); kalau
    # penyebutnya mendekati nol, hasilnya meledak jadi angka tak bermakna
    # (mis. -278%). Ambang 10% menyaring kasus itu, dan hasilnya dilaporkan
    # "tidak dapat dihitung" — bukan diisi nol, karena nol berarti
    # "tidak pulih sama sekali" dan itu klaim yang berbeda.
    min_deviation_ratio: float = 0.10

    # Ambang pemisah kuadran ketahanan. Nilai awal ini masih SEMENTARA dan
    # harus dikalibrasi memakai lima subjek pengembangan saja (BACKLOG U4.1),
    # lalu dibekukan sebelum subjek uji disentuh.
    reactivity_threshold_pct: float = 20.0   # |perubahan| RMSSD dianggap besar
    recovery_threshold_pct: float = 50.0     # >= dianggap pulih cepat

    # Fitur acuan untuk pemulihan dan ketahanan. RMSSD dipilih karena
    # knowledge base menyebutnya paling andal pada segmen 60 detik.
    primary_feature: str = "rmssd"


# ===========================================================================
# PROTOKOL SESI (disetujui — lihat BACKLOG K9 & Q1/Q2)
# ===========================================================================
@dataclass(frozen=True)
class SessionConfig:
    """
    Linimasa sesi wawancara. Semua durasi dalam detik.

    Angka-angka ini bukan selera UX — semuanya terikat panjang segmen 60 dtk.
    Fase yang lebih pendek dari 60 detik tidak menghasilkan segmen sama sekali.
    """

    # Dibuang, tidak dihitung. Memberi waktu detak jantung turun ke kondisi
    # duduk tenang setelah pengguna memasang alat dan menyiapkan diri.
    adaptation_sec: int = 60

    # Baseline personal. 240 dtk menghasilkan 7 segmen, cukup agar median-nya
    # tahan terhadap satu-dua segmen berisik.
    calibration_sec: int = 240

    # Fase antisipasi tingkat sesi (K9). 120 dtk menghasilkan 3 segmen.
    # Antisipasi PER PERTANYAAN sengaja tidak diukur: jendelanya (5-10 dtk)
    # jauh di bawah resolusi 60 detik, jadi tidak akan pernah terukur.
    briefing_sec: int = 120

    # Durasi menjawab satu pertanyaan -> 2 segmen.
    answer_sec: int = 90

    # Jeda setelah pertanyaan SULIT -> tepat 1 segmen pemulihan.
    # 60 dtk adalah lantai keras: di bawah ini pemulihan tidak bisa dihitung.
    recovery_gap_sec: int = 60

    # Jeda setelah pertanyaan biasa. Terlalu pendek untuk menghasilkan segmen,
    # jadi pemulihan untuk pertanyaan ini memang TIDAK dilaporkan (bukan nol).
    short_gap_sec: int = 20


# ===========================================================================
# PEMBAGIAN SUBJEK (BACKLOG U4.1 — cegah prompt overfitting)
# ===========================================================================
@dataclass(frozen=True)
class SplitConfig:
    """
    Pemisahan subjek pengembangan vs pengujian.

    Meski tidak ada model yang dilatih, menyetel prompt dan KB sambil melihat
    hasil TETAP bentuk fitting. Karena itu subjek uji disegel sejak awal.

    Pembagian PER SUBJEK, tidak pernah per segmen: baseline dihitung per
    subjek, jadi segmen milik orang yang sama berbagi acuan — memisahkannya
    per segmen akan membocorkan informasi.

    Subjek pengembangan dipilih menyebar (bukan S2-S6 berurutan), karena
    urutan penomoran bisa berkorelasi dengan urutan perekaman.
    """

    dev_subjects: tuple[str, ...] = ("S2", "S6", "S10", "S14", "S17")
    test_subjects: tuple[str, ...] = (
        "S3", "S4", "S5", "S7", "S8", "S9", "S11", "S13", "S15", "S16",
    )


# ===========================================================================
# OBJEK KONFIGURASI TUNGGAL
# ===========================================================================
@dataclass(frozen=True)
class Settings:
    """Wadah seluruh konfigurasi; dipakai dengan `from ... import settings`."""

    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    ecg_filter: ECGFilterConfig = field(default_factory=ECGFilterConfig)
    ppg_filter: PPGFilterConfig = field(default_factory=PPGFilterConfig)
    frequency: FrequencyConfig = field(default_factory=FrequencyConfig)
    dynamics: DynamicsConfig = field(default_factory=DynamicsConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    split: SplitConfig = field(default_factory=SplitConfig)


settings = Settings()
