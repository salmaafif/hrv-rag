# HRV Knowledge Base — for RAG-Based Stress Interpretation

**Version:** `kb_v2.0` · **Date:** 3 August 2026 · **Chunks:** 23 · **Language:** English

> Knowledge base for the RAG system. Each `##` section is one *chunk* that gets
> embedded and retrieved. Every chunk carries a **stable ID** that the LLM uses to
> fill the `references` field of its output, and that serves as the gold standard
> when measuring retrieval quality.
>
> Core principle: **use relative change against the user's own baseline**, never
> absolute thresholds, because HRV is highly individual. The system produces an
> *indication of stress*, **not a clinical diagnosis**.
>
> **The KB version must be recorded on every system output.** Editing this file
> changes the results, so any result without a version tag cannot be reproduced.
> Earlier versions are archived under `knowledge_base/versions/`.
>
> Language note: this KB is written in English so that retrieval stays
> single-language — queries built from HRV features are also English. Version
> `kb_v1.1` was the Indonesian equivalent. User-facing output remains Indonesian.

---

## HRV and the Autonomic Nervous System
**ID:** `KB-ANS-01` · **References:** Shaffer & Ginsberg (2017); Task Force (1996)

Heart Rate Variability (HRV) is the variation in time between consecutive heartbeats,
measured as RR intervals. HRV reflects the activity of the autonomic nervous system,
specifically the balance between the sympathetic branch that accelerates the heart
under pressure and the parasympathetic or vagal branch that calms it at rest.

The sinoatrial node — the heart's natural pacemaker — is innervated by both branches
at once, so any shift in their balance appears directly as a change in HRV. The
parasympathetic branch acts far faster than the sympathetic one: vagal changes appear
within seconds, whereas sympathetic changes take tens of seconds. This property is why
some HRV features remain meaningful even in short recordings.

## Interpreting High vs Low HRV
**ID:** `KB-LEVEL-01` · **References:** Shaffer & Ginsberg (2017); Thayer & Lane (2009)

Higher HRV generally indicates parasympathetic dominance, a relaxed state, and good
adaptive capacity. Lower HRV indicates sympathetic dominance, which commonly appears
when the body is under stress or pressure.

In a job interview context, a drop in HRV relative to the user's own resting state
indicates rising pressure. It must be stressed that "high" and "low" here always mean
relative to the same person's baseline, never relative to population values. Two
healthy people can differ several-fold in resting HRV without either of them having a
problem.

## RMSSD
**ID:** `KB-RMSSD-01` · **References:** Shaffer & Ginsberg (2017); Task Force (1996)

RMSSD (root mean square of successive differences) is computed from the differences
between consecutive RR intervals. Because it measures beat-to-beat change, RMSSD
captures fast-acting vagal influence and is largely unaffected by slow drifts.

RMSSD **decreases** as stress increases. Of all HRV features, RMSSD is the most
reliable for short recordings because it does not need a long window to stabilise.
This system treats RMSSD as the primary feature and everything else as supporting
evidence. When features contradict one another, RMSSD together with heart rate carries
more weight than frequency-domain features.

## SDNN
**ID:** `KB-SDNN-01` · **References:** Shaffer & Ginsberg (2017); Task Force (1996)

SDNN (standard deviation of NN intervals) is the standard deviation of all RR intervals
in a segment and therefore reflects total variability. Unlike RMSSD, which looks only at
differences between neighbouring beats, SDNN looks at the spread of all values.

SDNN is influenced by sympathetic and parasympathetic activity simultaneously, so a
decrease cannot be read directly as reduced vagal activity. SDNN tends to **decrease**
under pressure. In short segments SDNN also absorbs slow trends such as posture shifts
or a deep breath, which makes it more delicate to interpret than RMSSD.

## pNN50 and meanRR
**ID:** `KB-PNN50-01` · **References:** Shaffer & Ginsberg (2017); Task Force (1996)

pNN50 is the percentage of consecutive RR pairs differing by more than 50 milliseconds.
Like RMSSD it relates to vagal activity and **decreases** as pressure rises. Unlike
RMSSD it is a count rather than a magnitude, which makes it coarser: in people with low
HRV it can reach zero and stop discriminating at all. It is therefore reported as a
complement to RMSSD, not a replacement.

meanRR is the average RR interval. A smaller value means a faster heart rate, which
indicates arousal or pressure. Heart rate is the most directionally consistent marker
among all the features, even though it is the crudest.

## Frequency Domain: LF and HF
**ID:** `KB-FREQ-01` · **References:** Task Force (1996); Shaffer & Ginsberg (2017)

Frequency-domain analysis separates HRV variation by how fast it oscillates. The HF
band (high frequency, 0.15–0.40 Hz) reflects parasympathetic activity and is strongly
tied to breathing, because normal respiratory rates fall inside this range. HF
**decreases** as stress rises.

The LF band (low frequency, 0.04–0.15 Hz) is influenced by a mixture of sympathetic
activity, parasympathetic activity, and the baroreflex. Because it is mixed, LF cannot
be read as a measure of sympathetic activity alone. Note also that HF's dependence on
breathing means anything that alters the breathing pattern will alter HF, whether or
not pressure is present.

## Interpreting the LF/HF Ratio with Care
**ID:** `KB-LFHF-02` · **References:** Billman (2013); Task Force (1996)

The LF/HF ratio is often interpreted as sympatho-vagal balance, with higher values
linked to sympathetic dominance or pressure. This interpretation is **seriously
disputed** in the literature, because LF does not purely reflect sympathetic activity
and because a ratio of two quantities makes it hard to tell whether the numerator or
the denominator moved.

In this system LF/HF is treated as a **supporting indicator, not a decisive one**. A
rise in LF/HF strengthens the conclusion when it agrees with falling RMSSD and rising
heart rate. When LF/HF moves alone and contradicts RMSSD, RMSSD is followed and the
confidence score is lowered.

## Population Reference Values
**ID:** `KB-NORM-01` · **References:** Shaffer & Ginsberg (2017); Nunan et al. (2010)

For healthy populations on short recordings of roughly five minutes, approximate
reference values are SDNN around 30–100 ms with a mean near 50 ms, and RMSSD around
20–90 ms with a mean near 42 ms.

These values are **highly individual** and are affected by age, sex, breathing rhythm,
and recording duration. They must therefore **never** be used as thresholds to decide
a person's stress level. Their only role here is a sanity check: if someone's HRV falls
far outside these ranges, the likely explanation is a signal quality problem or
unsuitable measurement conditions. Assessment still relies on comparison against each
user's own baseline.

## HRV Patterns Under Social-Evaluative Stress
**ID:** `KB-STRESS-01` · **References:** Kirschbaum et al. (1993); Castaldo et al. (2015); Kim et al. (2018)

When facing a social-evaluative stressor — a situation where a person feels judged by
others, such as a job interview or a presentation — autonomic balance shifts towards
sympathetic dominance. The standard laboratory protocol for inducing this state is the
Trier Social Stress Test (TSST), which combines speaking in front of evaluators with an
arithmetic task.

The characteristic pattern, always relative to the user's own baseline, is: **RMSSD
decreases, HF decreases, SDNN decreases, LF/HF increases, and heart rate increases**.
The larger and more consistent this pattern across features, the stronger the
indication of pressure. Consistency across features is more convincing than a large
change in any single feature.

## Reactivity
**ID:** `KB-REACT-01` · **References:** Laborde et al. (2017)

Reactivity is the magnitude of change in HRV features relative to the user's baseline
when facing a stressor. It is computed as a percentage change, which makes it
comparable across people with very different absolute HRV levels.

High reactivity — for example RMSSD dropping sharply while heart rate climbs sharply —
indicates a strong stress response. It is worth noting that high reactivity is not
automatically bad: responding briskly to a challenge is normal, and what matters more
is whether the body can settle afterwards. Reactivity is therefore always read together
with recovery.

## Recovery
**ID:** `KB-RECOV-01` · **References:** Laborde et al. (2017)

Recovery is how quickly HRV returns towards baseline once a stressful segment has
passed. Fast recovery indicates good stress management; slow recovery indicates
pressure that persists even after the trigger is gone.

Recovery can only be measured when a quiet period follows the stressor. In an interview
practice session, that period is the gap between questions. If no sufficiently long gap
exists, recovery cannot be assessed at all — and that must be stated plainly rather
than filled in with zero. Zero means "did not recover at all", which is a very
different claim from "could not be measured".

## Quantifying Recovery
**ID:** `KB-RECOV-02` · **References:** Laborde et al. (2017); Task Force (1996)

Recovery is expressed as the percentage of the deviation that has returned towards
baseline. Where B is the baseline value, S is the value while stressed, and R is the
value during the gap, recovery equals (S − R) divided by (S − B), multiplied by one
hundred percent.

Reading it: one hundred percent means a full return to baseline; above one hundred
percent means overshooting past baseline; zero percent means no movement at all; and a
negative value means the state moved further away from baseline. This calculation is
only valid when the reaction was large enough. If the deviation while stressed is less
than one tenth of the baseline value, the division becomes unstable and recovery must
be declared not computable.

## Resilience Index
**ID:** `KB-RESIL-01` · **References:** Laborde et al. (2017)

Resilience to pressure is judged from the combination of **reactivity** and
**recovery**, never from either alone. There are four possible combinations: small
reactivity with fast recovery indicates high resilience; large reactivity with slow
recovery indicates low resilience; large reactivity with fast recovery indicates
someone responsive but flexible; and small reactivity with slow recovery indicates
held-in tension.

Resilience is reported as one of these four categories, **not as a numeric score**. A
numeric score would demand a between-person reference, whereas this entire system is
designed to compare a person against themselves.

## HRV Confounding Factors
**ID:** `KB-CONF-01` · **References:** Laborde et al. (2017); Quintana & Heathers (2014)

HRV interpretation must account for the following confounders: age, since HRV declines
with age; sex; breathing rhythm and depth; body posture, since lying and standing
produce different HRV; physical activity before measurement; and caffeine or nicotine
intake.

These factors can both **mimic and mask** changes caused by pressure. Caffeine, for
example, can lower HRV with no pressure present at all, producing a misleading picture.
Because all of them stay largely constant within a single short session, comparing
against the user's own baseline from that same session is far more dependable than
comparing between people.

## How Speaking Affects HRV
**ID:** `KB-CONF-02` · **References:** Bernardi et al. (2000); Grossman & Taylor (2007)

Speaking fundamentally alters the breathing pattern: breaths become deeper, slower, and
irregular as they follow sentence length. Because the HF band is driven by respiration,
this change can **increase** HF power and RMSSD — the opposite direction from what is
expected under pressure.

As a result, in tasks requiring extended speech such as interviews or presentations,
some people show HRV that rises even while they are under pressure. In such cases
**heart rate becomes the more trustworthy marker**, because its rise cannot be
explained by breathing pattern alone. If RMSSD and HF rise while heart rate also rises,
the most likely explanation is the effect of speaking, not the absence of pressure.

## Cognitive Load and Mental Effort
**ID:** `KB-COGN-01` · **References:** Hjortskov et al. (2004); Thayer et al. (2009)

Cognitive load is the amount of mental effort a task demands — for instance composing a
technical answer, recalling details, or doing arithmetic. Increased cognitive load also
**lowers HRV and raises heart rate**, through a pathway involving prefrontal cortical
control over the heart.

The critical problem: **the physiological signature of cognitive load is practically
indistinguishable from that of social-evaluative stress** when only HRV is available.
Both lower RMSSD and raise heart rate. The distinction must come from context, namely
the type of task being performed — technical or arithmetic questions lean towards
cognitive load, while questions that put the person under scrutiny lean towards social
pressure. This attribution is contextual and must be stated as a hypothesis, not a
certainty.

## Arousal and Valence
**ID:** `KB-AROUS-01` · **References:** Shaffer & Ginsberg (2017); Quintana & Heathers (2014)

Arousal is the general level of bodily activation or alertness. HRV and heart rate
measure arousal fairly directly. However, arousal is **valence-neutral**: it says how
activated someone is, not whether the experience is pleasant or unpleasant.

The consequence is significant. Joy, enthusiasm, and anger all raise arousal and lower
HRV, exactly as fear or anxiety do. A drop in HRV alone is therefore **not sufficient**
to conclude that negative pressure is present. Concluding pressure requires support
from situational context — in this system, the context is an interview simulation that
is evaluative by design.

## Ultra-Short-Term HRV in 60-Second Segments
**ID:** `KB-ULTRA-01` · **References:** Shaffer & Ginsberg (2017); Task Force (1996)

In very short recordings such as 60-second segments, time-domain features — especially
RMSSD and heart rate — remain relatively dependable because both capture fast changes
that are well represented within a minute.

Frequency-domain features are less stable, particularly the LF band. A single LF cycle
at the slow end lasts about twenty-five seconds, so a sixty-second window fits only
about two cycles — too few for a stable power estimate. On short segments, priority
therefore goes to RMSSD and its reactivity, while LF and LF/HF are interpreted with far
more caution and never used as the sole basis for a conclusion.

## Modality Differences: ECG and PPG
**ID:** `KB-MODAL-01` · **References:** Schäfer & Vagedes (2013)

ECG records the electrical activity of the heart and produces sharp R peaks, so the
timing of each beat can be determined very precisely. ECG is the **reference or gold
standard** for HRV measurement.

PPG records blood volume changes optically, usually at the wrist or fingertip, and
produces systolic peaks with a gentle shape. Because these peaks are less sharp than R
peaks, beat timing from PPG is less certain. The interval series derived from PPG is
called IBI, and its variability is called PRV — not HRV. This difference in terminology
is not a formality; it signals that the two are not identical.

## When PRV Diverges from HRV
**ID:** `KB-MODAL-02` · **References:** Schäfer & Vagedes (2013)

At rest and while still, PRV from PPG approximates HRV from ECG well enough that
results from the two can be treated as equivalent. That agreement **degrades** under
two conditions: during movement, because optical sensors are highly vulnerable to
motion artefacts; and under pressure, because changes in blood pressure and vascular
tone alter the pulse transit time from heart to wrist.

Pressure is precisely the condition this system measures. Assessments derived from PPG
must therefore be given a **lower confidence score** than assessments derived from ECG,
especially when the detected indication of pressure is strong.

## Guidance for Rating Stress Level
**ID:** `KB-INTERP-01` · **References:** Castaldo et al. (2015); Kim et al. (2018)

Assessment is always based on the pattern of relative change against the user's
baseline, never on a single value or an absolute threshold.

**Low stress:** HRV features at or above baseline; RMSSD and HF stable; heart rate not
meaningfully elevated; LF/HF not notably raised.
**Moderate stress:** moderate change in several features; RMSSD and HF slightly
decreased; heart rate slightly elevated; the pattern not yet consistent across features.
**High stress:** clear decrease in RMSSD and HF, together with elevated heart rate and
raised LF/HF, with the pattern consistent across most features.

The final judgement weighs reactivity and recovery together, along with consistency
across features — not the size of change in one feature alone.

## Handling Atypical Patterns
**ID:** `KB-INTERP-02` · **References:** Bernardi et al. (2000); Laborde et al. (2017)

Not everyone shows the textbook pattern. The most commonly encountered exception is
**RMSSD and HF rising while heart rate also rises**. This does not mean pressure is
absent. The most likely explanations are the effect of speaking on breathing, or a
baseline that was not recorded in a genuinely resting state — for instance when heart
rate was already high during calibration.

Guidance for such cases: first, check heart rate, since its rise is harder to explain
away through confounders. Second, check whether the baseline itself is plausible.
Third, **lower the confidence score and state the uncertainty explicitly** rather than
forcing a single label. Declaring uncertainty is the correct answer when the evidence
genuinely conflicts.

## Limitations and Interpretation Ethics
**ID:** `KB-ETHIC-01` · **References:** Quintana & Heathers (2014); Laborde et al. (2017)

This system provides a **physiology-based indication of stress or pressure response**,
not a clinical diagnosis of anxiety. Anxiety is a psychological construct whose
assessment requires professional evaluation; what is measured here is a physiological
stress response that correlates with situational anxiety, not anxiety itself.

Interpretation is meant to support interview practice, not medical assessment and not
personality judgement. Feedback should be phrased as trainable behaviour — for example
"it took longer to settle after difficult questions" — rather than as a label about who
someone is. Results are affected by signal quality and confounders, so a confidence
score must always accompany them.

---

## Sources

> **ATTENTION — must be verified before use in the thesis.** This list is a draft.
> Salma must open each reference, confirm that its content genuinely supports the claim
> in the chunk citing it, and reformat the citation according to PENS guidelines.
> References marked ⚠ are **unverified** and need checking most urgently, because they
> support the chunks added most recently.

**Present since `kb_v1.0`:**

1. Shaffer, F., & Ginsberg, J. P. (2017). *An Overview of Heart Rate Variability
   Metrics and Norms.* Frontiers in Public Health, 5, 258.
2. Nunan, D., Sandercock, G. R. H., & Brodie, D. A. (2010). *A quantitative systematic
   review of normal values for short-term heart rate variability in healthy adults.*
   Pacing and Clinical Electrophysiology, 33(11), 1407–1417.
3. Task Force of the European Society of Cardiology and the North American Society of
   Pacing and Electrophysiology (1996). *Heart rate variability: standards of
   measurement, physiological interpretation, and clinical use.* Circulation, 93(5),
   1043–1065.

**Added in `kb_v1.1`:**

4. ⚠ Schäfer, A., & Vagedes, J. (2013). *How accurate is pulse rate variability as an
   estimate of heart rate variability?* International Journal of Cardiology, 166(1),
   15–29. — supports `KB-MODAL-01`, `KB-MODAL-02`.
5. ⚠ Bernardi, L., et al. (2000). *Effects of controlled breathing, mental activity and
   mental stress with or without verbalization on heart rate variability.* Journal of
   the American College of Cardiology, 35(6), 1462–1469. — supports `KB-CONF-02`,
   `KB-INTERP-02`.
6. ⚠ Laborde, S., Mosley, E., & Thayer, J. F. (2017). *Heart rate variability and
   cardiac vagal tone in psychophysiological research — recommendations for experiment
   planning, data analysis, and data reporting.* Frontiers in Psychology, 8, 213.
7. ⚠ Billman, G. E. (2013). *The LF/HF ratio does not accurately measure cardiac
   sympatho-vagal balance.* Frontiers in Physiology, 4, 26. — supports `KB-LFHF-02`.
8. ⚠ Kirschbaum, C., Pirke, K. M., & Hellhammer, D. H. (1993). *The Trier Social Stress
   Test — a tool for investigating psychobiological stress responses in a laboratory
   setting.* Neuropsychobiology, 28(1–2), 76–81.
9. ⚠ Thayer, J. F., & Lane, R. D. (2009). *Claude Bernard and the heart–brain
   connection.* Neuroscience & Biobehavioral Reviews, 33(2), 81–88.
10. ⚠ Quintana, D. S., & Heathers, J. A. J. (2014). *Considerations in the assessment of
    heart rate variability in biobehavioral research.* Frontiers in Psychology, 5, 805.
11. ⚠ Grossman, P., & Taylor, E. W. (2007). *Toward understanding respiratory sinus
    arrhythmia.* Biological Psychology, 74(2), 263–285.
12. ⚠ Hjortskov, N., et al. (2004). *The effect of mental stress on heart rate
    variability and blood pressure during computer work.* European Journal of Applied
    Physiology, 92(1–2), 84–89. — supports `KB-COGN-01`.
13. ⚠ Castaldo, R., et al. (2015). *Acute mental stress assessment via short term HRV
    analysis in healthy adults: a systematic review.* Biomedical Signal Processing and
    Control, 18, 370–377.
14. ⚠ Kim, H. G., et al. (2018). *Stress and Heart Rate Variability: A Meta-Analysis and
    Review of the Literature.* Psychiatry Investigation, 15(3), 235–245.

**Note.** References from Salma's own literature review should be added here,
especially any covering HRV in job interview or academic evaluation contexts, since
those are closest to this system.
