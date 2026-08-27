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
 * So each axis below is a percentage OF THIS SESSION: a share of its questions,
 * a median of its own recoveries, a comparison of its own halves. Read one out
 * loud and it describes something that happened, in a sentence a person could
 * check against their memory of the interview.
 *
 * WHAT THEY ARE NOT. They are not traits. "Calm 60" means three of five
 * questions passed without a spike, not that the person is 60% calm. The naming
 * throughout follows the rule already set in `docs/development_journey.md`:
 * feedback is phrased as trainable behaviour, never as a label about the person
 * — "needed longer to settle after hard questions", not "low emotional
 * regulation". The chart carries that caveat in its own caption, because a
 * radar looks like a personality profile whatever the axes are called.
 *
 * K4 applies here too: nothing in this file produces a feature name, a raw
 * value, or a score out of four. Those exist in the response and stay behind
 * the developer panel.
 */

import { formatResilience } from './format'
import type { QuestionResult, SessionResponse, StressLevel } from '../types/api'

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

export interface Dimension {
  key: string
  /** Axis label on the chart. Short, and never a trait. */
  label: string
  /** 0-100, or null when this session could not measure it. */
  value: number | null
  /** One sentence a person can check against their own memory of the session. */
  meaning: string
  /** Why it cannot be shown, when `value` is null. */
  unmeasured?: string
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

/**
 * Share of questions answered without a pressure spike.
 *
 * Counts labels rather than averaging them: the label is what the rule actually
 * decided, and a person can verify this number by looking at the badges on the
 * cards below the chart.
 */
function calmness(questions: QuestionResult[]): Dimension {
  const calm = questions.filter((q) => q.level === 'low').length
  return {
    key: 'calm',
    label: 'Calm',
    value: questions.length ? (calm / questions.length) * 100 : null,
    meaning: `Kamu santai di ${calm} dari ${questions.length} pertanyaan`,
  }
}

/**
 * How much of the rise had settled again before the next question began.
 *
 * Null when no question had a long enough pause after it — which is a different
 * statement from "did not recover", and the difference is preserved all the way
 * from the Python side. Showing zero here would tell somebody they never calmed
 * down, on the strength of a measurement nobody took.
 */
function recovery(questions: QuestionResult[]): Dimension {
  const measured = questions
    .map((q) => q.recovery_pct)
    .filter((value): value is number => value !== null)
  const middle = median(measured)

  return {
    key: 'recovery',
    label: 'Recovery',
    value: middle === null ? null : clamp(middle),
    meaning:
      middle === null
        ? 'Belum terukur'
        : `Tekanan turun sekitar ${Math.round(clamp(middle))}% sebelum lanjut`,
    unmeasured:
      middle === null
        ? 'Jedanya kependekan buat diukur. Bukan berarti kamu tidak pulih.'
        : undefined,
  }
}

/**
 * Where the session landed on reaction size and recovery speed, as one value.
 *
 * READ FROM THE BACKEND'S LABEL, NOT RECOMPUTED. `summary.resilience` is
 * decided by the rule in `features/dynamics.py` from its own calibrated
 * thresholds; deriving a second answer here from the per-question numbers
 * would let the chart and the words disagree. The frontend only translates
 * the quadrant onto the 0-100 scale the radar needs.
 *
 * The mapping is additive, not ranked: the quadrant has two independent
 * favourable halves — a small reaction and a fast recovery — and each one
 * contributes 50. That is why two mixed quadrants share the middle: "big
 * reaction but fast recovery" and "small reaction but slow recovery" each got
 * one half right, and pretending one of them outranks the other would be a
 * claim the rule never made. The `meaning` sentence tells them apart.
 *
 * Null when the quadrant is null: recovery was never measurable, one axis of
 * the definition is missing, and inventing a value would state a conclusion
 * about a measurement nobody took.
 */
function resilience(quadrant: SessionResponse['summary']['resilience']): Dimension {
  if (quadrant === null) {
    return {
      key: 'resilience',
      label: 'Resilience',
      value: null,
      meaning: 'Belum terukur',
      unmeasured:
        'Pemulihanmu belum terukur, jadi bagian ini belum bisa disimpulkan.',
    }
  }

  const smallReaction =
    quadrant === 'high resilience' || quadrant === 'held-in tension'
  const fastRecovery =
    quadrant === 'high resilience' || quadrant === 'responsive but flexible'

  return {
    key: 'resilience',
    label: 'Resilience',
    value: (smallReaction ? 50 : 0) + (fastRecovery ? 50 : 0),
    meaning: formatResilience(quadrant),
  }
}

/**
 * The three axes of the response chart, in a fixed order.
 *
 * Fixed because the shape of a radar is only comparable between two sessions if
 * the axes stay where they are. Sorting them by value would make every session
 * look like a different chart.
 *
 * A fourth axis, "evenness", was built and then removed. It measured the gap
 * between the hardest and easiest question — which the timeline beside the chart
 * already shows better, as a shape rather than a number. It also needed
 * explaining every time somebody saw it, and an axis that has to be explained is
 * an axis that is not communicating.
 */
export function responseDimensions(result: SessionResponse): Dimension[] {
  const questions = result.questions
  return [
    calmness(questions),
    recovery(questions),
    resilience(result.summary.resilience),
  ]
}

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
