"""
intervals.py — the third entry point: a recording that arrives already as beats.

The ECG and PPG branches both start from a waveform and end at an `RRSeries`. A
recording uploaded by a user starts further along: consumer chest straps and
watches export inter-beat intervals directly, because the device did the peak
detection itself, on the raw optical or electrical signal, before anything left it.

So this file does NOT skip filtering and peak detection — it REPLACES them with
work already performed elsewhere. That distinction matters at the defence, because
CLAUDE.md requires the two modalities to live in separate files, and here they do
not diverge at all: for an uploaded interval series, ECG and PPG receive identical
treatment. The modality survives only as a label carried into the prompt
(Mandatory Rule #5), which is still worth having — it is the model's cue to trust
an optical reading less — but it changes no arithmetic.

What this file must therefore take seriously is the part no device does for us:
deciding whether the numbers really are inter-beat intervals in milliseconds. The
agreed file format carries no header and no unit marker, so a file in seconds and
a file in milliseconds are both just columns of numbers. Guessing wrong produces a
complete, confident, entirely wrong report, so the numbers are checked against
human physiology and rejected rather than interpreted when they do not fit.
"""

from __future__ import annotations

import numpy as np

from ..config.settings import QualityConfig, settings
from ..core.types import Modality, Phase, QualityReport, RRSeries
from .base import correct_ectopic

#: Fewest intervals worth accepting. One 60-second window needs 30 beats
#: (`SegmentationConfig.min_beats`), and a recording that cannot fill a single
#: window has nothing to measure.
MIN_INTERVALS = 30


class IntervalFormatError(ValueError):
    """The file does not hold inter-beat intervals in milliseconds."""


def parse_rr_csv(text: str) -> np.ndarray:
    """
    Read the agreed upload format: one interval per line, in milliseconds.

    No header, because that is what heart-rate apps export and asking people to
    edit a file before uploading it invites a worse mistake than it prevents. A
    header line is nevertheless tolerated if present — a first line that is not a
    number is skipped rather than treated as a failure, since "rr_ms" at the top of
    the file is a reasonable thing for someone to have added.

    Blank lines are ignored. Values may be decimal. Commas are accepted as column
    separators so a two-column export still parses, taking the first column.
    """
    values: list[float] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        field = line.split(",")[0].strip()
        try:
            values.append(float(field))
        except ValueError:
            # A non-numeric first line is a header. Anywhere else it is corruption,
            # and quietly dropping it would silently shorten the recording.
            if line_no == 1 and not values:
                continue
            raise IntervalFormatError(
                f"line {line_no} is not a number: {line[:40]!r}"
            ) from None

    return np.asarray(values, dtype=float)


def check_looks_like_milliseconds(rr_ms: np.ndarray) -> None:
    """
    Refuse anything that is not plausibly a series of intervals in milliseconds.

    Human resting intervals run roughly 300-2000 ms (200 down to 30 bpm), which is
    `QualityConfig.rr_min_sec`/`rr_max_sec`. Two wrong files are easy to produce and
    impossible to spot afterwards, and both are caught here by where the median
    lands:

    - **Seconds instead of milliseconds** (0.86 rather than 856). Every value would
      fall outside the physiological range, so ectopic correction would flag 100% of
      beats and every window would be dropped — a confusing "no usable data" report
      rather than a clear "wrong unit" one.

    - **Heart rate instead of intervals** (72 rather than 833). This is the
      dangerous one. BPM values are numerically valid, sit in a believable-looking
      range, and are INVERSELY related to what they are read as — so a fast heart
      would be reported as a slow one, and rising stress would read as calming down.
      The whole report would be backwards and internally consistent.

    A median is used rather than a mean so a handful of artefacts cannot move the
    verdict.
    """
    if rr_ms.size < MIN_INTERVALS:
        raise IntervalFormatError(
            f"only {rr_ms.size} intervals found; at least {MIN_INTERVALS} are "
            f"needed to fill a single 60-second window"
        )

    median = float(np.median(rr_ms))
    lo = settings.quality.rr_min_sec * 1000.0
    hi = settings.quality.rr_max_sec * 1000.0

    if median < 10.0:
        raise IntervalFormatError(
            f"median interval is {median:.2f}, which looks like SECONDS. "
            f"Multiply the column by 1000 and upload milliseconds."
        )
    if median < lo:
        raise IntervalFormatError(
            f"median value is {median:.0f}, which looks like HEART RATE in bpm "
            f"rather than an interval in milliseconds. These are inverses of one "
            f"another, so reading one as the other reverses every conclusion. "
            f"Export the RR/IBI interval series instead."
        )
    if median > hi:
        raise IntervalFormatError(
            f"median interval is {median:.0f} ms, i.e. below "
            f"{60000.0 / median:.0f} bpm, which is outside the physiological range "
            f"this system is validated for"
        )


def rr_series_from_intervals(
    rr_ms: np.ndarray,
    modality: Modality,
    subject: str,
    phase: Phase,
    quality_cfg: QualityConfig | None = None,
) -> RRSeries:
    """
    Turn a validated interval series into the same `RRSeries` a waveform produces.

    Ectopic correction is the shared function from `base`, not a copy, so an
    uploaded recording is cleaned by exactly the criteria the WESAD results were
    validated with.

    The `QualityReport` records that no waveform was inspected. Clipping and
    flat-line are properties of a raw signal, and this input has none — reporting
    0.0 for both would claim a check that never happened, so the report says so in
    its notes and leaves `is_acceptable` to rest on the outlier rate instead.
    """
    check_looks_like_milliseconds(rr_ms)

    corrected, is_outlier = correct_ectopic(rr_ms, quality_cfg)
    outlier_ratio = float(is_outlier.mean())

    report = QualityReport(
        clipping_ratio=float("nan"),
        flatline_ratio=float("nan"),
        is_acceptable=outlier_ratio <= settings.quality.max_outlier_ratio,
        notes=["no waveform available: intervals came from the device already "
               "detected, so clipping and flat-line could not be checked"],
    )

    # Each interval is timestamped at the beat that ENDS it, matching
    # `BasePreprocessor.peaks_to_intervals`, so segmentation behaves identically.
    t_sec = np.cumsum(corrected) / 1000.0

    return RRSeries(
        rr_ms=corrected, t_sec=t_sec, modality=modality,
        subject=subject, phase=phase, quality=report, is_outlier=is_outlier,
    )


def split_baseline_and_task(
    rr_ms: np.ndarray, baseline_minutes: float, offset_sec: float = 0.0
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Cut one continuous recording into its resting period and everything after.

    Returns `(resting, task, rest_end_sec)`, where `rest_end_sec` is where the cut
    actually landed measured from the first beat of the recording. Callers need
    that number to translate between the two clocks below, and deriving it a
    second time from `baseline_minutes` would be subtly wrong: the cut falls on a
    beat boundary, not on the requested second.

    Reactivity is defined against the person's OWN baseline (Mandatory Rule #2), so
    a single uploaded file has to supply both halves. The split is by elapsed time
    rather than by beat count: a fast heart produces more beats per minute, and
    splitting on beats would give an anxious person a shorter resting period than a
    calm one — shrinking exactly the reference their reactivity is measured against.

    TWO CLOCKS, AND WHY `offset_sec` EXISTS.

    A recording does not necessarily begin when the resting period does. A sensor
    connected over Bluetooth starts producing beats the moment it pairs, while the
    session — and every timestamp the session reports — begins later, when the
    person presses start. `offset_sec` is the distance between those two instants:
    how much of the recording had already been captured before the session clock
    reached zero. It is 0 for an uploaded file, where the two coincide.

    THE PRELUDE IS KEPT, NOT DISCARDED. Those early minutes are resting data —
    the person was sitting still fitting the sensor and reading the screen — and
    a two-minute rest is short enough that throwing them away is a real loss
    (`scripts/analyse_baseline_duration.py`: a two-minute baseline can land 43%
    from the truth, worst case 102%).

    But they are only PROBABLY resting: nobody watched, and nobody asked. So the
    prelude may contribute at most as much as the observed resting period does,
    which caps the unverified half at fifty percent rather than letting a long
    setup drown out the minutes we actually asked for. That rule needs no
    threshold of its own — it is stated entirely in terms of the rest that was
    requested.
    """
    elapsed = np.cumsum(rr_ms) / 1000.0
    requested = baseline_minutes * 60.0

    rest_end = offset_sec + requested
    # The prelude may match the observed rest in length, and no more.
    rest_start = max(0.0, offset_sec - requested)

    resting = rr_ms[(elapsed > rest_start) & (elapsed <= rest_end)]
    task = rr_ms[elapsed > rest_end]

    # Where the cut LANDED, not where it was aimed. Empty means the recording
    # ended before the resting period did; the caller reports that as its own
    # failure, so the honest value here is the whole recording.
    actual_end = float(elapsed[elapsed <= rest_end].max()) if resting.size else 0.0
    return resting, task, actual_end
