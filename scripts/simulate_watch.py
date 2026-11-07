"""
simulate_watch.py — Can a smartwatch heart rate carry the stress rule?

WHY THIS EXISTS. The system was validated on chest ECG, and the tier-T1 claim
(armband, heart rate only) already rests on an ablation: withholding RMSSD on the
ten sealed WESAD subjects gave macro-F1 0.871 against 0.839 with RMSSD included.
But that ablation withheld a feature from a PERFECT heart rate. A smartwatch does
not give a perfect heart rate. It gives a smoothed, delayed, occasionally wrong
one, sampled every few seconds, and it gives no beat-to-beat intervals at all.

So the honest question is not "is heart rate enough" — that is answered — but
"how wrong may the heart rate be before the rule stops working". This script
answers it as an ERROR BUDGET, measured on the sealed subjects with the frozen
rule, so the number can be compared with whatever a candidate watch is documented
to achieve.

TWO MODES.

  --budget   (default) Window-level error budget. Reads the holdout feature CSV
             and injects measurement error into the heart rate of every window,
             including the resting windows the personal baseline is built from.
             Runs anywhere; needs no raw signal.

  --emulate  Beat-level emulation from raw WESAD ECG: reporting interval,
             moving-average smoothing and its lag. Needs the WESAD pickles, so it
             only runs on the machine that has them.

THE ONE RESULT TO CARRY INTO A MEETING, established by --budget below: a watch
that is CONSISTENTLY wrong costs nothing, because every figure the rule uses is
relative to the same person measured by the same watch minutes earlier, so a
constant offset divides out. What costs accuracy is error that is random from
window to window, and error that appears only while the person is under pressure
— which is exactly when an optical sensor is worst, because the person is moving
and talking. Those two are budgeted separately here for that reason.

WHAT THIS IS NOT. It is a simulation of a watch, not a watch. It says how much
error the rule tolerates; it does not say how much error any particular watch
makes. That second number has to come from the device, and the plan is to measure
it directly against the HW9 armband before any watch is trusted.

Usage:
    python simulate_watch.py                    # error budget, real holdout data
    python simulate_watch.py --trials 500       # tighter intervals, slower
    python simulate_watch.py --emulate          # beat-level, needs WESAD
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Works both inside the hrv-rag repo (scripts/) and from a copy beside src/.
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE / "src", _HERE.parent / "src"):
    if (_candidate / "hrv_rag").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from hrv_rag.config.settings import OUTPUTS_DIR, settings          # noqa: E402
from hrv_rag.core.schemas import StressLevel                       # noqa: E402
from hrv_rag.evaluation.labels import (EvaluationRecord,           # noqa: E402
                                       TrueLabel, true_label)
from hrv_rag.evaluation.metrics import evaluate_classification     # noqa: E402
from hrv_rag.features.extractor import load_features               # noqa: E402
from hrv_rag.features.stress_level import RULE_VERSION, classify   # noqa: E402

HOLDOUT_CSV = OUTPUTS_DIR / "features_wesad_ecg_holdout.csv"

#: Fixed so the table is reproducible. Every configuration is drawn from the same
#: seed sequence, so two rows differ because their error model differs and not
#: because they happened to get different random numbers.
SEED = 20260911


# --------------------------------------------------------------------------
#  Scoring: the frozen rule, with RMSSD withheld
# --------------------------------------------------------------------------
def _label_from_hr(delta_pct_hr: float) -> TrueLabel:
    """
    Run the frozen rule on heart rate alone and fold it onto WESAD's two classes.

    RMSSD is set to NaN rather than omitted, because that is what a watch actually
    delivers: the field exists in the pipeline and carries no number. `_score_feature`
    awards it 0 points, so the verdict rests on the heart-rate arm — which is the
    situation being measured, not a special evaluation path.
    """
    verdict = classify({"delta_pct_rmssd": float("nan"),
                        "delta_pct_mean_hr": delta_pct_hr})
    return TrueLabel.LOW if verdict.level is StressLevel.LOW else TrueLabel.HIGH


def _score(frame: pd.DataFrame, delta_col: str,
           n_resamples: int = 0) -> tuple[float, float, float]:
    """
    macro-F1, kappa and accuracy for one column of heart-rate reactivity.

    `n_resamples` defaults to 0 — no bootstrap. The Monte-Carlo loops below call
    this thousands of times and each call would otherwise resample subjects two
    thousand times over, which is both slow and pointless: the spread that matters
    inside a loop is the spread ACROSS trials, and that is measured directly. The
    reference rows, which are computed once, keep the full interval.
    """
    records = []
    for row in frame.itertuples():
        truth = true_label(getattr(row, "phase"))
        if truth is None:
            continue
        records.append(EvaluationRecord(
            subject=row.subject, phase=row.phase, segment=int(row.segment),
            modality=row.modality, truth=truth,
            predicted=_label_from_hr(float(getattr(row, delta_col))),
            raw_level="", confidence=1.0, references=[], retrieved_ids=[],
            reasoning="", is_trustworthy=True,
        ))
    report = evaluate_classification(records, n_resamples=n_resamples)
    return report.macro_f1, report.kappa, report.accuracy


# --------------------------------------------------------------------------
#  The watch error model
# --------------------------------------------------------------------------
def apply_watch_error(frame: pd.DataFrame, rng: np.random.Generator, *,
                      scale_bias_pct: float = 0.0,
                      random_sd_bpm: float = 0.0,
                      stress_bias_bpm: float = 0.0,
                      round_to_integer: bool = True) -> pd.DataFrame:
    """
    Replace each window's heart rate with what a watch would have reported, then
    recompute reactivity the way the live system does.

    The four terms, and why each is separate:

    `scale_bias_pct`
        A constant proportional offset — the watch reads a fixed percentage high
        or low on this person. Included specifically to DEMONSTRATE that it does
        not matter: it multiplies the window and the baseline alike, and the ratio
        the rule reads is unchanged. Any calibration effort aimed at this term is
        effort spent on the one error that is already free.

    `random_sd_bpm`
        Independent error per reported window, in bpm. This is the term that costs
        accuracy, and it costs it twice over: once in the window being judged, and
        once in the resting windows the personal baseline is a median of. The
        baseline is better protected because a median over many resting windows
        averages the error down, which is modelled here by building the baseline
        from the noisy resting windows rather than from the clean ones.

    `stress_bias_bpm`
        Error that appears only while the person is under pressure. Negative values
        mean the watch under-reads the rise. Two real mechanisms produce it and
        both point the same way: a moving average lags a heart rate that is
        climbing, and an optical sensor degrades when the wearer moves and talks —
        which is what the stressed phase IS. This is the term that can quietly
        destroy the measurement while every static accuracy check still passes.

    `round_to_integer`
        Watches report whole bpm. Kept because it is free to model and because
        leaving it out would make the floor of the budget look better than it is.
    """
    out = frame.copy()

    # Recover each subject's own resting reference from the recorded reactivity.
    # meanHR = reference x (1 + delta/100), so the reference is recoverable exactly
    # and there is no need to re-run the signal pipeline to get it.
    measured = out["mean_hr"].to_numpy(dtype=float)

    watch = measured * (1.0 + scale_bias_pct / 100.0)
    if stress_bias_bpm:
        stressed = (out["phase"] == "question").to_numpy()
        watch = watch + stressed * stress_bias_bpm
    if random_sd_bpm:
        watch = watch + rng.normal(0.0, random_sd_bpm, size=watch.shape)
    if round_to_integer:
        watch = np.round(watch)

    out["watch_hr"] = watch

    # The baseline is the median of the RESTING windows as the watch saw them.
    # Taking it from the clean signal instead would hand the simulated watch a
    # reference no watch could ever have, and would flatter every row below.
    deltas = np.empty(len(out), dtype=float)
    for subject, idx in out.groupby("subject").groups.items():
        rows = out.loc[idx]
        resting = rows.loc[rows["phase"] == "calibration", "watch_hr"]
        reference = float(resting.median()) if len(resting) else float("nan")
        deltas[out.index.get_indexer(idx)] = (
            (rows["watch_hr"].to_numpy(dtype=float) - reference) / reference * 100.0
        )
    out["delta_pct_watch_hr"] = deltas
    return out


# --------------------------------------------------------------------------
#  Mode 1 — window-level error budget
# --------------------------------------------------------------------------
def run_budget(trials: int) -> None:
    if not HOLDOUT_CSV.exists():
        sys.exit(f"{HOLDOUT_CSV} not found. Run scripts/run_holdout.py first.")

    data = load_features(HOLDOUT_CSV)
    subjects = sorted(data["subject"].unique())

    print("=" * 74)
    print("WATCH ERROR BUDGET — sealed WESAD subjects, frozen rule "
          f"{RULE_VERSION}")
    print("=" * 74)
    print(f"  subjects  : {', '.join(subjects)}")
    print(f"  segments  : {len(data)}  (60 s windows, 30 s hop — not independent)")
    print(f"  thresholds: HR {settings.stress_rule.hr_moderate_pct:+.0f}% / "
          f"{settings.stress_rule.hr_high_pct:+.0f}%, RMSSD withheld (NaN)")
    print(f"  trials    : {trials} per configuration, seed {SEED}")
    print()

    # ---- reference rows -------------------------------------------------
    ecg_both = _score_with_classify(data, mask_rmssd=False)
    ecg_hr = _score_with_classify(data, mask_rmssd=True)

    rng = np.random.default_rng(SEED)
    perfect = apply_watch_error(data, rng, round_to_integer=False)
    perfect_score = _score(perfect, "delta_pct_watch_hr", n_resamples=2000)

    print("REFERENCE (no watch error)")
    print(f"  {'ECG, RMSSD + heart rate':<44} macro-F1 {ecg_both[0]:.3f}  "
          f"kappa {ecg_both[1]:.3f}")
    print(f"  {'ECG, heart rate only (ablation #9)':<44} macro-F1 {ecg_hr[0]:.3f}  "
          f"kappa {ecg_hr[1]:.3f}")
    print(f"  {'same, baseline re-derived here':<44} macro-F1 "
          f"{perfect_score[0]:.3f}  kappa {perfect_score[1]:.3f}")
    rng = np.random.default_rng(SEED)
    rounded = _score(apply_watch_error(data, rng), "delta_pct_watch_hr")
    print(f"  {'+ reported as whole bpm, nothing else':<44} macro-F1 "
          f"{rounded[0]:.3f}  kappa {rounded[1]:.3f}")
    print("  The third row rebuilds the personal reference from the resting")
    print("  windows in this table rather than from the denser resting hop the")
    print("  pipeline uses. Every watch row below is measured against IT, so the")
    print("  comparison isolates watch error and not the change of reference.")
    print()

    baseline_f1 = perfect_score[0]

    # ---- 1. constant offset --------------------------------------------
    print("-" * 74)
    print("1. CONSTANT OFFSET — a watch that reads a fixed percentage wrong")
    print("-" * 74)
    print(f"  {'offset':>10}   {'macro-F1':>9} {'kappa':>7} {'accuracy':>9}")
    for bias in (-10.0, -5.0, 0.0, 5.0, 10.0):
        rng = np.random.default_rng(SEED)
        scored = _score(apply_watch_error(data, rng, scale_bias_pct=bias,
                                          round_to_integer=False),
                        "delta_pct_watch_hr")
        print(f"  {bias:>9.0f}%   {scored[0]:9.3f} {scored[1]:7.3f} "
              f"{scored[2]:9.3f}")
    print("  Unchanged, as it must be: the window and the baseline are scaled by")
    print("  the same factor and the rule only ever reads their ratio. This is")
    print("  Mandatory Rule #2 paying for itself — a watch does not need to agree")
    print("  with a clinical monitor, it needs to disagree with it consistently.")
    print()

    # ---- 2. random error -------------------------------------------------
    print("-" * 74)
    print("2. RANDOM ERROR — independent per reported window")
    print("-" * 74)
    print(f"  {'SD (bpm)':>9}   {'macro-F1':>9} {'5-95%':>15} {'vs clean':>9}")
    for sd in (0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0):
        f1s = []
        for t in range(trials):
            rng = np.random.default_rng(SEED + t)
            f1s.append(_score(apply_watch_error(data, rng, random_sd_bpm=sd),
                              "delta_pct_watch_hr")[0])
        f1s = np.array(f1s)
        lo, hi = np.percentile(f1s, [5, 95])
        print(f"  {sd:>9.0f}   {f1s.mean():9.3f} {lo:7.3f}-{hi:<7.3f} "
              f"{f1s.mean() - baseline_f1:+9.3f}")
    print()

    # ---- 3. stress-only bias --------------------------------------------
    print("-" * 74)
    print("3. UNDER-READING UNDER PRESSURE — error only while stressed")
    print("-" * 74)
    print(f"  {'bias (bpm)':>11}   {'macro-F1':>9} {'5-95%':>15} {'vs clean':>9}")
    for bias in (0.0, -2.0, -4.0, -6.0, -8.0, -12.0):
        f1s = []
        for t in range(trials):
            rng = np.random.default_rng(SEED + t)
            f1s.append(_score(apply_watch_error(data, rng, stress_bias_bpm=bias),
                              "delta_pct_watch_hr")[0])
        f1s = np.array(f1s)
        lo, hi = np.percentile(f1s, [5, 95])
        print(f"  {bias:>11.0f}   {f1s.mean():9.3f} {lo:7.3f}-{hi:<7.3f} "
              f"{f1s.mean() - baseline_f1:+9.3f}")
    print()

    # ---- 4. a plausible combined device ---------------------------------
    print("-" * 74)
    print("4. COMBINED — the two terms together")
    print("-" * 74)
    print(f"  {'SD':>5} {'stress bias':>12}   {'macro-F1':>9} {'5-95%':>15}")
    for sd, bias in ((2.0, -2.0), (3.0, -4.0), (5.0, -4.0), (5.0, -8.0),
                     (8.0, -8.0)):
        f1s = []
        for t in range(trials):
            rng = np.random.default_rng(SEED + t)
            f1s.append(_score(apply_watch_error(data, rng, random_sd_bpm=sd,
                                                stress_bias_bpm=bias),
                              "delta_pct_watch_hr")[0])
        f1s = np.array(f1s)
        lo, hi = np.percentile(f1s, [5, 95])
        print(f"  {sd:>5.0f} {bias:>12.0f}   {f1s.mean():9.3f} "
              f"{lo:7.3f}-{hi:<7.3f}")
    print()
    print("HOW TO USE THIS TABLE. Find the row matching what the candidate watch")
    print("is documented to do against ECG, and read the macro-F1 beside it. If a")
    print("device has no published agreement figure for the CONDITION that matters")
    print("— seated, talking, arousal rising — then it has no row here and the")
    print("honest report is that its accuracy is unknown, not that it is adequate.")


def _score_with_classify(data: pd.DataFrame,
                         mask_rmssd: bool) -> tuple[float, float, float]:
    """The published reference figures, recomputed rather than quoted."""
    records = []
    for _, row in data.iterrows():
        truth = true_label(row["phase"])
        if truth is None:
            continue
        reactivity = {c: row[c] for c in row.index if c.startswith("delta_pct_")}
        if mask_rmssd:
            reactivity["delta_pct_rmssd"] = float("nan")
        verdict = classify(reactivity)
        records.append(EvaluationRecord(
            subject=str(row["subject"]), phase=str(row["phase"]),
            segment=int(row["segment"]), modality=str(row["modality"]),
            truth=truth,
            predicted=(TrueLabel.LOW if verdict.level is StressLevel.LOW
                       else TrueLabel.HIGH),
            raw_level=verdict.level.value, confidence=1.0, references=[],
            retrieved_ids=[], reasoning="", is_trustworthy=True,
        ))
    report = evaluate_classification(records)
    return report.macro_f1, report.kappa, report.accuracy


# --------------------------------------------------------------------------
#  Mode 2 — beat-level emulation from raw ECG
# --------------------------------------------------------------------------
def run_emulate(trials: int) -> None:
    """
    Rebuild a watch heart-rate STREAM from the ECG beats, then segment that.

    The budget mode above injects error into a window average. This mode instead
    reconstructs what the watch would have been reporting second by second, and
    only then averages — which is the only way to see the two things a window-level
    model cannot represent: the lag a moving average introduces at the moment the
    heart rate changes, and the effect of reporting a value only every few seconds.

    Needs the WESAD pickles, because the beats are the input.
    """
    from hrv_rag.core.types import Modality, Phase
    from hrv_rag.datasets.wesad import WESADLoader
    from hrv_rag.preprocessing.ecg import ECGPreprocessor

    subjects = list(settings.split.test_subjects)
    seg = settings.segmentation

    print("=" * 74)
    print("WATCH STREAM EMULATION — beat-level, sealed WESAD subjects")
    print("=" * 74)
    print(f"  subjects: {', '.join(subjects)}")
    print("  Reference heart rate is 60000/mean(RR) over each 60 s window, the")
    print("  same definition time_domain.mean_hr uses. The watch stream is built")
    print("  from the same beats and then averaged ARITHMETICALLY, because that")
    print("  is what a watch reports — mean(60/RR) is not 60/mean(RR), and the")
    print("  difference is part of what is being measured here.")
    print()
    print("  LIMITATION, and it is the important one. WESAD's resting and TSST")
    print("  blocks are not adjacent in the recording — amusement and meditation")
    print("  sit between them — so each is extracted as its own contiguous run and")
    print("  the smoothing never crosses the moment stress begins. What this table")
    print("  measures is therefore blurring and sparse reporting WITHIN a steady")
    print("  state. The lag at the transition, which is where a moving average")
    print("  hurts most, is not in these numbers and has to come from a recording")
    print("  where calm and pressure actually follow one another — the three-block")
    print("  protocol on the HW9, run again with a watch on the other wrist.\n")

    CONFIGS = EMULATION_CONFIGS
    per_config: dict[tuple[int, int], list[dict]] = {c: [] for c in CONFIGS}
    reference_rows: list[dict] = []

    for subject in subjects:
        loader = WESADLoader(subject)
        pre = ECGPreprocessor(sampling_rate=loader.sampling_rate(Modality.ECG))
        for phase in (Phase.CALIBRATION, Phase.QUESTION):
            raw = loader.load_phase_signal(subject, phase, Modality.ECG)
            series = pre.run(raw, subject=subject, phase=phase)
            _collect_windows(np.asarray(series.t_sec, dtype=float),
                             np.asarray(series.rr_ms, dtype=float),
                             subject, phase.value, CONFIGS,
                             reference_rows, per_config)
        print(f"  {subject} done")

    _report_emulation(reference_rows, per_config)


def _report_emulation(reference_rows: list[dict],
                      per_config: dict[tuple[int, int], list[dict]]) -> None:
    """Score every watch configuration against the beat-derived reference."""
    reference = pd.DataFrame(reference_rows)
    rng = np.random.default_rng(SEED)
    ref_score = _score(apply_watch_error(reference, rng, round_to_integer=False),
                       "delta_pct_watch_hr")
    print(f"\n  reference (beat-derived heart rate)  macro-F1 {ref_score[0]:.3f}  "
          f"kappa {ref_score[1]:.3f}\n")

    print(f"  {'report':>7} {'smooth':>7}   {'macro-F1':>9} {'kappa':>7} "
          f"{'vs reference':>13}")
    print("  " + "-" * 54)
    for (interval, smooth), rows in per_config.items():
        frame = pd.DataFrame(rows)
        rng = np.random.default_rng(SEED)
        # round_to_integer is off here: `_watch_stream` already reports whole bpm,
        # and rounding a second time would quantise an already-quantised number.
        score = _score(apply_watch_error(frame, rng, round_to_integer=False),
                       "delta_pct_watch_hr")
        print(f"  {interval:>6}s {smooth:>6}s   {score[0]:9.3f} {score[1]:7.3f} "
              f"{score[0] - ref_score[0]:+13.3f}")

    print("\n  A row that barely moves means the rule survives that much blurring.")
    print("  A row that collapses is a configuration no watch may be used in.")


#: The nine watch configurations, as (reporting interval, smoothing window) in
#: seconds. Declared once so `--emulate` and `--selftest` cannot drift apart.
EMULATION_CONFIGS: list[tuple[int, int]] = [
    (1, 0), (1, 5), (1, 10), (1, 30),
    (5, 10), (5, 30),
    (10, 10), (10, 30),
    (30, 30),
]


def run_selftest() -> None:
    """
    Exercise the whole emulation path on invented beats, with no dataset present.

    THIS PROVES NOTHING ABOUT WATCHES and its numbers must never be quoted. The
    beats are generated from a chosen heart rate, so the answer is known before the
    code runs; what is being checked is that the windowing, the stream
    reconstruction and the scoring all agree on which minute they are talking
    about. That check is worth having separately, because on the machine where
    WESAD lives a crash costs a reload of several hundred megabytes to discover.

    A real run is `--emulate`. This is the rehearsal.
    """
    print("=" * 74)
    print("SELF-TEST — synthetic beats, invented people, numbers not for quoting")
    print("=" * 74)

    rng = np.random.default_rng(SEED)
    reference_rows: list[dict] = []
    per_config: dict[tuple[int, int], list[dict]] = {
        c: [] for c in EMULATION_CONFIGS}

    for n in range(10):
        subject = f"X{n + 1}"
        resting_bpm = float(rng.uniform(62, 82))
        # Deliberately straddles the rule's +5% threshold. A rehearsal where every
        # invented person reacts enormously scores 1.000 in every configuration and
        # would therefore still print a clean table if the windowing were broken.
        rise = float(rng.uniform(1.0, 10.0))
        for phase, bpm, minutes in (("calibration", resting_bpm, 20),
                                    ("question", resting_bpm + rise, 10)):
            t, rr = _synthetic_beats(bpm, minutes * 60, rng)
            _collect_windows(t, rr, subject, phase, EMULATION_CONFIGS,
                             reference_rows, per_config)

    print(f"  built {len(reference_rows)} reference windows from 10 invented "
          f"subjects\n")
    _report_emulation(reference_rows, per_config)
    print("\n  If this printed a table, the emulation path runs. Whether it says")
    print("  anything true is what --emulate is for.")


def _synthetic_beats(bpm: float, duration_sec: float,
                     rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """
    A beat series at a chosen average rate, with respiratory-looking variability.

    The sinusoid is there so successive intervals are not independent — a series of
    independent draws would have no structure for a moving average to smooth, and
    would make every smoothing configuration look identical for the wrong reason.
    """
    mean_rr = 60000.0 / bpm
    t, rr, clock = [], [], 0.0
    while clock < duration_sec:
        breathing = 1.0 + 0.04 * np.sin(2 * np.pi * clock / 4.0)
        interval = mean_rr * breathing + rng.normal(0.0, 12.0)
        interval = float(np.clip(interval, 300.0, 2000.0))
        clock += interval / 1000.0
        t.append(clock)
        rr.append(interval)
    return np.asarray(t), np.asarray(rr)


def _collect_windows(t_sec: np.ndarray, rr_ms: np.ndarray, subject: str,
                     phase: str, configs: list[tuple[int, int]],
                     reference_rows: list[dict],
                     per_config: dict[tuple[int, int], list[dict]]) -> None:
    """
    Cut one phase's beats into the same windows `segmentation.py` would, once for
    the beat-derived reference and once per watch configuration.

    Split out of `run_emulate` so `--selftest` can exercise it on a synthetic beat
    series. Everything here except the loading is the part that can be wrong, and
    the loading is the part that cannot run without the dataset — so this is the
    line to cut on.

    The window grid is recomputed rather than reused from `segment_rr_series`,
    because the watch stream has to be averaged over the SAME intervals as the
    reference. Taking the reference windows from the segmenter and the watch
    windows from anywhere else would compare two different minutes.
    """
    seg = settings.segmentation
    if t_sec.size < 2:
        return
    t0 = float(t_sec[0])
    duration = float(t_sec[-1]) - t0
    n_windows = int((duration - seg.length_sec) // seg.hop_sec) + 1
    if n_windows < 1:
        return

    bounds = []
    for i in range(n_windows):
        start = t0 + i * seg.hop_sec
        end = start + seg.length_sec
        inside = (t_sec >= start) & (t_sec < end)
        if inside.sum() < seg.min_beats:
            continue
        bounds.append((i + 1, start, end, inside))
        reference_rows.append({
            "subject": subject, "phase": phase, "segment": i + 1,
            "modality": "ECG",
            "mean_hr": 60000.0 / float(np.mean(rr_ms[inside])),
        })

    for interval, smooth in configs:
        grid, values = _watch_stream(t_sec, rr_ms, interval, smooth)
        for index, start, end, _ in bounds:
            in_grid = (grid >= start) & (grid < end)
            if not in_grid.any():
                continue
            per_config[(interval, smooth)].append({
                "subject": subject, "phase": phase, "segment": index,
                "modality": "ECG",
                "mean_hr": float(np.mean(values[in_grid])),
            })


def _watch_stream(t_sec: np.ndarray, rr_ms: np.ndarray,
                  interval_sec: int, smooth_sec: int) -> tuple[np.ndarray,
                                                               np.ndarray]:
    """
    Turn a beat series into the heart-rate stream a watch would have reported.

    Three steps, in the order the device performs them:

    1. Instantaneous rate per beat, 60000/RR. A watch does not have RR intervals
       to average the way `time_domain.mean_hr` does; it has a rate estimate.
    2. A trailing moving average of `smooth_sec` seconds. Trailing, not centred:
       a device cannot average over beats that have not happened yet, and that
       asymmetry is precisely the lag this function exists to reproduce.
    3. Sampling of the smoothed curve every `interval_sec` seconds, rounded to
       whole bpm, which is the granularity every consumer watch reports.
    """
    inst = 60000.0 / rr_ms
    grid = np.arange(float(t_sec[0]), float(t_sec[-1]), float(interval_sec))
    if grid.size == 0:
        return grid, grid

    # Averages over a trailing window are prefix sums, not a loop. Written the
    # obvious way this function walked every beat for every reported second, which
    # on ten subjects times nine configurations is hundreds of millions of
    # comparisons and turns a two-minute run into an hour.
    upper = np.searchsorted(t_sec, grid, side="right")
    if smooth_sec > 0:
        lower = np.searchsorted(t_sec, grid - smooth_sec, side="right")
        cumulative = np.concatenate(([0.0], np.cumsum(inst)))
        count = upper - lower
        with np.errstate(invalid="ignore", divide="ignore"):
            values = np.where(count > 0,
                              (cumulative[upper] - cumulative[lower])
                              / np.maximum(count, 1),
                              np.nan)
    else:
        # No smoothing: the device reports the rate of the most recent beat.
        values = np.where(upper > 0, inst[np.maximum(upper - 1, 0)], np.nan)

    # A watch that has nothing new to report repeats its last value; it does not
    # go blank. Forward-filling reproduces that, and it matters because a gap is
    # exactly where a naive implementation would silently drop the window.
    values = pd.Series(values).ffill().bfill().to_numpy()
    return grid, np.round(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulate", action="store_true",
                        help="beat-level emulation from raw WESAD ECG")
    parser.add_argument("--selftest", action="store_true",
                        help="run the emulation path on invented beats, no dataset")
    parser.add_argument("--trials", type=int, default=200,
                        help="Monte-Carlo repetitions per noisy configuration")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.selftest:
        run_selftest()
    elif args.emulate:
        run_emulate(args.trials)
    else:
        run_budget(args.trials)


if __name__ == "__main__":
    main()
