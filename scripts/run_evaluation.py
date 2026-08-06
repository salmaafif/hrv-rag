"""
run_evaluation.py — Stage 5: assess segments and score the result.

Each assessed segment costs one Gemini call, and the free tier allows only 20 calls
per day. Completed assessments are therefore CACHED to disk: rerun the script on a
later day and it picks up where it stopped, skipping everything already done.

Only development subjects are ever touched. The ten test subjects stay sealed until
the prompt and the knowledge base are frozen (BACKLOG U4.1).

Usage:
    python scripts/run_evaluation.py                 # 40-segment sample
    python scripts/run_evaluation.py --n 80
    python scripts/run_evaluation.py --full          # all 293, takes several days
    python scripts/run_evaluation.py --pinned        # with KB-INTERP-01 pinned (T4.7)
    python scripts/run_evaluation.py --rules-only    # no API calls at all
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd                                             # noqa: E402

from hrv_rag.config.settings import OUTPUTS_DIR, settings       # noqa: E402
from hrv_rag.evaluation.cache import AssessmentCache, cache_key  # noqa: E402
from hrv_rag.evaluation.labels import (EvaluationRecord,        # noqa: E402
                                       TrueLabel, predicted_label, true_label)
from hrv_rag.evaluation.metrics import (evaluate_classification,  # noqa: E402
                                        evaluate_per_subject)
from hrv_rag.evaluation.rag_metrics import (measure_calibration,  # noqa: E402
                                            measure_faithfulness)
from hrv_rag.evaluation.rule_baseline import (rule_rmssd_and_hr,  # noqa: E402
                                              rule_rmssd_only)
from hrv_rag.features.extractor import load_features            # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_assessment import FEATURES_CSV, row_to_input           # noqa: E402


def stratified_sample(data: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    Take a balanced sample across subjects and phases.

    Balance matters: a random draw would over-represent calibration, which supplies
    roughly twice as many segments as the question phase, so the metrics would end up
    describing the resting state more than the stressed one.
    """
    n_groups = data["subject"].nunique() * data["phase"].nunique()
    per_group = max(1, n // n_groups)
    return (data.groupby(["subject", "phase"], group_keys=False)
                .head(per_group)
                .reset_index(drop=True))


def build_record(row: pd.Series, truth: TrueLabel, assessment) -> EvaluationRecord:
    return EvaluationRecord(
        subject=str(row["subject"]),
        phase=str(row["phase"]),
        segment=int(row["segment"]),
        modality=str(row["modality"]),
        truth=truth,
        predicted=predicted_label(assessment.response.stress_level.value),
        raw_level=assessment.response.stress_level.value,
        confidence=assessment.response.confidence,
        references=assessment.response.references,
        retrieved_ids=assessment.retrieved_ids,
        reasoning=assessment.response.reasoning,
        is_trustworthy=assessment.is_trustworthy,
    )


def report_rule_baselines(data: pd.DataFrame) -> None:
    """
    Score the threshold comparators (U3.1).

    Runs on whatever rows it is given and needs no API access, which is why it can be
    reported even when the LLM quota is exhausted.
    """
    print("\n" + "=" * 68)
    print(f"RULE-BASED COMPARATORS, no LLM — {len(data)} segments (U3.1)")
    print("=" * 68)

    variants = [
        ("always low", lambda _: TrueLabel.LOW),
        ("RMSSD only", rule_rmssd_only),
        ("RMSSD or heart rate", rule_rmssd_and_hr),
    ]
    for name, rule in variants:
        records = []
        for _, row in data.iterrows():
            truth = true_label(row["phase"])
            if truth is None:
                continue
            records.append(EvaluationRecord(
                subject=str(row["subject"]), phase=str(row["phase"]),
                segment=int(row["segment"]), modality=str(row["modality"]),
                truth=truth, predicted=rule(row_to_input(row).reactivity),
                raw_level="", confidence=1.0, references=[], retrieved_ids=[],
                reasoning="", is_trustworthy=True,
            ))
        report = evaluate_classification(records)
        print(f"\n  [{name}]")
        print(f"    accuracy {report.accuracy:.3f} | "
              f"macro-F1 {report.macro_f1:.3f} | kappa {report.kappa:.3f}")
        per_subject = evaluate_per_subject(records)
        print("    per subject: "
              + "  ".join(f"{s}={a:.2f}" for s, a in per_subject.items()))


def main() -> None:
    if not FEATURES_CSV.exists():
        sys.exit(f"{FEATURES_CSV} not found. Run scripts/run_features.py first.")

    data = load_features(FEATURES_CSV)

    if "--rules-only" in sys.argv:
        report_rule_baselines(data)
        return

    n = 40
    if "--n" in sys.argv:
        position = sys.argv.index("--n") + 1
        if position >= len(sys.argv):
            sys.exit("--n needs a number, e.g. --n 20")
        try:
            n = int(sys.argv[position])
        except ValueError:
            sys.exit(f"--n needs a number, got {sys.argv[position]!r}")
        if n < 1:
            sys.exit(f"--n must be at least 1, got {n}")
    subset = data if "--full" in sys.argv else stratified_sample(data, n)

    cfg = settings.rag
    if "--pinned" in sys.argv:
        cfg = replace(cfg, pinned_chunk_id="KB-INTERP-01")
        print("Rubric chunk KB-INTERP-01 pinned into every prompt (T4.7)")

    # Imported here so that --rules-only never needs an API key.
    from hrv_rag.rag.pipeline import AssessmentPipeline
    from hrv_rag.rag.retrieval import KBIndex

    pipeline = AssessmentPipeline(index=KBIndex.load(cfg=cfg))
    cache = AssessmentCache(OUTPUTS_DIR / "assessment_cache.jsonl")

    print(cache.summary())
    print(f"Evaluating {len(subset)} segments from "
          f"{subset['subject'].nunique()} development subjects.")
    print(f"Rate limit {settings.llm.requests_per_minute}/min, "
          f"free tier allows 20/day.\n")

    records, assessments = [], []
    for i, (_, row) in enumerate(subset.iterrows(), start=1):
        truth = true_label(row["phase"])
        if truth is None:
            continue

        key = cache_key(
            subject=str(row["subject"]), phase=str(row["phase"]),
            segment=int(row["segment"]), modality=str(row["modality"]),
            kb_version=pipeline.index.kb_version,
            prompt_version=settings.llm.prompt_version,
            model=settings.llm.model, temperature=settings.llm.temperature,
            pinned=cfg.pinned_chunk_id,
        )

        assessment = cache.get(key)
        if assessment is None:
            try:
                assessment = pipeline.assess(row_to_input(row))
            except RuntimeError as exc:
                # Daily quota exhausted. Stop cleanly and keep what was earned —
                # the cache lets tomorrow's run continue from exactly here.
                print(f"\n  STOPPED at {i}/{len(subset)}: {exc}")
                print(f"  {len(assessments)} assessments saved. "
                      f"Rerun tomorrow to continue.")
                break
            cache.put(key, assessment)

        assessments.append(assessment)
        records.append(build_record(row, truth, assessment))
        if i % 5 == 0:
            print(f"  {i}/{len(subset)} ...")

    if not records:
        print("\nNo segment could be assessed — the quota is likely exhausted.")
        print("Rule-based comparators need no API, so they are reported anyway:")
        report_rule_baselines(subset)
        return

    # ---------------------------------------------------------- RAG metrics
    print("\n" + "=" * 68)
    print("RAG SYSTEM")
    print("=" * 68)
    print(evaluate_classification(records).summary())

    print("\n  accuracy per subject:")
    for subject, acc in evaluate_per_subject(records).items():
        print(f"    {subject:<5} {acc:.3f}")

    # Comparators are scored on exactly the same rows, so the comparison is fair.
    evaluated = subset.head(len(records))
    report_rule_baselines(evaluated)

    print("\n" + "=" * 68)
    print("FAITHFULNESS (T5.6)")
    print("=" * 68)
    print(measure_faithfulness(assessments).summary())

    print("\n" + "=" * 68)
    print("CONFIDENCE CALIBRATION (T5.7)")
    print("=" * 68)
    for b in measure_calibration(records):
        print(b.summary())

    out = OUTPUTS_DIR / "evaluation_wesad_ecg_dev.csv"
    pd.DataFrame([a.technical_view() for a in assessments]).to_csv(out, index=False)
    print(f"\nTechnical layer written to: {out}")


if __name__ == "__main__":
    main()
