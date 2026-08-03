"""
modality.py — Paired comparison of ECG and PPG (BACKLOG T6.4).

WESAD is the only dataset in this project that records both modalities from the SAME
subjects at the SAME time. That makes this the strongest evidence available: any
difference between the two cannot be explained by different people, different days,
or different stressors — only by the measurement itself.

Three complementary views are computed, because each answers a different question:

- **ICC** asks whether the two methods rank and scale segments alike. It is the
  standard agreement statistic for repeated measurements of the same quantity.
- **Bland-Altman** asks *how far apart* they are and *whether the gap depends on the
  value*. Correlation can be excellent while a systematic offset makes the two
  unusable interchangeably — Bland-Altman exposes exactly that, which correlation
  alone hides.
- **Label agreement** asks the only question the end user cares about: would the
  system have reached the same conclusion from a smartwatch as from a chest strap?

Reporting only correlation would be the classic mistake in method-comparison work.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AgreementReport:
    """Agreement between two modalities on one feature."""

    feature: str
    n_pairs: int
    icc: float
    pearson: float
    bias: float                 # mean difference, PPG minus ECG
    loa_lower: float            # limits of agreement
    loa_upper: float
    proportional_bias: float    # slope of difference against mean

    def summary(self) -> str:
        return (
            f"  {self.feature:<12} n={self.n_pairs:<4} "
            f"ICC={self.icc:+.3f}  r={self.pearson:+.3f}  "
            f"bias={self.bias:+.2f}  LoA=[{self.loa_lower:+.2f}, "
            f"{self.loa_upper:+.2f}]  slope={self.proportional_bias:+.3f}"
        )


def icc_two_way_agreement(x: np.ndarray, y: np.ndarray) -> float:
    """
    ICC(2,1) — two-way random effects, absolute agreement, single measurement.

    Absolute agreement is the right variant here, not consistency. Consistency would
    forgive a fixed offset between the two devices; absolute agreement does not. If
    PPG systematically reads RMSSD higher than ECG, that matters, because the two are
    meant to be interchangeable measures of the same thing.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = x.size
    if n < 3:
        return float("nan")

    matrix = np.column_stack([x, y])
    k = 2

    grand_mean = matrix.mean()
    row_means = matrix.mean(axis=1)
    col_means = matrix.mean(axis=0)

    ss_rows = k * np.sum((row_means - grand_mean) ** 2)
    ss_cols = n * np.sum((col_means - grand_mean) ** 2)
    ss_total = np.sum((matrix - grand_mean) ** 2)
    ss_error = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    return float((ms_rows - ms_error) / denominator) if denominator != 0 else float("nan")


def bland_altman(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """
    Bland-Altman statistics for y against x.

    Returns (bias, lower limit, upper limit, proportional-bias slope).

    The differences are plotted against the MEAN of the two methods rather than
    against either one. Using one method as the x-axis would build in a correlation
    between the axes and produce a spurious trend even when none exists.

    The slope of difference against mean detects proportional bias: a gap that grows
    with the size of the measurement. That is the pattern expected here, since PPG
    and ECG agree well at rest but diverge under stress.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    difference = y - x
    average = (x + y) / 2.0

    bias = float(np.mean(difference))
    sd = float(np.std(difference, ddof=1))

    slope = float("nan")
    if x.size >= 3 and np.std(average) > 0:
        slope = float(np.polyfit(average, difference, 1)[0])

    # 1.96 SD covers about 95% of differences if they are roughly normal.
    return bias, bias - 1.96 * sd, bias + 1.96 * sd, slope


def compare_feature(ecg_values: np.ndarray, ppg_values: np.ndarray,
                    feature: str) -> AgreementReport:
    """Compute every agreement statistic for one feature."""
    ecg = np.asarray(ecg_values, float)
    ppg = np.asarray(ppg_values, float)

    valid = np.isfinite(ecg) & np.isfinite(ppg)
    ecg, ppg = ecg[valid], ppg[valid]

    if ecg.size < 3:
        return AgreementReport(feature, ecg.size, *([float("nan")] * 6))

    bias, lo, hi, slope = bland_altman(ecg, ppg)
    pearson = (float(np.corrcoef(ecg, ppg)[0, 1])
               if np.std(ecg) > 0 and np.std(ppg) > 0 else float("nan"))

    return AgreementReport(
        feature=feature, n_pairs=int(ecg.size),
        icc=icc_two_way_agreement(ecg, ppg), pearson=pearson,
        bias=bias, loa_lower=lo, loa_upper=hi, proportional_bias=slope,
    )


def label_agreement(ecg_labels: list[str], ppg_labels: list[str]) -> float:
    """
    Fraction of segments where both modalities produced the same stress label.

    This is the practically decisive number. ICC can look respectable while the two
    still disagree on the label often enough to matter — and the label is what the
    user actually sees.
    """
    if not ecg_labels or len(ecg_labels) != len(ppg_labels):
        return float("nan")
    matches = sum(1 for a, b in zip(ecg_labels, ppg_labels) if a == b)
    return matches / len(ecg_labels)
