/**
 * timeline.ts — fixture for V1, `POST /api/v1/analyze/timeline`.
 *
 * A 15-minute recording from a chest strap. The first four minutes are the
 * quiet baseline, so the timeline itself starts at second 240.
 *
 * Windows are 60 seconds long and advance every 30 seconds, matching
 * `features/segmentation.py`. That is why the baseline covers seven windows
 * (starting at 0, 30, 60 … 180) rather than four: it is 240 seconds of
 * recording, not 240 seconds of independent measurements. Neighbouring points
 * share half their data, which is the trap `docs/frontend_plan.md` section 6
 * warns about — the chart must not present two adjacent points as two
 * corroborating readings.
 *
 * Levels, scores and evidence are derived by `mockVerdict` rather than typed by
 * hand, so the fixture cannot drift out of agreement with the real scoring rule.
 */

import type {
  Baseline,
  TimelinePoint,
  TimelineResponse,
  TimelineSummary,
} from '../types/api'
import { mockVerdict } from './rule'

const WINDOW_SEC = 60
const HOP_SEC = 30
const BASELINE_SEC = 240

/**
 * [start second, RMSSD change %, heart rate change %].
 *
 * The arc: a settled opening, a sharp climb around minute six that holds for
 * about two minutes, a slow decline, and one late window where the two markers
 * disagree — RMSSD rises while heart rate also rises, the pattern that speaking
 * aloud can produce.
 */
const ARC: ReadonlyArray<readonly [number, number, number]> = [
  [240, -8, 2],
  [270, -12, 3],
  [300, -22, 6],
  [330, -38, 22],
  [360, -45, 30],
  [390, -52, 34],
  [420, -41, 26],
  [450, -33, 19],
  [480, -26, 12],
  [510, -21, 8],
  [540, -14, 4],
  [570, -9, 1],
  [600, -18, 6],
  [630, -11, 3],
  [660, -6, 1],
  [690, 14, 9],
  [720, -5, 2],
  [750, -3, 0],
  [780, -7, 1],
  [810, -2, -1],
  [840, -4, 0],
]

const points: TimelinePoint[] = ARC.map(([startSec, rmssd, hr]) => {
  const endSec = startSec + WINDOW_SEC
  const verdict = mockVerdict(rmssd, hr)
  return {
    // Fractional on purpose: with a 30-second hop these run 5, 5.5, 6 …
    minute: endSec / 60,
    start_sec: startSec,
    end_sec: endSec,
    level: verdict.level,
    score: verdict.score,
    delta_rmssd_pct: rmssd,
    delta_hr_pct: hr,
    evidence: verdict.evidence,
    features_disagree: verdict.features_disagree,
  }
})

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 1
    ? sorted[mid]!
    : (sorted[mid - 1]! + sorted[mid]!) / 2
}

/** Derived from the points, never typed separately, so the two cannot disagree. */
function summarise(timeline: TimelinePoint[]): TimelineSummary {
  const peak = timeline.reduce((worst, p) =>
    p.delta_rmssd_pct < worst.delta_rmssd_pct ? p : worst,
  )
  return {
    peak_minute: peak.minute,
    median_reactivity_pct: median(timeline.map((p) => p.delta_rmssd_pct)),
    count_low: timeline.filter((p) => p.level === 'low').length,
    count_moderate: timeline.filter((p) => p.level === 'moderate').length,
    count_high: timeline.filter((p) => p.level === 'high').length,
  }
}

const STABLE_BASELINE: Baseline = {
  rmssd_ms: 32,
  mean_hr_bpm: 73,
  n_segments: BASELINE_SEC / HOP_SEC - 1, // 7 windows fit inside 240 seconds
  is_stable: true,
  // Seven windows is 'limited', not 'full' — the two fields answer different
  // questions and a fixture that always said 'full' would let a screen conflate
  // them without any test noticing.
  evidence: 'limited',
  warning: null,
}

export const mockTimeline: TimelineResponse = {
  session_id: 'demo-timeline-001',
  modality: 'ECG',
  tier: 'T2',
  duration_sec: 900,
  baseline: STABLE_BASELINE,
  timeline: points,
  summary: summarise(points),
  narrative: {
    ringkasan:
      'Beberapa menit awal berjalan tenang. Sekitar menit keenam tekananmu ' +
      'naik tajam dan bertahan tinggi kurang lebih dua menit, lalu perlahan ' +
      'turun sampai akhir rekaman.',
    rekomendasi:
      'Bagian tengah sesi yang paling menuntut. Coba sisipkan jeda napas ' +
      'singkat sebelum masuk ke bagian itu, lalu lihat apakah puncaknya ' +
      'bergeser di latihan berikutnya.',
    penyemangat:
      'Menjelang akhir sesi kamu kembali tenang. Itu tanda pemulihan yang ' +
      'baik, dan bagian yang paling bisa kamu andalkan.',
  },
  meta: {
    kb_version: 'kb_v2.0',
    model: 'gemini-2.5-flash',
    trustworthy: true,
    prompt_version: 'HRV_session_narrative',
    rule_version: 'K16-2026-08-03',
  },
}

/**
 * The same recording, but with a resting period that was itself too variable to
 * trust.
 *
 * Kept as a separate fixture because it is the case most likely to be forgotten
 * during development: every number in the response is a comparison against the
 * baseline, so when the baseline is shaky the entire reading weakens. The screen
 * has to say that out loud instead of showing the levels as if nothing were
 * wrong.
 */
export const mockTimelineUnstableBaseline: TimelineResponse = {
  ...mockTimeline,
  session_id: 'demo-timeline-002',
  baseline: {
    ...STABLE_BASELINE,
    is_stable: false,
    warning:
      'Detak jantung masih naik-turun selama periode tenang, kemungkinan ' +
      'karena baru selesai bergerak atau belum sempat duduk diam.',
  },
}
