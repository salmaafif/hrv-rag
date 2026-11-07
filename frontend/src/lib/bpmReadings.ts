/**
 * bpmReadings.ts — heart-rate reports, kept alongside the beat intervals.
 *
 * Most smartwatches send a heart-rate value and never the gap between two beats.
 * Until the backend learned to score heart rate alone, such a device connected
 * and produced nothing. So every report's bpm is now kept with the moment it
 * arrived, whether or not intervals came with it — and the BACKEND, not this
 * browser, decides which of the two the session is scored from, because that
 * decision needs a frozen, tested threshold (`TierConfig.min_rr_coverage`).
 *
 * WHAT THIS FILE REFUSES TO DO: turn bpm into intervals, or fill a hole in the
 * stream. A missing report stays missing; the backend flags the hole and reports
 * the affected question as not measured.
 */

import type { BpmSample } from '../types/api'

export interface BpmReading {
  /** Seconds on the report clock. Only differences matter; see `toBpmSamples`. */
  atSec: number
  bpm: number
}

/**
 * The backend's accepted range (`schemas.MIN_BPM`/`MAX_BPM`, derived from the
 * 300-2000 ms interval bounds in `QualityConfig`).
 *
 * A value outside it — most often 0, sent while a watch has lost skin contact —
 * is a missing report, not a heart rate. Kept, it would make the backend refuse
 * the entire session over one packet; dropped, it becomes a short hole the
 * backend already knows how to handle honestly.
 */
export const MIN_REPORTED_BPM = 30
export const MAX_REPORTED_BPM = 200

/**
 * The readings with one more report, or the same array when the report is not
 * usable. Same array, not a copy, so a dropped packet costs no re-render.
 */
export function appendReading(
  readings: readonly BpmReading[],
  atSec: number,
  bpm: number,
): readonly BpmReading[] {
  if (!Number.isFinite(bpm) || bpm < MIN_REPORTED_BPM || bpm > MAX_REPORTED_BPM) {
    return readings
  }
  const last = readings[readings.length - 1]
  // The backend requires strictly increasing times; two packets stamped in the
  // same millisecond would otherwise reject the whole recording.
  if (last !== undefined && atSec <= last.atSec) return readings
  return [...readings, { atSec, bpm }]
}

/** Seconds from the first reading to the last one, or 0 with fewer than two. */
export function streamElapsedSec(readings: readonly BpmReading[]): number {
  if (readings.length < 2) return 0
  return readings[readings.length - 1]!.atSec - readings[0]!.atSec
}

/**
 * Fraction of the report stream's span covered by real beat intervals, 0 to 1.
 *
 * Intervals add up to the time they cover, so a strap that delivers every beat
 * lands near 1, an optical sensor that loses beats while the person talks lands
 * lower, and a watch that sends none lands on 0. Capped at 1 because the first
 * packet can carry beats from just before the first report.
 */
export function rrCoverage(
  rrMs: readonly number[],
  readings: readonly BpmReading[],
): number {
  const span = streamElapsedSec(readings)
  if (span <= 0) return 0
  const covered = rrMs.reduce((total, ms) => total + ms, 0) / 1000
  return Math.min(1, covered / span)
}

/** The request shape: seconds from the FIRST reading, snake_case like the API. */
export function toBpmSamples(readings: readonly BpmReading[]): BpmSample[] {
  const origin = readings[0]?.atSec ?? 0
  return readings.map((reading) => ({
    at_sec: reading.atSec - origin,
    bpm: reading.bpm,
  }))
}
