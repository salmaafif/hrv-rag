"""
run_session.py — Session-level report: reactivity, arousal, recovery, resilience.

Shows what the product actually produces for one user: a per-question breakdown plus
the session summary. Everything printed here is computed by code, so it runs with NO
API calls at all.

WESAD has no interview questions, so the TSST phase is divided into equal windows
that stand in for questions. That substitution is a demonstration device, not a
measurement claim: the numbers are real, but which "question" a window represents is
arbitrary. Real sessions supply a genuine timeline.

Usage:
    python scripts/run_session.py              # all development subjects
    python scripts/run_session.py S14
    python scripts/run_session.py --with-llm   # also ask Gemini to interpret
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np                                              # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings       # noqa: E402
from hrv_rag.core.session import (Question, QuestionType,       # noqa: E402
                                  SessionTimeline)
from hrv_rag.features.baseline import BaselineProfile           # noqa: E402
from hrv_rag.features.dynamics import resilience_quadrant       # noqa: E402
from hrv_rag.features.extractor import load_features            # noqa: E402
from hrv_rag.features.question import (cognitive_load_hint,      # noqa: E402
                                       measure_question)
from hrv_rag.features.stress_level import classify              # noqa: E402

FEATURES_CSV = OUTPUTS_DIR / "features_wesad_ecg_dev.csv"

#: Question types assigned to the stand-in windows, alternating between the two
#: families so the cognitive-versus-social attribution can be seen at work.
TYPES = [QuestionType.INTRODUCTION, QuestionType.BEHAVIOURAL,
         QuestionType.TECHNICAL, QuestionType.NUMERICAL]

#: Matches SessionConfig: 90 s to answer, then a 60 s gap after difficult questions.
ANSWER_SEC = settings.session.answer_sec
GAP_SEC = settings.session.recovery_gap_sec


def build_timeline(subject: str, n_questions: int = 4) -> SessionTimeline:
    """
    Lay out stand-in questions across the stressed phase.

    Every second question is marked difficult and therefore gets a full recovery
    gap. That mirrors decision K11 — a 60-second gap is the hard floor for measuring
    recovery, so giving one to every question would make the session too long.
    """
    timeline = SessionTimeline(
        session_id=subject,
        calibration_start_sec=0.0,
        calibration_end_sec=float(settings.session.calibration_sec),
        confounders=[],
    )
    cursor = 0.0
    for i in range(n_questions):
        difficult = (i % 2 == 0)
        timeline.questions.append(Question(
            number=i + 1,
            text=f"Question {i + 1}",
            qtype=TYPES[i % len(TYPES)],
            answer_start_sec=cursor,
            answer_end_sec=cursor + ANSWER_SEC,
            gap_end_sec=(cursor + ANSWER_SEC + GAP_SEC) if difficult else None,
            is_difficult=difficult,
        ))
        cursor += ANSWER_SEC + (GAP_SEC if difficult else 20)
    return timeline


def report_subject(subject: str, data) -> None:
    session = data[data["subject"] == subject]
    calibration = session[session["phase"] == "calibration"]
    stressed = session[session["phase"] == "question"].copy()

    if calibration.empty or stressed.empty:
        print(f"  {subject}: not enough data\n")
        return

    # Re-zero the time axis so the stressed phase starts at t=0, matching the
    # timeline's own coordinates.
    stressed["start_sec"] -= stressed["start_sec"].min()
    stressed["end_sec"] = stressed["start_sec"] + settings.segmentation.length_sec

    baseline = BaselineProfile.from_segments(subject, calibration)
    timeline = build_timeline(subject)

    print(f"--- {subject} ---")
    print(f"  {baseline.describe()}")
    spread = baseline.relative_spread("rmssd")
    if spread == spread and spread > 0.40:
        print(f"  WARNING: unsteady baseline (relative IQR {spread:.0%}) — "
              f"reactivity below is less certain")

    # Heart-rate change is printed ONCE. The arousal index returns that same number
    # under another name, so showing both columns would dress a single measurement
    # up as two agreeing ones.
    print(f"\n  {'no':<3} {'type':<13} {'dRMSSD':>8} {'dHR = arousal':>14} "
          f"{'recovery':>15}  {'LEVEL':<9} score")
    print("  " + "-" * 82)

    reactivities, recoveries = [], []
    for question in timeline.questions:
        m = measure_question(question, stressed, baseline)
        if not m.has_data:
            print(f"  {question.number:<3} {question.qtype.value:<13} "
                  f"no usable segment")
            continue

        d_rmssd = m.reactivity.get("delta_pct_rmssd", float("nan"))
        d_hr = m.reactivity.get("delta_pct_mean_hr", float("nan"))
        _, hint = cognitive_load_hint(question.qtype, m.reactivity)

        recovery = (f"{m.recovery.percent:.0f}%" if m.recovery.is_computable
                    else "not computable")
        reactivities.append(d_rmssd)
        if m.recovery.is_computable:
            recoveries.append(m.recovery.percent)

        verdict = classify(m.reactivity)
        flag = " (!)" if any("disagree" in e for e in verdict.evidence) else ""
        print(f"  {question.number:<3} {question.qtype.value:<13} "
              f"{d_rmssd:7.1f}% {d_hr:13.1f}% {recovery:>15}  "
              f"{verdict.level.value:<9} {verdict.points}/4 pts{flag}")

    if not reactivities:
        print()
        return

    median_reactivity = float(np.median(reactivities))
    median_recovery = float(np.median(recoveries)) if recoveries else None
    quadrant = resilience_quadrant(median_reactivity, median_recovery)
    most = int(np.argmin(reactivities)) + 1

    print(f"\n  median reactivity : {median_reactivity:.1f}%")
    print(f"  median recovery   : "
          f"{'not computable' if median_recovery is None else f'{median_recovery:.0f}%'}")
    print(f"  most triggering   : question {most}")
    print(f"  resilience        : "
          f"{quadrant.value if quadrant else 'cannot be determined'}")
    print("  (!) marks a question where the features disagreed: RMSSD rose "
          "while heart rate also rose\n")


def main(args: list[str]) -> None:
    if not FEATURES_CSV.exists():
        sys.exit(f"{FEATURES_CSV} not found. Run scripts/run_features.py first.")

    data = load_features(FEATURES_CSV)
    subjects = [a for a in args if not a.startswith("--")]
    if not subjects:
        subjects = list(settings.split.dev_subjects)

    print("Session-level report — every number below is plain arithmetic on the "
          "measured signal.")
    print("No model, no training, no prediction: each figure compares this person "
          "against their own")
    print("resting baseline, recorded minutes earlier.")
    print("The LEVEL column comes from a scoring rule, not the LLM: same input, "
          "same label, every time.")
    print("Explaining that label in words is the LLM's job, and needs API "
          "access.\n")
    for subject in subjects:
        report_subject(subject, data)

    if "--with-llm" in args:
        print("=" * 70)
        print("LLM interpretation requires API quota; run without --with-llm "
              "to stay offline.")


if __name__ == "__main__":
    main(sys.argv[1:])
