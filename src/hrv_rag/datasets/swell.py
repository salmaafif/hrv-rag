"""
swell.py — SWELL-KW, entered at the FEATURE level rather than the signal level.

This file deliberately does NOT subclass `BaseDatasetLoader`. That contract is
built around `load_phase_signal`, and there is no signal here to load. Forcing an
inheritance that cannot honour its own interface would hide the difference that
matters most about this dataset, so it is stated in the open instead.

WHAT WAS AVAILABLE, AND WHY THIS PART WAS CHOSEN
------------------------------------------------
The public SWELL-KW HRV package ships three layers, and only one of them can
support the method used here:

1. `data/final/train.csv` and `test.csv` — 36 HRV features over 5-minute sliding
   windows. Rejected: there is NO subject column, only a constant `datasetId`.
   Mandatory Rule #2 requires every percentage to be measured against the same
   person's own baseline, and without knowing who a row belongs to that is
   impossible. The window is also five minutes against this project's sixty
   seconds, so the numbers would not be comparable to the WESAD results anyway.

2. `data/raw/rri/p*.txt` — per-subject RR series. Rejected on inspection: the
   time column advances in exact 0.25 s steps, so this is a tachogram already
   interpolated onto a 4 Hz grid, not a beat-by-beat series. Measured on p1, not
   one consecutive pair differs by more than 20%, where a genuine beat series
   shows around 1.5%. RMSSD and pNN50 are defined on successive BEATS, so
   computing them from an interpolated curve would report a number that looks
   reasonable and means something else. The time axes also disagree with the
   labels (150 minutes of RR against 179 minutes of labelling), leaving no
   trustworthy way to say which condition a stretch belongs to.

3. `data/raw/labels/hrv stress labels.xlsx` — one sheet per participant, one row
   per MINUTE, carrying subject, condition, heart rate and RMSSD. This is the
   layer used. Three things make it fit:

   - Its one-minute window matches this project's 60-second segments.
   - It carries an explicit REST condition, which gives the personal baseline
     Mandatory Rule #2 depends on.
   - The scoring rule needs exactly RMSSD and heart rate, and both are present.

   Sanity check on the values: median RMSSD 45.7 ms and median heart rate 73 bpm,
   which sits squarely alongside the WESAD development subjects (RMSSD roughly
   40-55 ms). The units in the file are SECONDS, converted here.

LIMITATIONS THAT MUST BE REPORTED
---------------------------------
- The features were computed by the SWELL authors, not by this code. Mandatory
  Rule #1 still holds — the LLM computes nothing — but reproducibility differs
  from WESAD, where every number came from `features/`. Say so in the report.
- Only RMSSD and heart rate are available. No LF/HF, no pNN50, no SDNN. The
  scoring rule is unaffected, but the retrieval query is built from two of its
  five usual features, so the RAG context is thinner than on WESAD.
- 47% of minutes have no HR or RMSSD at all, and after dropping those only 14 of
  the 23 subjects retain a usable rest period together with all three conditions.
- Consecutive minutes do not overlap, unlike the 30-second-hop segments used on
  WESAD. For this dataset the independence caveat in BACKLOG L2 does not apply —
  which is worth stating, because it makes SWELL the cleaner of the two.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

#: Condition code in the spreadsheet -> the phase name used throughout this
#: project. Rest becomes the calibration phase so `BaselineProfile.from_segments`
#: works on it unchanged.
#:
#: The three stressor codes are kept distinct rather than collapsed, because they
#: are the whole reason SWELL is here: WESAD is binary, so its data could never
#: separate "moderate" from "high" and the upper threshold stayed uncalibrated
#: (BACKLOG T2c.10).
CONDITION_TO_PHASE: dict[str, str] = {
    "R": "calibration",     # rest
    "N": "no_stress",       # neutral working condition
    "T": "time_pressure",   # same task, two-thirds of the time
    "I": "interruption",    # unexpected emails mid-task
}

#: Minimum rest minutes before a subject's baseline is worth trusting. The median
#: of fewer than three values moves too far when one minute is noisy, and every
#: reactivity percentage for that subject is divided by it.
MIN_REST_MINUTES = 3


def _locate(root: Path | None) -> Path:
    """Find the labels workbook inside a kagglehub download."""
    if root is not None:
        candidate = Path(root)
        if candidate.is_file():
            return candidate
        matches = sorted(candidate.rglob("hrv stress labels.xlsx"))
        if matches:
            return matches[0]
        raise FileNotFoundError(f"no 'hrv stress labels.xlsx' under {candidate}")

    cache = Path.home() / ".cache" / "kagglehub" / "datasets" / "qiriro"
    matches = sorted(cache.rglob("hrv stress labels.xlsx"))
    if not matches:
        raise FileNotFoundError(
            "SWELL labels not found. Download it first:\n"
            "  python -c \"from dotenv import load_dotenv; load_dotenv();"
            " import kagglehub;"
            " print(kagglehub.dataset_download('qiriro/swell-heart-rate-variability-hrv'))\""
        )
    return matches[0]


def load_swell_minutes(root: Path | None = None) -> pd.DataFrame:
    """
    Read every participant sheet into one table shaped like this project's own.

    The column names deliberately match what `features/extractor.py` produces —
    `subject`, `phase`, `rmssd`, `mean_hr` — so `BaselineProfile`, `classify` and
    the whole of `evaluation/` are reused without a single change. Renaming at the
    boundary is the entire job of this function.

    Minutes with no heart rate or no RMSSD are dropped rather than filled. An
    imputed value would enter the median that defines someone's baseline and there
    would be no way to tell afterwards which numbers had been measured.
    """
    path = _locate(root)
    book = pd.ExcelFile(path)

    frames = []
    for sheet in book.sheet_names:
        frame = book.parse(sheet)
        if "subject" not in frame.columns:
            continue
        frames.append(frame)

    raw = pd.concat(frames, ignore_index=True)
    raw = raw.dropna(subset=["HR", "RMSSD"])

    table = pd.DataFrame({
        "subject": raw["subject"].astype(str),
        "phase": raw["Condition"].astype(str).map(CONDITION_TO_PHASE),
        # The workbook stores RMSSD in seconds; everything here works in
        # milliseconds, as the WESAD tables do.
        "rmssd": raw["RMSSD"].astype(float) * 1000.0,
        "mean_hr": raw["HR"].astype(float),
        "minute": raw["ElapsedTime"].astype(int),
    })
    table = table.dropna(subset=["phase"])

    # `start_sec` lets the same code that reads WESAD segment tables read this one.
    # One row is one minute, and the minutes do not overlap.
    table["start_sec"] = table["minute"] * 60.0
    table["end_sec"] = table["start_sec"] + 60.0
    table["segment"] = table["minute"] + 1
    table["modality"] = "ECG"
    table["outlier_pct"] = np.nan     # not measurable: no beat series was seen

    return table.sort_values(["subject", "minute"]).reset_index(drop=True)


def usable_subjects(table: pd.DataFrame, require_all_conditions: bool = True
                    ) -> list[str]:
    """
    Subjects with enough rest to anchor a baseline, plus something to compare it to.

    `require_all_conditions` distinguishes the two questions SWELL can answer. For
    calibrating the moderate/high boundary (T2c.10) all three stressor levels must
    be present in the same person, which holds for 14 subjects. For simply asking
    whether stress is detected at all, one stressor is enough, which holds for 22.
    """
    counts = (table.groupby(["subject", "phase"]).size()
              .unstack(fill_value=0))
    stressors = [p for p in CONDITION_TO_PHASE.values() if p != "calibration"]
    for column in ["calibration", *stressors]:
        if column not in counts:
            counts[column] = 0

    enough_rest = counts["calibration"] >= MIN_REST_MINUTES
    if require_all_conditions:
        has_work = np.logical_and.reduce([counts[s] > 0 for s in stressors])
    else:
        has_work = counts[stressors].sum(axis=1) > 0

    return sorted(counts.index[enough_rest & has_work])
