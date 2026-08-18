"""
settings.py — Every numeric parameter in the project, centralised.

CLAUDE.md rule: each numeric parameter must have a reason that can be explained at
the thesis defence. Every value below therefore carries a comment explaining why it
is what it is, not merely what it is.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

# Safe in this direction only: `core.types` imports nothing from `config`.
from ..core.types import Phase

# ===========================================================================
# PATHS
# ===========================================================================
REPO_DIR = Path(__file__).resolve().parents[3]      # .../hrv-rag
DATA_RAW = REPO_DIR / "data" / "raw"
DATA_PROCESSED = REPO_DIR / "data" / "processed"
KB_DIR = REPO_DIR / "knowledge_base"
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

    # Overlap used for the RESTING phase only, giving a 15-second hop there.
    #
    # The resting period is short by design — asking someone to sit still is dead
    # time before the practice can begin, and four minutes of it is long enough
    # that people stop sitting still. But the personal baseline is the MEDIAN
    # across its windows, and every reactivity percentage in the whole session is
    # divided by that median, so too few windows makes a shaky divisor.
    #
    # Sampling the same minutes more densely is the way out. Over two minutes,
    # a 30-second hop yields only 1-2 windows while a 15-second hop yields 2-4 —
    # roughly what three minutes used to give. It adds no information, because
    # two minutes contains two minutes of data either way; what it adds is a more
    # stable central value drawn from it.
    #
    # Measured on the five development subjects, the finer hop moves the baseline
    # RMSSD by 0.07-1.33% over a full WESAD resting phase, so the validated
    # numbers are unaffected. The one large shift (S10, 20.7% over a two-minute
    # slice) is the subject with the least steady baseline, and there the denser
    # sampling is what lets the median reject a noisy minute rather than average
    # it in — the finer hop corrects the answer rather than disturbing it.
    #
    # The cost, stated plainly: windows now share 75% of their data instead of
    # 50%, so they are even less independent. That is acceptable HERE because
    # they feed a median, which is a robustness device rather than a statistical
    # test. It would NOT be acceptable for the segments being classified, which
    # is why this applies to the resting phase alone.
    baseline_overlap_sec: int = 45

    # Segments with fewer beats than this are discarded. 30 beats per 60 seconds
    # equals 30 bpm — below that it is almost certainly failed detection rather
    # than a real physiological state.
    min_beats: int = 30

    @property
    def hop_sec(self) -> int:
        """Distance the window slides between segments (seconds)."""
        return self.length_sec - self.overlap_sec

    @property
    def baseline_hop_sec(self) -> int:
        """Window slide used for the resting phase (seconds)."""
        return self.length_sec - self.baseline_overlap_sec

    def for_phase(self, phase: Phase) -> "SegmentationConfig":
        """
        The segmentation to use for one phase.

        Written as a method on the config rather than left to each caller,
        because forgetting it would be invisible: the resting phase would simply
        produce fewer windows, the baseline would rest on one or two of them, and
        every percentage afterwards would be quietly less reliable with nothing
        on screen to say so.
        """
        if phase is not Phase.CALIBRATION:
            return self
        return replace(self, overlap_sec=self.baseline_overlap_sec)


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
# BASELINE QUALITY GATE
# ===========================================================================
@dataclass(frozen=True)
class BaselineGateConfig:
    """
    When a resting period is too unsteady to build a personal reference on.

    Mandatory Rule #2 makes every figure in the report a percentage against this
    baseline, so a bad one corrupts the whole session — and it does so SILENTLY.
    No error is raised, no number looks odd; the report is simply describing
    somebody else. That is why this gate exists at all.

    WHAT THE THRESHOLDS ARE AND ARE NOT. Calibrated on 14 August 2026 over 2,820
    baselines drawn from all fifteen WESAD resting phases. For each one the
    quantity a live session CAN see (spread, resting heart rate) was set against
    the one it CANNOT: how far that baseline lands from the subject's twenty-minute
    median. A baseline is counted bad when it misses by more than 20% — the scoring
    rule's own moderate threshold, so those are the ones that can move a label.

    Neither signal predicts that well. Spread correlates with the error at only
    Spearman +0.24, resting heart rate +0.26; a trend test within the window was
    worthless at -0.01 and was dropped. Together, at these values, the gate turns
    away about 10% of sessions and catches about 41% of the genuinely bad ones,
    with roughly half its refusals correct.

    So this is a CATASTROPHE FILTER, not a certificate. It reliably catches the
    person who plainly is not at rest — WESAD S10 sat at 99 bpm and its baselines
    landed 34% off, the worst of the fifteen, and every one of its windows is
    refused. It will let subtler failures through. Passing the gate must never be
    reported as "the baseline is good", only as "nothing obviously wrong was
    visible".

    Per SUBJECT the picture is much stronger (Pearson +0.94): the signals identify
    an unsteady PERSON well and an unsteady four minutes poorly. That is the honest
    limit of a short rest, not a defect of the code.
    """

    # Relative IQR of RMSSD across the calibration windows.
    #
    # THIS NUMBER DEPENDS ON HOW MUCH RECORDING THERE WAS, which is the trap that
    # caught the first calibration of it. Measured on two-minute rests alone, 0.20
    # looked right. But production does not build two-minute baselines: a Bluetooth
    # sensor streams from the moment it pairs, and `split_baseline_and_task` keeps
    # that prelude, so a real baseline spans up to four minutes and about twelve
    # windows rather than four. Twelve windows reveal variability that four
    # conceal, so the same steady person scores a HIGHER spread on the longer and
    # more accurate recording — median 15.5% against 9%. At 0.20 the gate then
    # refused 35% of sessions, most of them wrongly.
    #
    # Swept again across mixed prelude lengths (0, 1 and 2 minutes), which is the
    # range production actually produces. At 0.35 the gate refuses 10.3% and 47% of
    # its refusals are correct; tightening to 0.30 buys three points of recall for
    # five points of precision, and loosening to 0.40 changes almost nothing.
    #
    # Consequence to state plainly: this check is more lenient on a short recording,
    # which is the opposite of ideal, because a short baseline is the worse one
    # (17.1% bad at four windows against 7.7% at twelve). Gating on window count
    # instead was measured and rejected — it refuses 41% of sessions to catch 75%
    # of the bad ones, and four in five of those refusals are wrong.
    max_relative_spread: float = 0.35

    # Resting heart rate. Someone sitting still at over 90 bpm is not at rest,
    # whatever their HRV happens to look like.
    #
    # The stronger of the two checks, and unlike the spread it does not shift with
    # how long the recording is — a rate is a level, not a dispersion. On its own it
    # refuses 7.4% and 41% of those refusals are correct, which is most of what the
    # pair achieves together.
    #
    # It is also the only one a person can act on. "Your interquartile range is too
    # wide" is not an instruction; "sit quietly for another minute" is.
    max_resting_hr_bpm: float = 90.0

    # How many windows a baseline needs before it is reported without a caveat.
    #
    # This is NOT a third refusal. It is the answer to the one thing the two checks
    # above cannot express: how much evidence they were applied to. A person who
    # presses start the instant the sensor pairs gives four windows; one who spends
    # two minutes fitting an armband gives twelve, at no cost to anybody. Measured
    # over 4,700 baselines, the difference in what SLIPS THROUGH undetected:
    #
    #     under 6 windows   11.8% of sessions carry a bad baseline, unflagged
    #     6 to 9 windows     6.6%
    #     10 or more         3.9%
    #
    # Three times the risk, decided entirely by a habit nobody was ever told about.
    # Blocking the start button until enough had accumulated was considered and
    # rejected: waiting is exactly what the session timeline was shortened twice to
    # remove, and reintroducing it through a side door would undo that.
    #
    # So the amount of evidence is REPORTED instead. A thin baseline is not refused,
    # it is labelled — the same move the rest of the system already makes when it
    # says recovery was "not measurable" rather than quietly writing 0%.
    min_windows_full_evidence: int = 10
    min_windows_limited_evidence: int = 6


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
# STRESS LEVEL RULE (the product's classifier)
# ===========================================================================
@dataclass(frozen=True)
class StressRuleConfig:
    """
    Thresholds that turn reactivity into a low / moderate / high label.

    This rule, not the LLM, assigns the label in the product. Two reasons, both
    measured rather than assumed:

    - On the development subjects a two-feature rule reaches macro-F1 0.828 and
      kappa 0.656, while an LLM given the same numbers answered "uncertain" on 6 of
      13 resting segments that the rule got right.
    - A rule is instant, free, offline, and identical every time it runs — none of
      which is true of a model behind an API.

    The LLM keeps the job it is actually better at: explaining the result in
    language a person can act on.

    Both features are scored because neither is sufficient alone. RMSSD moved the
    expected way in only three of five development subjects, whereas heart rate rose
    in all five; conversely heart rate alone is too crude to grade severity. Scoring
    them together lets one cover for the other.
    """

    # --- CALIBRATED on the five development subjects, 3 August 2026, then FROZEN.
    # Swept 81 combinations; the best moved macro-F1 from 0.831 to 0.851 and kappa
    # from 0.666 to 0.703. Only ONE value changed: the RMSSD moderate threshold.
    # Do not retune these against the test subjects — that would turn the headline
    # figures into a description of how well the thresholds were fitted.

    # RMSSD below baseline by this much scores one point, or two.
    rmssd_moderate_pct: float = -20.0        # calibrated (was -15.0)
    rmssd_high_pct: float = -30.0            # NOT calibrated — see note below

    # Heart rate above baseline by this much scores one point, or two.
    hr_moderate_pct: float = 5.0             # calibrated, unchanged
    hr_high_pct: float = 15.0                # NOT calibrated — see note below

    # WHY TWO THRESHOLDS COULD NOT BE CALIBRATED.
    #
    # WESAD is binary: a subject is either at rest or undergoing TSST, with nothing
    # in between. Both "moderate" and "high" therefore map onto the same stressed
    # class during scoring, so the grid search was blind to where that boundary sits
    # — the five top-scoring combinations differed only in the high thresholds and
    # produced identical results.
    #
    # The values kept are the ones derived from the literature. Calibrating them
    # needs a dataset with a genuine middle condition (SWELL-KW has three levels) or
    # self-reports from real users. Until then, treat the moderate/high boundary as
    # reasoned rather than measured, and say so.

    # Total points needed for each label, out of a maximum of four.
    moderate_points: int = 1
    high_points: int = 3


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

    # Prompt file stem under prompts/. The prompt is part of the system in a RAG
    # design — the equivalent of model architecture in a deep-learning approach —
    # so it lives in its own file and must never be edited silently. To change the
    # wording, copy the file under a new name and point this at it, so earlier
    # results stay reproducible.
    prompt_version: str = "HRV_stress_interpretation"

    # Prompt for the hybrid path, where the rule assigns the label and the model
    # only writes the narrative. One call covers the whole session.
    narrative_prompt: str = "HRV_session_narrative"

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

    # Which backend answers. "gemini" or "ollama"; the environment variable
    # LLM_PROVIDER overrides it, so a run can switch backend without editing code.
    #
    # Gemini remains the default deliberately. Every number already reported was
    # produced with it, and a default that silently changed the backend would make
    # older results irreproducible without anyone noticing.
    provider: str = "gemini"


@dataclass(frozen=True)
class OllamaConfig:
    """
    Parameters for a self-hosted model reached through OpenWebUI's Ollama proxy.

    WHY THIS EXISTS. The free Gemini tier allows 20 calls a day, which is not
    enough to run the ablations the thesis needs (BACKLOG T5.8), and depending on
    a model the vendor can update without notice is a stated limitation (L8). A
    self-hosted model removes both: the call budget becomes the GPU rental, and
    the weights are pinned by a digest that cannot change underneath a result.

    WHAT IT DOES NOT CHANGE. The classification figures — WESAD holdout accuracy
    0.852, macro-F1 0.839, kappa 0.678 — come from the frozen scoring rule and
    involve no API call at all (`scripts/run_holdout.py`). Swapping the backend
    touches the narrative, faithfulness and run-to-run consistency, and nothing
    else.
    """

    # Model tag exactly as `ollama list` reports it, e.g. "qwen3:32b". Empty by
    # design: there is no sensible default, and a wrong tag must fail loudly at
    # startup rather than have Ollama quietly serve some other model. Set it in
    # .env as OLLAMA_MODEL.
    model: str = ""

    # OpenWebUI mounts Ollama's OWN api under /ollama. That native route is used
    # rather than the OpenAI-compatible /api/chat/completions because only the
    # native one accepts a full JSON Schema in `format`, which is what keeps the
    # structured-output guarantee that `response_schema` gives on Gemini. Losing
    # it would reintroduce malformed-JSON failures the pipeline was built to be
    # free of. Going through OpenWebUI rather than straight to port 11434 keeps
    # the authentication: a Vast.ai instance has a public address, and a bare
    # Ollama port is an open GPU for anyone who scans it.
    # TWO ROUTES REACH THE SAME OLLAMA, and the Vast.ai instance portal exposes
    # both. Which one you get decides the path prefix, so it is configurable
    # rather than assumed:
    #
    #   direct    /api/chat          — Ollama's own port, mapped by Vast
    #   openwebui /ollama/api/chat   — proxied through OpenWebUI
    #
    # The direct route is the default because it needs no OpenWebUI account: the
    # port is still fronted by the instance portal's Caddy, so the Vast access
    # token authenticates it. Going through OpenWebUI was originally chosen to
    # get authentication, and that reason turned out to hold on both routes.
    #
    # Set OLLAMA_ROUTE=openwebui in .env to switch.
    chat_path: str = "/api/chat"
    tags_path: str = "/api/tags"

    # A fixed seed makes generation reproducible in a way the Gemini API does not
    # expose at all. This upgrades the consistency check (T5.4) from "three runs
    # happened to agree" to "identical under a fixed seed, and this much spread
    # without one" — a far stronger claim, and one an examiner can re-run.
    seed: int = 20260811

    # Context window, in tokens.
    #
    # This is the parameter most likely to corrupt results silently. Ollama's own
    # default is small, and a prompt longer than the window is TRUNCATED rather
    # than rejected — so the retrieved knowledge chunks, which sit in the middle
    # of the prompt, would simply not reach the model while it still returned a
    # confident, well-formed answer. The RAG system would appear to work while
    # having stopped being a RAG system.
    #
    # 8192 comes from a measurement rather than from caution. Asked to report its
    # own token counts, the server put a real assembled prompt — features, five
    # retrieved chunks, instructions — at 1,918 tokens, with roughly 300 more
    # generated. This leaves a factor of four.
    #
    # It was 16384, which was simply a large round number. Cutting it frees VRAM
    # and costs no speed: a benchmark at 4096 was no faster, because generation
    # rate rather than context allocation is what sets the pace.
    num_ctx: int = 8192

    # Generous, because the FIRST call after an instance starts must load the
    # weights into VRAM, and on a large model that alone can take minutes. A
    # tight timeout here looks exactly like a broken endpoint.
    timeout_sec: float = 600.0

    # A rented GPU has no quota, so pacing exists only to avoid queueing requests
    # faster than one machine can serve them.
    requests_per_minute: int = 60


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

    # Personal baseline. 120 s at the resting hop of 15 s yields 2-4 segments,
    # measured across the five development subjects.
    #
    # Shortened twice, both times for the person waiting rather than for the
    # statistics: 240 s originally, 180 s on 6 Aug 2026, and 120 s the day after.
    # Sitting still is dead time before the practice can begin, and the longer it
    # runs the less likely someone is to actually keep still — a baseline they did
    # not really observe is worse than a shorter one they did.
    #
    # 120 s IS THE HARD FLOOR, and not by convention. Features are computed over
    # 60-second windows, and a 60-second rest produces a beat series spanning only
    # about 59 seconds — measured from the first beat to the last, not from when
    # the timer started. Nothing fits, so the result is not a weak baseline but no
    # baseline at all, and with no baseline the whole session is unscoreable.
    # A finer hop does not rescue it: zero windows stay zero.
    #
    # What makes 120 s workable is `baseline_overlap_sec`, which samples these
    # same two minutes every 15 seconds instead of every 30. That recovers about
    # the window count three minutes gave before, without adding information that
    # is not there.
    #
    # Kept identical to the web demo's `INTERVIEW_REST_MINUTES`, so the protocol
    # described here and the one users actually perform are the same protocol.
    calibration_sec: int = 120

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
    baseline_gate: BaselineGateConfig = field(default_factory=BaselineGateConfig)
    stress_rule: StressRuleConfig = field(default_factory=StressRuleConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    split: SplitConfig = field(default_factory=SplitConfig)


settings = Settings()
