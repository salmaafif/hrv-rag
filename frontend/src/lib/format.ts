/**
 * format.ts — every number-to-text and code-to-label conversion in the app.
 *
 * Centralised on purpose. The most damaging mistake this interface can make is
 * quiet and easy: rendering a measurement that does not exist as though it were
 * a measurement of zero. If each component formatted its own values, that
 * mistake would have to be avoided in every one of them, and it only takes
 * being wrong once. Here it is decided in a single place and locked by
 * `format.test.ts`.
 */

import type {
  Modality,
  QuestionType,
  ResilienceQuadrant,
  StressLevel,
} from '../types/api'

/**
 * What is shown wherever a value could not be measured.
 *
 * Not "0%", not "—", not an empty cell. A dash reads as a formatting gap and
 * invites the reader to fill it in themselves; this says plainly that the
 * measurement was not obtained.
 */
export const NOT_MEASURED = 'tidak diukur'

/**
 * Whether a nullable measurement is actually present.
 *
 * Exported so components can branch on it — hiding a progress bar, say —
 * without repeating the null check and getting the polarity wrong.
 */
export function hasMeasurement(value: number | null): value is number {
  return value !== null && Number.isFinite(value)
}

/**
 * Recovery as a percentage, or the words for "not measurable".
 *
 * `null` means there was no gap long enough after the question to see whether
 * the person settled. That is an absence of evidence. Zero would be evidence of
 * an absence — the claim that the body did not settle at all — which is a much
 * stronger statement about someone, and a different one. Rendering the first as
 * the second would be the single most misleading thing this UI could do, so the
 * two can never collapse into the same string.
 *
 * Non-finite numbers are treated as absent too. JSON cannot carry NaN, so this
 * should not arise from the API, but a value arriving from a computation
 * upstream still must not print as "NaN%".
 */
export function formatRecovery(pct: number | null): string {
  if (!hasMeasurement(pct)) return NOT_MEASURED
  return `${Math.round(pct)}%`
}

/** Indonesian labels for the three levels. Shown next to every colour. */
const LEVEL_LABEL: Record<StressLevel, string> = {
  low: 'Rendah',
  moderate: 'Sedang',
  high: 'Tinggi',
}

export function formatLevel(level: StressLevel): string {
  return LEVEL_LABEL[level]
}

/**
 * A behavioural sentence in place of the raw level word (decision A12,
 * docs/ARSITEKTUR_KARIRLINK_HRV.md §4).
 *
 * Not about the numbers — those are already hidden. It is the WORD "Tinggi"
 * itself that is risky: heart-rate biofeedback improves the match between felt
 * stress and physiology, but people with high anxiety sensitivity report MORE
 * stress specifically when the feedback is labelled with a stress word. Naming
 * the behaviour instead of scoring the person keeps the same information
 * without handing back a label to react to.
 */
const LEVEL_BEHAVIOR: Record<StressLevel, string> = {
  low: 'Tubuhmu tetap tenang di pertanyaan ini.',
  moderate: 'Tubuhmu bereaksi sedang di pertanyaan ini.',
  high: 'Tubuhmu bereaksi kuat di pertanyaan ini.',
}

export function formatLevelBehavior(level: StressLevel): string {
  return LEVEL_BEHAVIOR[level]
}

/**
 * Indonesian labels for the resilience quadrants.
 *
 * `null` is a real answer here, not a missing one: `resilience_quadrant()`
 * returns nothing when recovery could not be measured, because one of the two
 * axes is unavailable. "Belum dapat disimpulkan" says that, where naming a
 * quadrant anyway would invent a conclusion.
 */
const RESILIENCE_LABEL: Record<ResilienceQuadrant, string> = {
  'high resilience': 'Reaksi kecil, pulih cepat',
  'held-in tension': 'Reaksi kecil, pulih lambat',
  'responsive but flexible': 'Reaksi besar, pulih cepat',
  'low resilience': 'Reaksi besar, pulih lambat',
}

export function formatResilience(quadrant: ResilienceQuadrant | null): string {
  if (quadrant === null) return 'Belum dapat disimpulkan'
  return RESILIENCE_LABEL[quadrant]
}

/**
 * Where the data came from.
 *
 * Kept visible because mandatory rule #5 says modality travels with the result:
 * a wrist sensor and a chest strap do not earn the same confidence, and the
 * person reading the screen is entitled to know which one produced it.
 */
const MODALITY_LABEL: Record<Modality, string> = {
  ECG: 'Chest strap (ECG)',
  PPG: 'Smartwatch (PPG)',
}

export function formatModality(modality: Modality): string {
  return MODALITY_LABEL[modality]
}

const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  introduction: 'Perkenalan',
  behavioural: 'Pengalaman',
  technical: 'Teknis',
  numerical: 'Hitungan',
  situational: 'Situasional',
}

export function formatQuestionType(type: QuestionType): string {
  return QUESTION_TYPE_LABEL[type]
}

/** Elapsed time as mm:ss, for the timer during a running session. */
export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const mm = String(Math.floor(safe / 60)).padStart(2, '0')
  const ss = String(safe % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

/** Recording length in whole minutes, for the summary header. */
export function formatDuration(seconds: number): string {
  return `${Math.round(seconds / 60)} menit`
}

/**
 * A signed percentage, for the developer panel only.
 *
 * The sign is always written, including the plus, because these values are read
 * as directions rather than magnitudes — whether RMSSD went up or down is the
 * whole point, and a missing plus makes a rise look like a bare quantity.
 */
export function formatSignedPercent(value: number | null): string {
  if (!hasMeasurement(value)) return NOT_MEASURED
  const rounded = Math.round(value * 10) / 10
  return `${rounded > 0 ? '+' : ''}${rounded.toFixed(1)}%`
}
