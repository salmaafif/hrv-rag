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
    Heart rate alone — the comparator that decides whether an armband is enough.

    NOT AN ACADEMIC EXERCISE. The first test device is a Coospo HW9, an optical
    armband, and optical sensors give a trustworthy heart rate but an untrustworthy
    RMSSD: paired against ECG on WESAD, meanHR reached ICC +0.986 while RMSSD
    managed +0.109, and beat detection fell to 78-84% during the stressor itself.
    So this is not "the rule minus a feature" — it is the rule as it will actually
    run on the hardware that was bought.

    THE RESULT WAS NOT THE EXPECTED ONE. Measured on the ten sealed subjects,
    dropping RMSSD did not cost anything; it HELPED. Macro-F1 went from 0.839 to
    0.871 and kappa from 0.678 to 0.742, and per subject the change was positive
    five times, zero five times, and negative never. The paired difference is
    +0.031 with a 95% interval of [+0.008, +0.056], which does not touch zero.

    The reason is already documented as limitation L9: RMSSD moved the WRONG way
    under stress in two of five development subjects, while heart rate rose in all
    five. A feature that points backwards for a substantial minority of people is
    not adding evidence, it is adding noise — and on this dataset removing it is a
    net gain rather than a compromise.

    WHAT THIS DOES NOT SAY. It does not say RMSSD is useless in general; it says
    RMSSD measured over 60-second windows, on this stressor, in this population of
    fifteen, did not help this rule. And it is measured on ECG recordings with
    RMSSD withheld, which is a simulation of an armband rather than an armband.
    """
    cfg = cfg or RuleConfig()
    hr = reactivity.get("delta_pct_mean_hr")
    if hr is None or hr != hr:
        return TrueLabel.LOW          # nothing measured, nothing to claim
    return TrueLabel.HIGH if hr >= cfg.hr_rise_pct else TrueLabel.LOW
