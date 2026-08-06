/**
 * rule.ts — a mirror of the backend's scoring rule, for BUILDING FIXTURES ONLY.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * DO NOT IMPORT THIS FROM APPLICATION CODE.
 *
 * Mandatory rule #1 of this project is that the numbers are computed once, by
 * Python, and never re-derived anywhere else. A second implementation of the
 * classifier that the UI could reach would break that guarantee: the screen
 * might then disagree with the result the backend actually produced, and the
 * thesis claim that every displayed label is reproducible would no longer hold.
 *
 * This copy exists so the mock fixtures are internally consistent — so that a
 * point with `delta_rmssd_pct: -41` really does carry the level, score and
 * evidence the backend would have given it, instead of numbers invented by
 * hand that happen to look plausible. It is deleted the moment the real API is
 * connected. `mocks.test.ts` enforces that nothing outside `src/mocks/` imports
 * it.
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * Mirrors `src/hrv_rag/features/stress_level.py` and the thresholds frozen in
 * `src/hrv_rag/config/settings.py` on 3 August 2026:
 *
 *     RMSSD below baseline   -20% -> 1 point    -30% -> 2 points
 *     heart rate above it     +5% -> 1 point    +15% -> 2 points
 *
 *     0 points -> low      1-2 -> moderate      3-4 -> high
 */

import type { StressLevel } from '../types/api'

const RMSSD_MODERATE_PCT = -20
const RMSSD_HIGH_PCT = -30
const HR_MODERATE_PCT = 5
const HR_HIGH_PCT = 15

function scoreFeature(
  value: number,
  moderate: number,
  high: number,
  rising: boolean,
): number {
  if (rising) return value >= high ? 2 : value >= moderate ? 1 : 0
  return value <= high ? 2 : value <= moderate ? 1 : 0
}

export interface MockVerdict {
  level: StressLevel
  score: number
  evidence: string[]
  features_disagree: boolean
}

/** Reproduces `classify()` for one pair of reactivity percentages. */
export function mockVerdict(
  deltaRmssdPct: number,
  deltaHrPct: number,
): MockVerdict {
  const rmssdPoints = scoreFeature(
    deltaRmssdPct,
    RMSSD_MODERATE_PCT,
    RMSSD_HIGH_PCT,
    false,
  )
  const hrPoints = scoreFeature(deltaHrPct, HR_MODERATE_PCT, HR_HIGH_PCT, true)
  const score = rmssdPoints + hrPoints

  // Wording copied from stress_level.py so the developer panel shows the same
  // strings the backend would send.
  const evidence = [
    `RMSSD ${Math.abs(deltaRmssdPct).toFixed(0)}% ` +
      `${deltaRmssdPct < 0 ? 'below' : 'above'} baseline (${rmssdPoints} pt)`,
    `heart rate ${Math.abs(deltaHrPct).toFixed(0)}% ` +
      `${deltaHrPct > 0 ? 'above' : 'below'} baseline (${hrPoints} pt)`,
  ]

  // The vagal marker says calm while the heart says otherwise. Speaking aloud
  // can produce this, which is exactly why an interview needs it flagged.
  const featuresDisagree =
    deltaRmssdPct > 10 && deltaHrPct > HR_MODERATE_PCT
  if (featuresDisagree) {
    evidence.push(
      'features disagree: RMSSD rose while heart rate also rose, ' +
        'which speaking can cause',
    )
  }

  const level: StressLevel =
    score >= 3 ? 'high' : score >= 1 ? 'moderate' : 'low'

  return { level, score, evidence, features_disagree: featuresDisagree }
}
