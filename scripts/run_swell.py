"""
run_swell.py — Stage 7: the scoring rule against SWELL-KW's three stress levels.

    python scripts/run_swell.py              # the 14 subjects with all three levels
    python scripts/run_swell.py --any        # 22 subjects, at least one stressor

Offline. No API key, no quota: the label comes from `features/stress_level.py`,
which is deterministic (decision K16).

WHY THIS DATASET EARNS ITS PLACE
--------------------------------
WESAD answered whether pressure is detected at all, and answered it well
(macro-F1 0.839 on ten sealed subjects). What it could never answer is where the
line between MODERATE and HIGH belongs, because it has only two conditions: any
threshold that separated them mapped both onto the same class, so all 81 candidate
combinations in the calibration sweep scored identically (BACKLOG T2c.10).

SWELL-KW has a genuine gradient — neutral work, then the same task with a third of
the time removed, then that plus eight unexpected interruptions. Each step adds a
demand without withdrawing the previous one, so for the first time the ordering of
the labels is a property of the experiment rather than an interpretation of it.

WHAT MUST BE SAID ALONGSIDE ANY NUMBER THIS PRINTS
--------------------------------------------------
The HRV features here were computed by the SWELL authors, not by this project's
`features/` code. Mandatory Rule #1 still holds — nothing is computed by an LLM —
but WESAD figures came from this pipeline end to end and these did not. The two
are therefore reported side by side, never pooled, exactly as CLAUDE.md requires.

See `datasets/swell.py` for why this layer of the dataset was used and the other
two were rejected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hrv_rag.datasets.swell import (load_swell_minutes,  # noqa: E402
                                    usable_subjects)
from hrv_rag.evaluation.labels import (EvaluationRecord,  # noqa: E402
                                       predicted_label, true_label)
from hrv_rag.evaluation.metrics import (evaluate_classification,  # noqa: E402
                                        evaluate_per_subject)
from hrv_rag.features.baseline import BaselineProfile  # noqa: E402
from hrv_rag.features.stress_level import classify  # noqa: E402

#: The two features the scoring rule reads. Nothing else is available in this
#: dataset — no LF/HF, no pNN50, no SDNN — which is fine for the rule but does
#: leave the retrieval query thinner than on WESAD.
FEATURES = ["rmssd", "mean_hr"]


def build_records(table: pd.DataFrame, subjects: list[str]
                  ) -> list[EvaluationRecord]:
    """
    Score every working minute against its own subject's resting baseline.

    The baseline is built per subject and only from the rest block, which is what
    Mandatory Rule #2 demands: HRV varies so much between people that comparing
    one person's raw RMSSD to another's says almost nothing. What is modelled is
    how far each person moved from their own quiet state.
    """
    records: list[EvaluationRecord] = []

    for subject in subjects:
        rows = table[table["subject"] == subject]
        rest = rows[rows["phase"] == "calibration"]
        baseline = BaselineProfile.from_segments(subject, rest[FEATURES])

        for _, row in rows.iterrows():
            truth = true_label(str(row["phase"]), dataset="SWELL")
            if truth is None:            # the rest block anchors, it is not scored
                continue

            reactivity = baseline.reactivity(
                {feature: float(row[feature]) for feature in FEATURES}
            )
            verdict = classify(reactivity)

            records.append(EvaluationRecord(
                subject=subject,
                phase=str(row["phase"]),
                segment=int(row["segment"]),
                modality="ECG",
                truth=truth,
                predicted=predicted_label(verdict.level.value, dataset="SWELL"),
                raw_level=verdict.level.value,
                confidence=1.0,          # a rule states its answer; it does not rate it
                references=[],
                retrieved_ids=[],
                reasoning=verdict.describe(),
                is_trustworthy=True,
            ))

    return records


def main(argv: list[str]) -> int:
    require_all = "--any" not in argv

    try:
        table = load_swell_minutes()
    except FileNotFoundError as exc:
        print(exc)
        return 1

    subjects = usable_subjects(table, require_all_conditions=require_all)
    print("=" * 78)
    print("SWELL-KW — scoring rule against three stress levels (Stage 7)")
    print("=" * 78)
    print(f"  subjects used : {len(subjects)} of {table['subject'].nunique()}"
          f"  ({'all three conditions' if require_all else 'at least one stressor'})")
    print(f"  minutes       : {len(table[table['subject'].isin(subjects)])}")
    print("  features      : RMSSD and heart rate, computed by the SWELL authors")
    print("  windows       : 1 minute, NOT overlapping — so unlike WESAD, these")
    print("                  observations are independent (BACKLOG L2 does not apply)\n")

    if not subjects:
        print("  No subject has both a usable rest block and a stressor condition.")
        return 1

    records = build_records(table, subjects)
    report = evaluate_classification(records, dataset="SWELL", modality="ECG")
    print(report.summary())

    print("\n  accuracy per subject:")
    for subject, accuracy in sorted(evaluate_per_subject(records).items()):
        print(f"    {subject:5s} {accuracy:.3f}")

    print("\n  where the errors fall (truth -> predicted):")
    confusion = pd.crosstab(
        pd.Series([r.truth.value for r in records], name="truth"),
        pd.Series([r.raw_level for r in records], name="predicted"),
    )
    print("   " + confusion.to_string().replace("\n", "\n   "))

    print("\n  Report these numbers BESIDE the WESAD figures, never merged with")
    print("  them: different subjects, different stressor, and features computed")
    print("  by different code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
