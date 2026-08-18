"""
baseline.py — Each subject's personal reference and the reactivity computation.

This is Mandatory Rule #2 in practice: what carries meaning is not "RMSSD = 22 ms"
but "RMSSD is 35% BELOW this person's baseline". HRV is too individual — shaped by
age, sex, breathing rhythm, posture, and caffeine — for absolute cross-person
thresholds to be trustworthy.

The only class in the `features` package lives here, deliberately (decision K12):
`BaselineProfile` HOLDS one subject's reference and is reused across many segments.
Every other module in the package is plain functions, because they hold no state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from ..config.settings import BaselineGateConfig, settings
from ..core.types import Phase, RRSeries

from .frequency_domain import FREQ_FEATURES
from .time_domain import TIME_FEATURES

#: Features compared against the baseline.
COMPARED_FEATURES: tuple[str, ...] = TIME_FEATURES + FREQ_FEATURES


@dataclass
class BaselineProfile:
    """
    One subject's HRV reference, summarised from the calibration phase.

    Attributes:
        subject   : subject ID
        values    : reference value per feature
        spread    : interquartile range per feature — a measure of how stable the
                    reference is. A large IQR means an unsteady baseline, and any
                    reactivity computed from it deserves less trust.
        n_segments: number of calibration segments behind this reference
    """

    subject: str
    values: dict[str, float]
    spread: dict[str, float] = field(default_factory=dict)
    n_segments: int = 0

    # ------------------------------------------------------------ builder
    @classmethod
    def from_segments(cls, subject: str,
                      calibration_features: pd.DataFrame) -> "BaselineProfile":
        """
        Build the reference from the calibration-phase feature table.

        The MEDIAN is used, not the mean. A single noisy segment can drag the mean a
        long way, whereas the median barely moves. Since every reactivity figure is
        divided by this reference, its stability determines the stability of
        everything computed afterwards.
        """
        if calibration_features.empty:
            raise ValueError(
                f"{subject}: no calibration segment passed the quality gates, "
                f"so no baseline can be built."
            )

        values, spread = {}, {}
        for feat in COMPARED_FEATURES:
            if feat not in calibration_features.columns:
                continue
            col = calibration_features[feat].dropna()
            if col.empty:
                continue
            values[feat] = float(col.median())
            spread[feat] = float(col.quantile(0.75) - col.quantile(0.25))

        return cls(subject=subject, values=values, spread=spread,
                   n_segments=len(calibration_features))

    @classmethod
    def from_series(cls, subject: str, resting: RRSeries) -> "BaselineProfile":
        """
        Build the reference straight from a resting recording, sampled densely.

        Preferred over `from_segments` whenever the raw resting series is at hand,
        because it segments with the finer resting hop — 15 seconds instead of 30
        — and that is what makes a two-minute rest usable at all.

        Why the density belongs HERE and not in the feature table: on WESAD the
        resting segments are also the low-stress examples the system is scored
        against, so sampling them twice as densely would double one class and
        change every classification metric without any measurement changing. The
        baseline needs the steadiest central value it can extract from a short
        recording; the classification set needs segments as independent as the
        design allows. Same recording, two different requirements.

        Over two minutes the finer hop yields 2-4 windows where the standard hop
        yields 1-2. Across a full WESAD resting phase the two agree to within
        0.07-1.33%, so this changes nothing that was already validated.
        """
        from .extractor import extract_features_with  # local: avoids a cycle

        table, _ = extract_features_with(
            resting, settings.segmentation.for_phase(Phase.CALIBRATION)
        )
        return cls.from_segments(subject, table)

    # ---------------------------------------------------------------- use
    def reactivity(self, features: dict[str, float]) -> dict[str, float]:
        """
        Relative change of one segment against the reference, in percent.

            reactivity = (segment_value - reference) / reference x 100

        Negative means below baseline, positive means above it.

        IMPORTANT — the code stops here. There is no combined "stress score",
        because fusing these five numbers is exactly the job of the LLM working from
        the knowledge base. If the code did the fusing, the LLM would merely be
        reading off a threshold and the whole RAG approach would lose its purpose.
        """
        out: dict[str, float] = {}
        for feat, ref in self.values.items():
            if feat not in features:
                continue
            value = features[feat]
            if ref in (0, None) or np.isnan(ref) or np.isnan(value):
                out[f"delta_pct_{feat}"] = np.nan
            else:
                out[f"delta_pct_{feat}"] = (value - ref) / ref * 100.0
        return out

    def relative_spread(self, feature: str) -> float:
        """
        IQR divided by the reference value — how unsteady the baseline is.

        Used as a warning flag: when this is large, any reactivity derived from that
        reference needs more cautious interpretation.
        """
        ref = self.values.get(feature)
        iqr = self.spread.get(feature)
        if not ref or iqr is None or ref == 0:
            return float("nan")
        return iqr / abs(ref)

    def describe(self) -> str:
        rmssd = self.values.get("rmssd", float("nan"))
        return (f"baseline {self.subject}: {self.n_segments} segments, "
                f"reference RMSSD {rmssd:.1f} ms "
                f"(relative IQR {self.relative_spread('rmssd'):.0%})")


class BaselineEvidence(str, Enum):
    """
    How much resting recording the verdict was reached on.

    A separate axis from whether the baseline looks steady, and it has to be,
    because a baseline can be perfectly steady and rest on almost nothing. Four
    windows cannot disagree with each other much — the checks then pass for want of
    evidence rather than on the strength of it.
    """

    FULL = "full"
    LIMITED = "limited"
    MINIMAL = "minimal"


@dataclass(frozen=True)
class BaselineVerdict:
    """
    Whether a resting period is fit to be a personal reference.

    `is_acceptable` False does not mean the session failed. It means the resting
    period should be recorded again BEFORE the interview, which is the only moment
    at which it is still cheap to fix.

    `evidence` is deliberately NOT folded into `is_acceptable`. A thin baseline is
    not a faulty one, and refusing on it would send somebody to redo a resting
    period that may have been perfectly good. What it changes is how much the
    result deserves to be trusted, and that belongs in the report rather than in a
    gate.
    """

    is_acceptable: bool
    reasons: list[str]
    relative_spread: float
    resting_hr_bpm: float
    n_windows: int = 0
    evidence: BaselineEvidence = BaselineEvidence.FULL

    @property
    def is_thin(self) -> bool:
        return self.evidence is not BaselineEvidence.FULL

    def note_for_user(self) -> str:
        """Indonesian, plain language, no feature names (decision K4)."""
        if not self.is_acceptable:
            return ("periode tenang di awal belum benar-benar tenang, jadi angka "
                    "di bawah ini kurang pasti dari biasanya")
        if self.evidence is BaselineEvidence.MINIMAL:
            return ("periode tenang di awal terlalu singkat untuk jadi "
                    "pembanding yang kuat, jadi angka di bawah ini sebaiknya "
                    "dibaca sebagai gambaran kasar")
        if self.evidence is BaselineEvidence.LIMITED:
            return ("periode tenang di awal cukup singkat, jadi angka di bawah "
                    "ini sedikit kurang pasti dari biasanya")
        return ""

    def note_for_model(self) -> str:
        """English, technical — this one goes into the prompt, not onto a screen."""
        parts = []
        if not self.is_acceptable:
            parts.append(f"the resting baseline was unsteady "
                         f"({'; '.join(self.reasons)})")
        if self.is_thin:
            parts.append(f"it rests on only {self.n_windows} resting windows "
                         f"({self.evidence.value} evidence)")
        if not parts:
            return ""
        return (f"{', and '.join(parts)} — so reactivity figures are less certain "
                f"than usual")


def check_baseline(profile: BaselineProfile,
                   cfg: BaselineGateConfig | None = None) -> BaselineVerdict:
    """
    The single place that decides whether a resting period is usable.

    THIS USED TO LIVE IN FOUR PLACES. The same `> 0.40` comparison was written out
    in `session_pipeline.py`, in the API's `analysis.py`, and in two scripts. Four
    copies of a number that had never been measured, which is the arrangement where
    one gets corrected and the other three quietly keep disagreeing with it — the
    offline report and the API would then hand the same recording two different
    verdicts.

    Two independent checks, either of which is enough to refuse:

    1. **Spread** — the resting windows disagree with each other, so their median
       is not standing on anything.
    2. **Resting heart rate** — the windows may agree perfectly and still describe
       somebody who never settled. Spread cannot see this: a steadily elevated
       heart rate is steady. It is caught only by asking whether the level itself
       is plausible for a person sitting still.

    A measurement that could not be taken is not a failure. NaN spread means fewer
    than the windows needed to form an IQR, and refusing on that would turn a short
    recording into a bad one.
    """
    cfg = cfg or settings.baseline_gate
    spread = profile.relative_spread(settings.dynamics.primary_feature)
    hr = profile.values.get("mean_hr", float("nan"))

    reasons = []
    if spread == spread and spread > cfg.max_relative_spread:
        reasons.append(f"relative IQR {spread:.0%} exceeds "
                       f"{cfg.max_relative_spread:.0%}")
    if hr == hr and hr > cfg.max_resting_hr_bpm:
        reasons.append(f"resting heart rate {hr:.0f} bpm exceeds "
                       f"{cfg.max_resting_hr_bpm:.0f} bpm, which is not a resting "
                       f"state")

    if profile.n_segments >= cfg.min_windows_full_evidence:
        evidence = BaselineEvidence.FULL
    elif profile.n_segments >= cfg.min_windows_limited_evidence:
        evidence = BaselineEvidence.LIMITED
    else:
        evidence = BaselineEvidence.MINIMAL

    return BaselineVerdict(is_acceptable=not reasons, reasons=reasons,
                           relative_spread=spread, resting_hr_bpm=hr,
                           n_windows=profile.n_segments, evidence=evidence)
