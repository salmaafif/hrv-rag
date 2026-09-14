/**
 * questionHeartRate.ts — each question's stretch of the heart recording.
 *
 * COMPUTED IN THE BROWSER FROM DATA THE BROWSER ALREADY HOLDS. The raw beat
 * series never leaves the session (it lives in memory from the live sensor),
 * and the API contract gains nothing: this is presentation slicing, not a new
 * measurement. The backend keeps owning every number that carries a claim.
 *
 * K4 boundary, stated once: heart rate in bpm is everyday language and is
 * allowed in front of a user — the owner set that precedent with the live
 * trace on the session screen. RMSSD, scores and feature names remain
 * forbidden here as everywhere.
 *
 * TWO SOURCES, ONE SLICER. A strap gives beat intervals, and each beat becomes
 * a point at the moment it ended. A watch gives heart-rate reports, and each
 * report is a point as it is — never turned into beats. After that both are the
 * same thing, a heart rate at a second of the recording, cut by the same rule.
 *
 * THE OFFSET IS THE WHOLE DIFFICULTY. Question times are stamped by the
 * session clock, which starts when the person presses start; the recording
 * starts earlier, when the sensor paired. `offsetSec` is the distance between
 * those clocks — drop it and every window slides onto the wrong stretch of
 * recording, silently, with a perfectly plausible-looking curve. That bug
 * class already bit this project once; the test suite pins it here. Each
 * source carries its own offset, measured on its own clock.
 */

import type { BpmReading } from './bpmReadings'
import type { QuestionTimelineEntry } from '../types/api'

export interface HeartPoint {
  /** Seconds since the answer began. */
  t: number
  bpm: number
}

export interface QuestionHeartRate {
  points: HeartPoint[]
  meanBpm: number
}

export interface HeartRateByQuestion {
  byNumber: Map<number, QuestionHeartRate>
  /**
   * ONE bpm scale shared by every question's panel. Each panel auto-fitted to
   * its own range would make a flat question and a spiky one look identical —
   * the entire comparison the graph exists to show would be scaled away.
   */
  domain: { min: number; max: number }
}

/** A heart rate at a second of the recording. */
interface TimedRate {
  atSec: number
  bpm: number
}

/** Fewer points than this draws nothing — two dots are not a curve. */
const MIN_POINTS = 5

/** Padding around the observed range so the line never touches the frame. */
const DOMAIN_PAD_BPM = 3

/** From beat intervals: each beat is a point at the moment it ended. */
export function questionHeartRates(
  rrMs: readonly number[],
  offsetSec: number,
  timeline: QuestionTimelineEntry[],
): HeartRateByQuestion | null {
  if (rrMs.length < MIN_POINTS) return null

  const rates: TimedRate[] = []
  let total = 0
  for (const rr of rrMs) {
    total += rr / 1000
    rates.push({ atSec: total, bpm: 60000 / rr })
  }
  return slice(rates, offsetSec, timeline)
}

/**
 * From heart-rate reports: each report is a point as the device sent it.
 *
 * `offsetSec` must be measured on the REPORT clock
 * (`SessionState.sessionBpmOffsetSec`), counted from the first report — which
 * is why the readings are re-based on that first report here.
 */
export function questionHeartRatesFromReadings(
  readings: readonly BpmReading[],
  offsetSec: number,
  timeline: QuestionTimelineEntry[],
): HeartRateByQuestion | null {
  if (readings.length < MIN_POINTS) return null
  const origin = readings[0]!.atSec
  return slice(
    readings.map((reading) => ({ atSec: reading.atSec - origin, bpm: reading.bpm })),
    offsetSec,
    timeline,
  )
}

function slice(
  rates: readonly TimedRate[],
  offsetSec: number,
  timeline: QuestionTimelineEntry[],
): HeartRateByQuestion | null {
  const byNumber = new Map<number, QuestionHeartRate>()
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY

  for (const entry of timeline) {
    const start = entry.answer_start_sec + offsetSec
    const end = entry.answer_end_sec + offsetSec

    const points: HeartPoint[] = []
    for (const rate of rates) {
      if (rate.atSec >= start && rate.atSec < end) {
        points.push({ t: rate.atSec - start, bpm: rate.bpm })
      }
    }
    if (points.length < MIN_POINTS) continue

    const meanBpm =
      points.reduce((sum, p) => sum + p.bpm, 0) / points.length
    byNumber.set(entry.number, { points, meanBpm })
    for (const p of points) {
      if (p.bpm < min) min = p.bpm
      if (p.bpm > max) max = p.bpm
    }
  }

  if (byNumber.size === 0) return null
  return {
    byNumber,
    domain: { min: min - DOMAIN_PAD_BPM, max: max + DOMAIN_PAD_BPM },
  }
}
