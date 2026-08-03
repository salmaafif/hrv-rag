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

import numpy as np
import pandas as pd

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
