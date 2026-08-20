/**
 * api.ts — the shape of what the backend returns.
 *
 * This file is the frontend's half of the contract described in
 * `docs/frontend_plan.md` section 3. Field names are kept in the backend's
 * snake_case rather than being renamed to camelCase, so that a response can be
 * compared against this file line by line without a mental translation step.
 * The contract is the deliverable handed to the KARIRLINK web team; making it
 * easy to check matters more than matching JavaScript house style.
 *
 * The types that carry the most weight here are the nullable ones. `null` is
 * never a synonym for zero anywhere in this API — see `recovery_pct`.
 */

/** Which sensor produced the data. Affects how much confidence a reading earns. */
export type Modality = 'ECG' | 'PPG'

/**
 * The stress label.
 *
 * Note the absence of 'uncertain'. The backend's `StressLevel` enum does have
 * that fourth value, but it belongs to the per-segment LLM path. Both endpoints
 * used by this frontend take their label from the rule in
 * `features/stress_level.py`, which only ever returns these three.
 */
export type StressLevel = 'low' | 'moderate' | 'high'

/** Interview question categories the backend recognises. */
export type QuestionType =
  | 'introduction'
  | 'behavioural'
  | 'technical'
  | 'numerical'
  | 'situational'

/**
 * Where a whole session lands on the two axes of reaction size and recovery
 * speed. Null when recovery could not be measured at all: without one axis the
 * quadrant is undefined, and guessing it would overstate what the data shows.
 */
export type ResilienceQuadrant =
  | 'high resilience'
  | 'held-in tension'
  | 'responsive but flexible'
  | 'low resilience'

/** The person's own resting reference, against which everything else is judged. */
export interface Baseline {
  rmssd_ms: number
  mean_hr_bpm: number
  /** How many 60-second windows the baseline was averaged over. */
  n_segments: number
  /**
   * False when the resting period itself was too variable to trust. Every
   * result in the response is a comparison against this baseline, so when it is
   * unstable the whole reading weakens — the UI must say so rather than
   * presenting the numbers at face value.
   */
  is_stable: boolean
  /**
   * How much resting recording the baseline stands on — a SEPARATE question from
   * `is_stable`, and one the UI must not merge into it. `is_stable` says nothing
   * looked wrong; `evidence` says how much was looked at.
   *
   * Few windows means the checks passed for want of evidence rather than on the
   * strength of it. Measured on WESAD: under six windows, 11.8% of sessions carry
   * a bad baseline with nothing flagged, against 3.9% at ten or more. The number
   * of windows is decided by how long the sensor was connected before the person
   * pressed start, which is why `warning` explains it in words they can act on.
   */
  evidence: 'full' | 'limited' | 'minimal'
  warning: string | null
}

/** Provenance, so a result can be traced back to the knowledge base and model. */
export interface ResponseMeta {
  kb_version: string
  model: string
  /**
   * False when a guard caught the model inventing a number or citing a chunk
   * that was never retrieved. The narrative should not be shown as-is when this
   * is false.
   */
  trustworthy: boolean
}

// ---------------------------------------------------------------------------
// V1 — POST /api/v1/analyze/timeline
// ---------------------------------------------------------------------------

export interface TimelinePoint {
  /**
   * Which minute of the recording this window ends in.
   *
   * CAN BE FRACTIONAL. Windows are 60 seconds long but advance every 30
   * seconds, so successive values run 5, 5.5, 6, 6.5 rather than 5, 6, 7.
   * `start_sec` and `end_sec` are the authoritative fields; treat `minute` as a
   * label for display only.
   */
  minute: number
  start_sec: number
  end_sec: number
  level: StressLevel
  /** 0–4, from the two-feature rule. Developer view only. */
  score: number
  /** Percent change against the person's own baseline. Developer view only. */
  delta_rmssd_pct: number
  delta_hr_pct: number
  /** English, one line per feature that scored. Developer view only. */
  evidence: string[]
  /**
   * True when RMSSD rose while heart rate also rose. The two markers point
   * opposite ways, so the reading is less certain and the UI must flag it.
   */
  features_disagree: boolean
}

export interface TimelineSummary {
  /** Null when no window could be measured. */
  peak_minute: number | null
  median_reactivity_pct: number | null
  count_low: number
  count_moderate: number
  count_high: number
}

/** Indonesian prose from the LLM. The only part of the response it writes. */
export interface TimelineNarrative {
  ringkasan: string
  rekomendasi: string
  penyemangat: string
}

export interface TimelineResponse {
  session_id: string
  modality: Modality
  duration_sec: number
  baseline: Baseline
  timeline: TimelinePoint[]
  summary: TimelineSummary
  narrative: TimelineNarrative
  meta: ResponseMeta
}

// ---------------------------------------------------------------------------
// V2 and V3 — POST /api/v1/analyze/session
// ---------------------------------------------------------------------------

export interface QuestionResult {
  number: number
  text: string
  type: QuestionType
  level: StressLevel
  score: number
  delta_rmssd_pct: number
  delta_hr_pct: number
  /**
   * How much of the reaction faded during the gap before the next question,
   * as a percentage.
   *
   * NULL MEANS NOT MEASURABLE — there was no gap long enough to measure it.
   * It does NOT mean zero. Zero would be the claim "the body did not settle at
   * all", which is a far stronger and different statement. Never render this as
   * "0%"; use `formatRecovery` in `lib/format.ts`, which handles the case.
   */
  recovery_pct: number | null
  /** Why recovery could not be measured. Empty string when it could. */
  recovery_note: string
  evidence: string[]
  features_disagree: boolean
  /** Indonesian, from the LLM. What happened, described as behaviour. */
  penjelasan: string
  /** Indonesian, from the LLM. One concrete thing to practise. */
  saran: string
}

export interface SessionSummary {
  /** Question number with the largest reaction. Null when none was measurable. */
  most_triggering_question: number | null
  resilience: ResilienceQuadrant | null
  median_reactivity_pct: number | null
  /** Null when no question had a measurable recovery gap. */
  median_recovery_pct: number | null
}

export interface SessionNarrative {
  ringkasan_sesi: string
  penyemangat: string
}

export interface SessionResponse {
  session_id: string
  /**
   * Not shown in the example in `docs/frontend_plan.md`, but included here on
   * purpose: mandatory rule #5 says the modality travels with the result, and
   * the UI has to be able to say whether a reading came from a chest strap or a
   * watch. Flagged as a proposed addition to the contract.
   */
  modality: Modality
  baseline: Baseline
  questions: QuestionResult[]
  summary: SessionSummary
  narrative: SessionNarrative
  meta: ResponseMeta
}

// ---------------------------------------------------------------------------
// Request payloads
// ---------------------------------------------------------------------------

/** One entry of the question timeline the caller supplies for V2 and V3. */
export interface QuestionTimelineEntry {
  number: number
  text: string
  type: QuestionType
  answer_start_sec: number
  answer_end_sec: number
  /** End of the quiet gap after the answer, from which recovery is measured. */
  gap_end_sec: number
  is_difficult: boolean
}

export interface AnalyzeRequest {
  /** Beat-to-beat intervals in milliseconds, when coming from Bluetooth. */
  rr_ms?: number[]
  /**
   * Raw CSV text, when the source is an uploaded file.
   *
   * Exactly one of `rr_ms` and `csv` is sent. The recording never travels as a
   * `.pkl`: the WESAD files run to hundreds of megabytes, which is not
   * something anyone will upload to a hosted demo.
   */
  csv?: string
  /** How many minutes at the start of the recording form the baseline. */
  baseline_minutes: number
  modality: Modality
  /**
   * Seconds of recording that already existed when the session clock reached
   * zero.
   *
   * A Bluetooth sensor streams from the moment it pairs, while every timestamp
   * below is measured from the moment the person pressed start. Those two
   * instants are not the same, and the gap between them is however long fitting
   * the band and reading the screen took. Left unstated, it shifts the resting
   * period and every question window by that amount — silently, because the
   * response stays complete and merely describes different minutes.
   *
   * Zero for an uploaded file, where the recording and the session begin
   * together.
   */
  offset_sec?: number
}

export interface SessionRequest extends AnalyzeRequest {
  questions: QuestionTimelineEntry[]
}
