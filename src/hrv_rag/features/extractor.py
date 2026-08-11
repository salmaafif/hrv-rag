"""
extractor.py — Assembler: RRSeries -> per-segment feature table.

This module computes nothing of its own. Its job is to chain segmentation,
time-domain features, and frequency-domain features into one table, then attach the
provenance columns (subject, modality, phase, signal quality).

Those provenance columns are mandatory (T2.4) because CLAUDE.md forbids pooling
results across datasets and across modalities into a single metric. Without marker
columns that prohibition would be impossible to enforce at evaluation time.
"""

from __future__ import annotations

import pandas as pd

from ..config.settings import SegmentationConfig, settings
from ..core.types import RRSeries
from .frequency_domain import frequency_features
from .segmentation import SegmentationResult, segment_rr_series
from .time_domain import time_domain_features

#: Mapping from Python attribute names to column names for CSV and reports.
#: The code uses snake_case per PEP 8; tables in the thesis use the scientific
#: notation the examiners will recognise (RMSSD, pNN50, and so on).
DISPLAY_NAMES: dict[str, str] = {
    "mean_rr": "meanRR",
    "mean_hr": "meanHR",
    "sdnn": "SDNN",
    "rmssd": "RMSSD",
    "pnn50": "pNN50",
    "lf_welch": "LF_welch",
    "hf_welch": "HF_welch",
    "lf_hf_welch": "LF/HF_welch",
    "lf_ls": "LF_ls",
    "hf_ls": "HF_ls",
    "lf_hf_ls": "LF/HF_ls",
}


def extract_features(series: RRSeries) -> tuple[pd.DataFrame, SegmentationResult]:
    """
    Turn one `RRSeries` into a feature table with one row per segment.

    The `SegmentationResult` is returned as well so the caller can report how many
    windows were dropped and why. That quality information also travels into the
    prompt, allowing the LLM to adjust its confidence score.

    The standard hop is used for EVERY phase, including the resting one.

    That is deliberate, and was briefly got wrong. The resting phase does get
    sampled more densely — but only when building the personal baseline, which is
    what `BaselineProfile.from_series` is for. Applying that density here as well
    looks harmless and is not: on WESAD these rows are also the low-stress class,
    so doubling them doubled one side of the classification set and dropped
    macro-F1 from 0.851 to 0.797 without a single measurement having changed.

    Two different jobs, two different sampling rates. The baseline wants the
    steadiest possible central value from a short recording; the classification
    set wants segments that are as independent as the design allows.
    """
    return extract_features_with(series, settings.segmentation)


def extract_features_with(series: RRSeries, seg_cfg: SegmentationConfig
                          ) -> tuple[pd.DataFrame, SegmentationResult]:
    """
    Same as `extract_features`, with the segmentation stated explicitly.

    Exists so `BaselineProfile.from_series` can ask for the denser resting hop
    without that density leaking into the table everything else is built from.
    """
    result = segment_rr_series(series, seg_cfg=seg_cfg)

    rows = []
    for seg in result.segments:
        row: dict[str, object] = {
            # --- provenance columns (T2.4) ---
            "subject": series.subject,
            "modality": series.modality.value,
            "phase": series.phase.value,
            "segment": seg.index,
            "start_sec": round(seg.start_sec, 1),
            "end_sec": round(seg.end_sec, 1),
            "n_beats": seg.n_beats,
            "outlier_pct": round(seg.outlier_ratio * 100, 2),
        }
        row.update(time_domain_features(seg.rr_ms))
        row.update(frequency_features(seg.rr_ms))
        rows.append(row)

    return pd.DataFrame(rows), result


def from_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Restore snake_case names after reading a CSV written for display.

    The inverse of `to_display_columns`. It exists so that every consumer of the
    feature CSV does not have to carry its own translation table — a duplicated
    mapping is exactly the kind of thing that silently drifts out of step.
    """
    mapping = {shown: attr for attr, shown in DISPLAY_NAMES.items()}
    for attr, shown in DISPLAY_NAMES.items():
        mapping[f"delta%_{shown}"] = f"delta_pct_{attr}"
    return df.rename(columns=mapping)


def load_features(path) -> pd.DataFrame:
    """Read a feature CSV and hand it back with the names the code expects."""
    return from_display_columns(pd.read_csv(path))


def to_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename feature columns to scientific notation, including reactivity columns.

    Used only when writing CSV or displaying a table. Inside the code the snake_case
    names remain, so the source stays PEP 8 compliant.
    """
    mapping = dict(DISPLAY_NAMES)
    for attr, shown in DISPLAY_NAMES.items():
        mapping[f"delta_pct_{attr}"] = f"delta%_{shown}"
    return df.rename(columns=mapping)
