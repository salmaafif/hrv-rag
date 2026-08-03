"""
settings.py — Every numeric parameter in the project, centralised.

CLAUDE.md rule: each numeric parameter must have a reason that can be explained at
the thesis defence. Every value below therefore carries a comment explaining why it
is what it is, not merely what it is.
"""

from dataclasses import dataclass, field
from pathlib import Path

# ===========================================================================
# PATHS
# ===========================================================================
REPO_DIR = Path(__file__).resolve().parents[3]      # .../hrv-rag
DATA_RAW = REPO_DIR / "data" / "raw"
DATA_PROCESSED = REPO_DIR / "data" / "processed"
KB_DIR = REPO_DIR / "kb"
KB_FILE = KB_DIR / "knowledge_base_HRV.md"
KB_INDEX_DIR = DATA_PROCESSED / "kb_index"
OUTPUTS_DIR = REPO_DIR / "outputs"
PROMPTS_DIR = REPO_DIR / "prompts"

# WESAD still lives outside the repo on Salma's machine. The loader tries
# data/raw first and falls back to this location.
WESAD_FALLBACK = Path.home() / "Documents" / "WESAD"


# ===========================================================================
# SEGMENTATION
# ===========================================================================
@dataclass(frozen=True)
class SegmentationConfig:
    """Parameters for splitting an interval series into analysis segments."""

    # 60 seconds: the standard compromise for ultra-short-term HRV. Long enough
    # for RMSSD to stabilise, short enough to separate responses to individual
    # questions.
    length_sec: int = 60

    # 30-second overlap (sliding window). Doubles temporal resolution to 30 s
    # without shortening the analysis window. CONSEQUENCE: neighbouring segments
    # share half their data, so they are NOT independent — this must be stated
    # when reporting metrics (BACKLOG L2).
    overlap_sec: int = 30

    # Segments with fewer beats than this are discarded. 30 beats per 60 seconds
    # equals 30 bpm — below that it is almost certainly failed detection rather
    # than a real physiological state.
    min_beats: int = 30

    @property
    def hop_sec(self) -> int:
        """Distance the window slides between segments (seconds)."""
        return self.length_sec - self.overlap_sec


# ===========================================================================
# SIGNAL QUALITY & ECTOPIC CORRECTION
# ===========================================================================
@dataclass(frozen=True)
class QualityConfig:
    """Rejection thresholds for signals and problematic beats."""

    # Physiological RR bounds. 0.3 s = 200 bpm, 2.0 s = 30 bpm. Outside this
    # range it is almost certainly an artefact rather than a real beat.
    rr_min_sec: float = 0.30
    rr_max_sec: float = 2.00

    # Maximum change from the preceding interval still considered plausible.
    # Normal HRV changes gradually; a jump above 20% signals an ectopic beat or a
    # misdetected R peak. (Malik criterion.)
    max_rel_diff: float = 0.20

    # If more than 10% of beats in a segment are problematic, the whole segment is
    # discarded. Interpolating too many beats means the HRV features come mostly
    # from guesses rather than from measurement.
    max_outlier_ratio: float = 0.10

    # --- Raw-signal quality checks ---
    # Fraction of samples pinned at the extremes of the ADC range (clipping).
    max_clipping_ratio: float = 0.01
    # Window length (seconds) used to detect a flat signal / detached electrode.
    flatline_window_sec: float = 2.0
    # Tolerated fraction of the recording spent flat-lined.
    max_flatline_ratio: float = 0.05


# ===========================================================================
# PER-MODALITY FILTERS
# ===========================================================================
@dataclass(frozen=True)
class ECGFilterConfig:
    """
    ECG branch filter.

    Bandpass 0.5-40 Hz: removes baseline drift from breathing and movement
    (<0.5 Hz) and muscle / high-frequency noise (>40 Hz), while preserving the QRS
    complex whose energy is concentrated around 10-25 Hz.
    """

    lowcut_hz: float = 0.5
    highcut_hz: float = 40.0
    # Order 2 per CLAUDE.md. A low order gives a gentler phase response and better
    # numerical stability; a sharp transition band is not critical here.
    order: int = 2
    # 50 Hz notch: the mains frequency in Indonesia (PLN).
    notch_hz: float = 50.0
    # Notch quality factor. Q=30 gives a narrow stop band, so signal components
    # near 50 Hz are not stripped out along with the interference.
    notch_q: float = 30.0


@dataclass(frozen=True)
class PPGFilterConfig:
    """
    PPG branch filter (used in Stage 6).

    The 0.5-8 Hz band is far narrower than for ECG because the PPG waveform is
    smooth and has nothing as sharp as a QRS complex. Passing higher frequencies
    would only admit noise.
    """

    lowcut_hz: float = 0.5
    highcut_hz: float = 8.0
    order: int = 2


# ===========================================================================
# FREQUENCY-DOMAIN FEATURES
# ===========================================================================
@dataclass(frozen=True)
class FrequencyConfig:
    """
    Standard frequency bands per Task Force ESC/NASPE (1996).

    Decision K2: LF/HF is computed TWO ways side by side (Welch after resampling
    to 4 Hz, and Lomb-Scargle directly on the unevenly sampled series), then
    compared as material for the defence.
    """

    lf_band: tuple[float, float] = (0.04, 0.15)
    hf_band: tuple[float, float] = (0.15, 0.40)

    # 4 Hz: the customary resampling rate for HRV. Comfortably above the Nyquist
    # requirement for the HF band (0.4 Hz) so no aliasing occurs, without waste.
    resample_hz: float = 4.0


# ===========================================================================
# DYNAMICS: RECOVERY & RESILIENCE
# ===========================================================================
@dataclass(frozen=True)
class DynamicsConfig:
    """Parameters for recovery computation and resilience classification."""

    # Recovery is only computed when the deviation during the question is large
    # enough to matter. The formula divides by (stressed - baseline); if that
    # denominator approaches zero the result explodes into meaningless numbers
    # (e.g. -278%). A 10% threshold filters those cases out, and the result is
    # reported as "not computable" — never as zero, because zero would mean
    # "did not recover at all", which is a different claim entirely.
    min_deviation_ratio: float = 0.10

    # Cut-offs separating the resilience quadrants. These starting values are
    # PROVISIONAL and must be calibrated on the five development subjects only
    # (BACKLOG U4.1), then frozen before the test subjects are touched.
    reactivity_threshold_pct: float = 20.0   # |RMSSD change| counted as large
    recovery_threshold_pct: float = 50.0     # >= counted as fast recovery

    # Reference feature for recovery and resilience. RMSSD is chosen because the
    # knowledge base identifies it as the most dependable on 60-second segments.
    primary_feature: str = "rmssd"


# ===========================================================================
# RAG: EMBEDDING & RETRIEVAL
# ===========================================================================
@dataclass(frozen=True)
class RAGConfig:
    """Parameters for indexing the knowledge base and retrieving chunks."""

    # CLAUDE.md originally specified `text-embedding-004`, but that model returns
    # 404 on the API in use. Its replacement is the current Gemini embedding
    # model. This is not a preference — it is a necessity.
    embedding_model: str = "gemini-embedding-001"

    # The model's native dimensionality. For 23 chunks, 23 x 3072 float32 is only
    # ~280 KB, so there is no reason to truncate it to save space.
    embedding_dim: int = 3072

    # Documents and queries are embedded differently because their shapes genuinely
    # differ: a KB chunk is a long explanation, a query is a short feature summary.
    # Telling the model which role each text plays improves matching at no cost.
    task_document: str = "RETRIEVAL_DOCUMENT"
    task_query: str = "RETRIEVAL_QUERY"

    # Number of chunks retrieved per query. Starting value 3; will be swept
    # (k = 1, 3, 5, 7) in ablation U3.4 and then frozen.
    top_k: int = 3

    # Minimum similarity. Chunks below this are treated as irrelevant and dropped,
    # so the context is not padded with material that could mislead the LLM.
    #
    # The value is measured, not guessed. Gemini embeddings produce scores in a
    # narrow band, so a low threshold filters nothing at all. Calibration against
    # the English KB (kb_v2.0) with English queries:
    #     highly relevant query   -> top score 0.807
    #     loosely relevant query  -> top score 0.661
    #     irrelevant queries      -> top score 0.527-0.561
    # So 0.60 sits inside the gap between "irrelevant" and "loosely relevant",
    # with a small margin above the highest irrelevant score.
    #
    # NOTE: calibrated on five sample queries only; must be revisited during the
    # U3.4 sweep and then frozen.
    min_similarity: float = 0.60

    # Chunk pinned into every prompt regardless of the search result, or None to
    # disable pinning.
    #
    # Why this exists: KB-INTERP-01 defines the criteria for low / moderate / high.
    # It is a rubric, not ordinary knowledge, yet it competes with ordinary chunks
    # during retrieval. On the S2 calibration segment it failed to reach the top 3,
    # and the model answered "uncertain" for what was plainly a resting segment —
    # it had no definition of "low" to work from.
    #
    # Left disabled by default so that evaluation can MEASURE whether pinning
    # helps, rather than the question being settled by assumption (BACKLOG T4.7).
    pinned_chunk_id: str | None = None


# ===========================================================================
# LLM GENERATION
# ===========================================================================
@dataclass(frozen=True)
class LLMConfig:
    """Parameters for the interpretation call to Gemini."""

    model: str = "gemini-2.5-flash"

    # Temperature 0.0 for maximum determinism. The LLM is stochastic by nature,
    # so run-to-run consistency must still be MEASURED rather than assumed
    # (BACKLOG T5.4); temperature will also be swept in ablation U3.5.
    temperature: float = 0.0

    # Prompt version. The prompt is part of the system in a RAG design — the
    # equivalent of model architecture in a deep-learning approach — so it lives
    # in a versioned file under prompts/ and must never be edited silently.
    prompt_version: str = "v1"

    # Requests per minute. The Gemini free tier allows only 5 for
    # gemini-2.5-flash; exceeding it returns HTTP 429 and aborts the run partway
    # through, wasting every call already made. The client paces itself to stay
    # underneath. Raise this if billing is enabled.
    requests_per_minute: int = 5

    # Upper bound on the response. Set to 8192 after 2048 proved too small:
    # gemini-2.5-flash spends output tokens on internal reasoning as well, so the
    # JSON was being truncated mid-string and failed to parse. The guard caught it
    # loudly rather than returning half an answer, which is the desired behaviour.
    max_output_tokens: int = 8192


# ===========================================================================
# SESSION PROTOCOL (approved — see BACKLOG K9 & Q1/Q2)
# ===========================================================================
@dataclass(frozen=True)
class SessionConfig:
    """
    Interview session timeline. All durations in seconds.

    These numbers are not a UX preference — every one of them is tied to the
    60-second segment length. A phase shorter than 60 seconds yields no segment
    at all, and therefore no measurement.
    """

    # Discarded, not analysed. Gives heart rate time to settle into a quiet seated
    # state after the user has fitted the device and got ready.
    adaptation_sec: int = 60

    # Personal baseline. 240 s yields 7 segments, enough for the median to resist
    # one or two noisy segments.
    calibration_sec: int = 240

    # Session-level anticipation phase (K9). 120 s yields 3 segments.
    # PER-QUESTION anticipation is deliberately not measured: a 5-10 s window sits
    # far below the 60-second resolution, so it could never be captured.
    briefing_sec: int = 120

    # Time to answer one question -> 2 segments.
    answer_sec: int = 90

    # Gap after a DIFFICULT question -> exactly 1 recovery segment.
    # 60 s is a hard floor: below it, recovery cannot be computed at all.
    recovery_gap_sec: int = 60

    # Gap after an ordinary question. Too short to yield a segment, so recovery
    # for those questions is genuinely NOT REPORTED — as opposed to being zero.
    short_gap_sec: int = 20


# ===========================================================================
# SUBJECT SPLIT (BACKLOG U4.1 — guard against prompt overfitting)
# ===========================================================================
@dataclass(frozen=True)
class SplitConfig:
    """
    Separation of development and test subjects.

    Even though no model is trained, tuning the prompt and the KB while looking at
    results IS a form of fitting. The test subjects are therefore sealed from the
    start.

    The split is PER SUBJECT, never per segment: the baseline is computed per
    subject, so segments belonging to the same person share a reference. Splitting
    per segment would leak information across the boundary.

    Development subjects are spread out rather than sequential (not S2-S6), because
    numbering order may correlate with recording order.
    """

    dev_subjects: tuple[str, ...] = ("S2", "S6", "S10", "S14", "S17")
    test_subjects: tuple[str, ...] = (
        "S3", "S4", "S5", "S7", "S8", "S9", "S11", "S13", "S15", "S16",
    )


# ===========================================================================
# SINGLE CONFIGURATION OBJECT
# ===========================================================================
@dataclass(frozen=True)
class Settings:
    """Container for all configuration; used via `from ... import settings`."""

    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    ecg_filter: ECGFilterConfig = field(default_factory=ECGFilterConfig)
    ppg_filter: PPGFilterConfig = field(default_factory=PPGFilterConfig)
    frequency: FrequencyConfig = field(default_factory=FrequencyConfig)
    dynamics: DynamicsConfig = field(default_factory=DynamicsConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    split: SplitConfig = field(default_factory=SplitConfig)


settings = Settings()
