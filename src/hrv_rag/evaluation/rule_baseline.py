"""
rule_baseline.py — Threshold comparator without any LLM (BACKLOG U3.1).

This is the question an examiner is guaranteed to ask: how do you know the RAG
system helped? Without a comparator there is no answer, only an assertion.

The rule is deliberately the simplest defensible one: RMSSD falls sharply below the
person's own baseline, so the segment is stressed. It uses the same computed
features and the same personal baseline as the RAG path, so the only difference
between them is interpretation — which is exactly the variable under test.

Two outcomes, both useful:
  - RAG beats the rule -> the knowledge base and the LLM add measurable value.
  - RAG does not beat it -> an honest and important finding, and the thesis should
    say so plainly rather than bury it.

A second variant is included that also considers heart rate. It exists because the
data demanded it: two of five development subjects show RMSSD RISING under stress,
while heart rate rose in all five. A rule that only watches RMSSD is guaranteed to
misclassify those subjects, and comparing the two variants quantifies exactly how
much that costs.

A third variant watches heart rate alone (docs/PETA_PEKERJAAN.md ablation #9,
docs/ARSITEKTUR_KARIRLINK_HRV.md A4). It answers a narrower but higher-stakes
question than the first two: `development_journey.md` §4.13 found PPG agrees
with ECG on heart rate but not on RMSSD-derived variability, so the tier-T1
product row (armband/watch, HR-only) can only be claimed honestly if a rule
built on heart rate alone still separates stress from calm. If its macro-F1
collapses toward chance, T1 has no basis and the product table has to say so.
"""

from __future__ import annotations

from dataclasses import dataclass

from .labels import TrueLabel


@dataclass(frozen=True)
class RuleConfig:
    """
    Thresholds for the rule-based comparator.

    These must be calibrated on the development subjects only and then frozen,
    exactly like the prompt (BACKLOG U4.1). Tuning them against the test subjects
    would give the comparator an advantage the RAG system never had, making the
    comparison meaningless.
    """

    # RMSSD this far below baseline (percent) counts as stressed.
    rmssd_drop_pct: float = -20.0

    # Heart rate this far above baseline counts as stressed, used by the
    # two-feature variant.
    hr_rise_pct: float = 10.0


def rule_rmssd_only(reactivity: dict[str, float],
                    cfg: RuleConfig | None = None) -> TrueLabel:
    """
    Single-feature rule: stressed when RMSSD drops far enough below baseline.

    Never abstains. That is a genuine difference from the RAG system, which may
    answer `uncertain`, and it must be remembered when comparing the two: the rule
    achieves 100% coverage by construction, not by being more capable.
    """
    cfg = cfg or RuleConfig()
    delta = reactivity.get("delta_pct_rmssd")
    if delta is None or delta != delta:
        return TrueLabel.LOW          # no evidence of stress available
    return TrueLabel.HIGH if delta <= cfg.rmssd_drop_pct else TrueLabel.LOW


def rule_rmssd_and_hr(reactivity: dict[str, float],
                      cfg: RuleConfig | None = None) -> TrueLabel:
    """
    Two-feature rule: stressed when RMSSD drops OR heart rate rises enough.

    The disjunction matters. Requiring both would fail on precisely the subjects
    whose RMSSD moves the wrong way, whereas heart rate rose in every development
    subject (+5.1% to +74%). This variant tests whether that single extra feature
    recovers the cases the simpler rule loses.
    """
    cfg = cfg or RuleConfig()
    rmssd = reactivity.get("delta_pct_rmssd")
    hr = reactivity.get("delta_pct_mean_hr")

    rmssd_says_stress = (rmssd is not None and rmssd == rmssd
                         and rmssd <= cfg.rmssd_drop_pct)
    hr_says_stress = (hr is not None and hr == hr and hr >= cfg.hr_rise_pct)

    return TrueLabel.HIGH if (rmssd_says_stress or hr_says_stress) else TrueLabel.LOW


def rule_hr_only(reactivity: dict[str, float],
                 cfg: RuleConfig | None = None) -> TrueLabel:
    """
    Single-feature rule: stressed when heart rate rises far enough above baseline.

    Deliberately the same shape as `rule_rmssd_only`, with the one feature a PPG
    armband can report with confidence swapped in for the one it cannot (Mandatory
    Rule #5 modality note; `development_journey.md` §4.13). Its macro-F1 against
    `rule_rmssd_only`'s, on the same subjects, is the whole ablation #9 result —
    whichever one a tier-T1 product can actually claim.
    """
    cfg = cfg or RuleConfig()
    hr = reactivity.get("delta_pct_mean_hr")
    if hr is None or hr != hr:
        return TrueLabel.LOW          # no evidence of stress available
    return TrueLabel.HIGH if hr >= cfg.hr_rise_pct else TrueLabel.LOW
