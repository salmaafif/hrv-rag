"""
dataset.py — turning WESAD into sequences a model can be trained on.

This is the file where a deep-learning comparison is won or lost, because every
way of getting it wrong produces a BETTER-looking score, not a worse one. Three
decisions below are load-bearing, and each is made the way it is to keep the
comparison honest rather than to make the model look good.

1. SPLIT BY SUBJECT, NEVER BY SEGMENT.

   Segments overlap by 30 seconds (`SegmentationConfig.overlap_sec`). A split made
   per segment therefore puts two halves of the same 60 seconds of one person's
   heartbeat on opposite sides of the train/test boundary. The model would be
   tested on data it had already seen, and would report an excellent number that
   means nothing. `settings.split` is imported rather than restated so this cannot
   drift away from the split the RAG results were produced under.

2. NORMALISE AGAINST THE PERSON'S OWN BASELINE.

   Mandatory Rule #2. Resting interval length is deeply individual, so a model fed
   raw milliseconds can identify the subject and, with only five training
   subjects, will: it would learn "this is S6, and S6 segments are mostly resting"
   instead of learning what pressure looks like. Dividing by the subject's own
   resting mean removes the individual offset while leaving the beat-to-beat
   structure — which is the only thing a sequence model has to work with — fully
   intact.

   The raw form is still available through `normalise=False`, because "what does
   baseline normalisation buy the model?" is a fair ablation. It is not the
   default.

3. PAD TO THE PHYSIOLOGICAL CEILING; NEVER RESAMPLE, NEVER TRUNCATE.

   Segments hold a variable number of beats, because a fast heart fits more of
   them into sixty seconds. Two tempting fixes are both wrong here:

   - *Resampling to a fixed length* would interpolate the interval series, which
     is precisely the defect that made the SWELL package's `raw/rri` layer
     unusable (BACKLOG T7.1): RMSSD is defined between BEATS, and a smooth curve
     drawn through them is a different quantity that still looks reasonable.

   - *Truncating to a fixed length* would discard beats only from the segments
     that have the most of them — that is, the fastest hearts, which are
     disproportionately the stressed ones. The bias would run in exactly the
     direction of the thing being measured.

   So sequences are padded to a ceiling set by physiology, with a mask marking
   real beats. `n_beats` is kept alongside, because the beat COUNT is itself
   informative — it is heart rate — and a model given only the padded array with
   no mask would have to rediscover it from the padding.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hrv_rag.config.settings import settings
from hrv_rag.core.types import Modality, Phase
from hrv_rag.datasets.wesad import WESADLoader
from hrv_rag.evaluation.labels import WESAD_PHASE_TO_LABEL, TrueLabel
from hrv_rag.features.baseline import BaselineProfile
from hrv_rag.features.segmentation import segment_rr_series
from hrv_rag.preprocessing.ecg import ECGPreprocessor

#: Longest interval sequence a valid 60-second segment can hold.
#:
#: 200 beats per minute is `QualityConfig.rr_min_sec` expressed as a rate, so no
#: segment that survived the quality gates can exceed it. Padding to the ceiling
#: rather than to the longest sequence actually observed keeps the array shape
#: identical between the development and the sealed test set — a shape that
#: depended on the data would be a small, quiet channel from the test set back
#: into the model's design.
MAX_BEATS = 200

#: The two WESAD phases that carry a label. Amusement is excluded upstream: it is
#: positive arousal, not pressure, and mixing it in would corrupt the scale.
LABELLED_PHASES = (Phase.CALIBRATION, Phase.QUESTION)

#: Integer encoding of the ground truth, fixed here so every model and every
#: report agrees on which way round the classes are.
LABEL_TO_INT: dict[TrueLabel, int] = {TrueLabel.LOW: 0, TrueLabel.HIGH: 1}


@dataclass(frozen=True)
class SequenceDataset:
    """
    One split, ready for a sequence model.

    `subjects` travels with the arrays rather than being dropped after splitting,
    because per-subject results are reported for the rule baseline already
    (`evaluate_per_subject`) and the comparison has to be readable the same way.
    It also makes the leakage check below possible at all.
    """

    x: np.ndarray            # (n, MAX_BEATS) float32 — intervals, padded
    mask: np.ndarray         # (n, MAX_BEATS) bool    — True where a real beat sits
    y: np.ndarray            # (n,) int              — 0 low, 1 high
    subjects: np.ndarray     # (n,) str
    phases: np.ndarray       # (n,) str
    n_beats: np.ndarray      # (n,) int              — heart rate, in effect
    normalised: bool

    def __len__(self) -> int:
        return int(self.x.shape[0])

    def summary(self) -> str:
        low = int((self.y == 0).sum())
        high = int((self.y == 1).sum())
        return (f"{len(self)} segments from {len(set(self.subjects.tolist()))} "
                f"subjects — {low} low, {high} high; "
                f"beats {self.n_beats.min()}-{self.n_beats.max()} "
                f"(median {int(np.median(self.n_beats))})")


def build_subjects(subject_ids: list[str] | tuple[str, ...],
                   normalise: bool = True,
                   verbose: bool = False) -> SequenceDataset:
    """
    Build sequences for the named subjects, through the system's own pipeline.

    `ECGPreprocessor` and `segment_rr_series` are the same objects the RAG path
    uses, so the segments here ARE the segments there — including the ones the
    quality gates threw away. Giving the model windows the rule never saw would
    quietly hand it an advantage.

    A subject whose calibration phase yields no segment is skipped rather than
    included with a missing baseline: without a resting reference there is nothing
    to normalise against, and Mandatory Rule #2 has no meaning for that person.
    """
    x_rows, y_rows, subj_rows, phase_rows, n_rows = [], [], [], [], []

    for subject in subject_ids:
        loader = WESADLoader(subject)
        pre = ECGPreprocessor(sampling_rate=loader.sampling_rate(Modality.ECG))

        series_by_phase = {}
        for phase in LABELLED_PHASES:
            raw = loader.load_phase_signal(subject, phase, Modality.ECG)
            series_by_phase[phase] = pre.run(raw, subject=subject, phase=phase)

        reference = 1.0
        if normalise:
            baseline = BaselineProfile.from_series(
                subject, series_by_phase[Phase.CALIBRATION]
            )
            reference = _resting_mean_rr(baseline)
            if not np.isfinite(reference) or reference <= 0:
                if verbose:
                    print(f"  {subject}: no usable resting reference — skipped")
                continue

        for phase in LABELLED_PHASES:
            result = segment_rr_series(series_by_phase[phase])
            if verbose:
                print(f"  {subject} {phase.value:<12} {result.summary()}")

            for segment in result.segments:
                rr = np.asarray(segment.rr_ms, dtype=np.float64)
                if rr.size > MAX_BEATS:
                    # Physiologically impossible for a segment that passed the
                    # gates. Raised rather than clipped, because clipping is the
                    # biased-truncation failure this file exists to avoid.
                    raise ValueError(
                        f"{subject} {phase.value} segment {segment.index} holds "
                        f"{rr.size} beats, above the {MAX_BEATS}-beat ceiling. "
                        f"That is faster than the quality gates allow, so the "
                        f"segmentation or the gates have changed."
                    )
                x_rows.append(rr / reference)
                y_rows.append(LABEL_TO_INT[WESAD_PHASE_TO_LABEL[phase]])
                subj_rows.append(subject)
                phase_rows.append(phase.value)
                n_rows.append(rr.size)

    return _pack(x_rows, y_rows, subj_rows, phase_rows, n_rows, normalise)


def _resting_mean_rr(baseline: BaselineProfile) -> float:
    """
    The subject's own resting interval length, used as the normalising reference.

    `baseline.values["mean_rr"]` is the MEDIAN meanRR across the calibration
    windows — the very quantity every reactivity percentage in the RAG path is
    divided by. Taking it from here rather than recomputing an average over the
    resting series is the point: the comparator is then normalised by the
    identical number, not by something merely similar that could disagree with it
    in a way nobody would ever look for.
    """
    return float(baseline.values.get("mean_rr", float("nan")))


def _pack(x_rows, y_rows, subj_rows, phase_rows, n_rows,
          normalised: bool) -> SequenceDataset:
    n = len(x_rows)
    x = np.zeros((n, MAX_BEATS), dtype=np.float32)
    mask = np.zeros((n, MAX_BEATS), dtype=bool)
    for i, rr in enumerate(x_rows):
        x[i, : rr.size] = rr
        mask[i, : rr.size] = True

    return SequenceDataset(
        x=x, mask=mask,
        y=np.asarray(y_rows, dtype=np.int64),
        subjects=np.asarray(subj_rows, dtype=object),
        phases=np.asarray(phase_rows, dtype=object),
        n_beats=np.asarray(n_rows, dtype=np.int64),
        normalised=normalised,
    )


def build_dev(normalise: bool = True, verbose: bool = False) -> SequenceDataset:
    """The five development subjects. Everything is chosen on these and only these."""
    return build_subjects(settings.split.dev_subjects, normalise, verbose)


def build_holdout(normalise: bool = True, verbose: bool = False) -> SequenceDataset:
    """
    The ten sealed subjects. Touched ONCE, after every choice has been frozen.

    Worth stating plainly because the temptation is specific and strong: picking an
    architecture, an epoch count, or an early-stopping point by watching this set
    does not merely inflate the deep-learning number. It destroys the RAG figures
    too — accuracy 0.852, macro-F1 0.839, kappa 0.678 are honest only for as long
    as these ten subjects have never influenced a decision. There is no second
    sealed set to fall back on.
    """
    return build_subjects(settings.split.test_subjects, normalise, verbose)


def assert_no_leakage(train: SequenceDataset, test: SequenceDataset) -> None:
    """
    Refuse to proceed if any subject appears on both sides.

    A cheap check for the most expensive mistake available here. It is written as
    an assertion the caller must run rather than as a comment, because by the time
    a leaked result is on screen it looks like success.
    """
    shared = set(train.subjects.tolist()) & set(test.subjects.tolist())
    if shared:
        raise ValueError(
            f"Subjects appear in both splits: {sorted(shared)}. Segments overlap "
            f"by {settings.segmentation.overlap_sec} s, so this leaks halves of "
            f"the same window across the boundary and the score becomes fiction."
        )
