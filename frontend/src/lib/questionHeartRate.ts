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
 * THE OFFSET IS THE WHOLE DIFFICULTY. Question times are stamped by the
 * session clock, which starts when the person presses start; the recording
 * starts earlier, when the sensor paired. `offsetSec` is the distance between
 * those clocks — drop it and every window slides onto the wrong stretch of
 * recording, silently, with a perfectly plausible-looking curve. That bug
 * class already bit this project once; the test suite pins it here.
 */

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

/** Fewer beats than this draws nothing — two dots are not a curve. */
const MIN_BEATS = 5

/** Padding around the observed range so the line never touches the frame. */
const DOMAIN_PAD_BPM = 3

export function questionHeartRates(
  rrMs: readonly number[],
  offsetSec: number,
  timeline: QuestionTimelineEntry[],
): HeartRateByQuestion | null {
  if (rrMs.length < MIN_BEATS) return null

  // Beat timestamps in RECORDING seconds, at the beat's end.
  const beatAt: number[] = []
  let total = 0
  for (const rr of rrMs) {
    total += rr / 1000
    beatAt.push(total)
  }

  const byNumber = new Map<number, QuestionHeartRate>()
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY

  for (const entry of timeline) {
    const start = entry.answer_start_sec + offsetSec
    const end = entry.answer_end_sec + offsetSec

    const points: HeartPoint[] = []
    for (let i = 0; i < rrMs.length; i++) {
      if (beatAt[i]! >= start && beatAt[i]! < end) {
        points.push({ t: beatAt[i]! - start, bpm: 60000 / rrMs[i]! })
      }
    }
    if (points.length < MIN_BEATS) continue

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
