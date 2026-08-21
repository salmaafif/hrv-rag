/**
 * sessionInsights.ts — the numbers the dashboard draws, derived from one session.
 *
 * EVERY FIGURE HERE COMES FROM THE PERSON'S OWN SESSION AND NOTHING ELSE. No
 * population norm, no reference group, no score borrowed from a scale somebody
 * else calibrated. That is not a stylistic preference: Mandatory Rule #2 makes
 * every measurement in this system relative to the individual, and the thesis
 * rejected a 0-100 "resilience score" for exactly this reason — a number like
 * "resilience 72" only means something against other people, and comparing
 * people is the thing this design set out to avoid.
 *
 * WHAT THEY ARE NOT. They are not traits. The naming throughout follows the rule
 * already set in `docs/development_journey.md`: feedback is phrased as trainable
 * behaviour, never as a label about the person — "needed longer to settle after
 * hard questions", not "low emotional regulation".
 *
 * K4 applies here too: nothing in this file produces a feature name, a raw
 * value, or a score out of four. Those exist in the response and stay behind
 * the developer panel.
 *
 * THE RADAR IS GONE, and with it `responseDimensions`. Two independent lines of
 * reasoning arrived at the same place. Geometrically, only two honest magnitudes
 * exist in this data — reaction size and recovery speed — and a two-axis radar
 * is a line. The third axis that made it drawable measured a DIRECTION on a
 * chart whose other two measured magnitudes, so its midpoint meant "no change"
 * while everywhere else the midpoint meant "half"; a steady session drew the
 * same dent as a bad one. And psychologically, a radar is read as a personality
 * profile whatever its axes are called, which is the cue Feedback Intervention
 * Theory identifies behind the third of feedback effects that make performance
 * WORSE (Kluger & DeNisi 1996).
 *
 * What replaced it is the quadrant — reaction size against recovery speed —
 * which is what the design document called Ketahanan all along. The direction
 * the third axis carried survives as `sessionTrend`, one sentence under the
 * timeline that already shows it as a shape.
 */

import type { QuestionResult, ResilienceQuadrant, SessionResponse,
               StressLevel } from '../types/api'

/**
 * Pressure carried by one label, on a 0-100 scale.
 *
 * The three labels are ordered but not evenly spaced by anything measurable, so
 * the midpoint is a presentational choice rather than a finding. It is stated
 * here once rather than being implied in four different places.
 */
const PRESSURE: Record<StressLevel, number> = {
  low: 0,
  moderate: 50,
  high: 100,
}

const clamp = (value: number) => Math.max(0, Math.min(100, value))

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[middle - 1]! + sorted[middle]!) / 2
    : sorted[middle]!
}

// ---------------------------------------------------------------- ketahanan

/** Which cell of the 2×2 a session landed in. */
export interface ResilienceCell {
  /** Column: was the reaction big or small? */
  reaction: 'kecil' | 'besar'
  /** Row: did the body settle quickly or slowly? */
  recovery: 'cepat' | 'lambat'
}

const CELL: Record<ResilienceQuadrant, ResilienceCell> = {
  'high resilience': { reaction: 'kecil', recovery: 'cepat' },
  'held-in tension': { reaction: 'kecil', recovery: 'lambat' },
  'responsive but flexible': { reaction: 'besar', recovery: 'cepat' },
  'low resilience': { reaction: 'besar', recovery: 'lambat' },
}

/**
 * Where this session sits on the two axes of Ketahanan.
 *
 * READ FROM THE LABEL, NOT RECOMPUTED. The backend's rule decides the quadrant
 * from its own thresholds; deriving a position here from `recovery_pct` and the
 * level counts would let the picture and the words disagree, which is the exact
 * failure `pressureTimeline` was written to avoid. Same principle, same reason.
 *
 * `null` is a real answer: `resilience_quadrant()` returns nothing when recovery
 * could not be measured at all, because one of the two axes is missing. Guessing
 * a cell anyway would invent a conclusion out of an absent measurement.
 */
export function resilienceCell(
  quadrant: ResilienceQuadrant | null,
): ResilienceCell | null {
  return quadrant === null ? null : CELL[quadrant]
}

// ---------------------------------------------------------------- arah sesi

/**
 * Whether the later half of the interview ran calmer than the earlier half.
 *
 * A SENTENCE, NOT A NUMBER — and that is the whole point of the change. As a
 * chart axis this had to be squeezed onto a 0-100 scale where 50 meant "no
 * change", which reads as a mediocre score to everyone who has ever seen a
 * chart. In words the same finding is unambiguous and needs no caveat.
 *
 * An odd number of questions puts the middle one in neither half. Splitting it
 * across both would let one question pull both ends at once.
 *
 * Returns `null` under two questions, where there are no halves to compare.
 */
export function sessionTrend(result: SessionResponse): string | null {
  const questions = result.questions
  const half = Math.floor(questions.length / 2)
  if (half === 0) return null

  const mean = (part: QuestionResult[]) =>
    part.reduce((total, q) => total + PRESSURE[q.level], 0) / part.length
  const shift = mean(questions.slice(0, half)) - mean(questions.slice(-half))

  if (shift > 5) return 'Kamu makin santai menjelang akhir.'
  if (shift < -5) return 'Tekanannya menumpuk di akhir.'
  return 'Segitu-gitu saja dari awal sampai akhir.'
}

// ------------------------------------------------------------------ ringkas

export interface Headline {
  label: string
  value: string
  hint: string
}

/**
 * The three figures at the top of the dashboard.
 *
 * Chosen for what a person can act on tomorrow, not for what is easiest to
 * compute. Which question was hardest tells them what to rehearse; how many ran
 * calm tells them it was not all bad; how quickly they settled tells them
 * whether the pauses are working.
 */
export function headlines(result: SessionResponse): Headline[] {
  const questions = result.questions
  const calm = questions.filter((q) => q.level === 'low').length
  const triggering = questions.find(
    (q) => q.number === result.summary.most_triggering_question,
  )
  const measured = questions
    .map((q) => q.recovery_pct)
    .filter((value): value is number => value !== null)
  const settled = median(measured)

  return [
    {
      label: 'Paling bikin tegang',
      value: triggering ? `Pertanyaan ${triggering.number}` : 'Belum jelas',
      hint: triggering ? triggering.text : 'Tidak ada yang menonjol',
    },
    {
      label: 'Lewat dengan santai',
      value: `${calm} dari ${questions.length}`,
      hint:
        calm === questions.length
          ? 'Semuanya kamu lewati dengan tenang'
          : 'Sisanya bikin tegang',
    },
    {
      label: 'Sempat mereda',
      value: settled === null ? 'Belum terukur' : `${Math.round(clamp(settled))}%`,
      hint:
        settled === null
          ? 'Jeda antar pertanyaan kependekan'
          : 'Sebelum pertanyaan berikutnya mulai',
    },
  ]
}

export interface TimelinePoint {
  number: number
  label: string
  level: StressLevel
  pressure: number
}

/**
 * The per-question line, in the order they were asked.
 *
 * Plotted from the LABEL rather than from the underlying percentage change. The
 * percentage is a technical figure a user must not be shown (K4), and the label
 * is what the scoring rule actually decided — so the line and the badges beside
 * it can never disagree.
 */
export function pressureTimeline(result: SessionResponse): TimelinePoint[] {
  return result.questions.map((question) => ({
    number: question.number,
    label: `Q${question.number}`,
    level: question.level,
    pressure: PRESSURE[question.level],
  }))
}
