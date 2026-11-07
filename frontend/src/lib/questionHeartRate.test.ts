/**
 * questionHeartRate.test.ts — slicing the recording by question.
 *
 * The test that matters most is the offset one. Dropping the offset produces a
 * chart that renders beautifully and describes the wrong minute — the failure
 * mode this project has already met once through the API, now guarded on the
 * client too.
 */

import { describe, expect, it } from 'vitest'
import {
  questionHeartRates,
  questionHeartRatesFromReadings,
} from './questionHeartRate'
import type { QuestionTimelineEntry } from '../types/api'

function entry(number: number, start: number, end: number): QuestionTimelineEntry {
  return {
    number, text: `Q${number}`, type: 'behavioural',
    answer_start_sec: start, answer_end_sec: end, gap_end_sec: end,
    is_difficult: false,
  }
}

/** One beat per second, so beat #n ends at recording second n+1. */
const oneHz = (n: number) => Array.from({ length: n }, () => 1000)

describe('slicing the recording by question', () => {
  it('honours the offset between the sensor clock and the session clock', () => {
    /**
     * 100 s of beats existed before the person pressed start. A question at
     * session seconds 10-20 therefore lives at recording seconds 110-120.
     * Make those ten beats uniquely fast so grabbing any OTHER stretch is
     * visible: without the offset the window lands on 60 bpm and the mean
     * comes out ~60 instead of ~120.
     */
    const rr = oneHz(200)
    // Twenty 500 ms beats span ten seconds: recording 110-120 s runs at 120 bpm.
    for (let i = 110; i < 130; i++) rr[i] = 500

    const result = questionHeartRates(rr, 100, [entry(1, 10, 20)])!
    const q1 = result.byNumber.get(1)!

    expect(q1.meanBpm).toBeGreaterThan(100)
  })

  it('slices each question to its own answer window', () => {
    const rr = oneHz(300)
    const result = questionHeartRates(rr, 0, [
      entry(1, 10, 40), entry(2, 60, 90),
    ])!

    const q1 = result.byNumber.get(1)!
    expect(q1.points[0]!.t).toBeGreaterThanOrEqual(0)
    expect(q1.points[q1.points.length - 1]!.t).toBeLessThan(30)
    expect(result.byNumber.get(2)!.points.length).toBeGreaterThan(20)
  })

  it('shares one bpm scale across every question', () => {
    /**
     * A calm question and a racing one must sit on the same axis — per-panel
     * auto-fit would scale the difference away, which is the one comparison
     * the chart exists to offer.
     */
    const rr = [...oneHz(100), ...Array.from({ length: 100 }, () => 500)]
    const result = questionHeartRates(rr, 0, [
      entry(1, 10, 40),     // 60 bpm stretch
      entry(2, 110, 140),   // 120 bpm stretch
    ])!

    expect(result.domain.min).toBeLessThan(65)
    expect(result.domain.max).toBeGreaterThan(115)
  })

  it('draws nothing for a question with too few beats, rather than a two-dot line', () => {
    const result = questionHeartRates(oneHz(100), 0, [
      entry(1, 10, 12),     // two beats
      entry(2, 20, 50),
    ])!

    expect(result.byNumber.has(1)).toBe(false)
    expect(result.byNumber.has(2)).toBe(true)
  })

  it('returns null when the browser holds no recording at all', () => {
    expect(questionHeartRates([], 0, [entry(1, 0, 30)])).toBeNull()
    expect(questionHeartRates(oneHz(100), 0, [entry(1, 500, 530)])).toBeNull()
  })
})

describe('slicing a watch that reports heart rate only', () => {
  /** One report a second, starting wherever the device clock happened to be. */
  const reports = (count: number, startSec = 0, bpm = 60) =>
    Array.from({ length: count }, (_, i) => ({ atSec: startSec + i, bpm }))

  it('draws the reports as sent, without turning them into beats', () => {
    const result = questionHeartRatesFromReadings(
      reports(100, 0, 72), 0, [entry(1, 10, 40)],
    )!
    const q1 = result.byNumber.get(1)!
    expect(q1.points.every((p) => p.bpm === 72)).toBe(true)
    expect(q1.points).toHaveLength(30)
  })

  it('honours the offset measured on the report clock', () => {
    // 100 s of reports before start; a question at session 10-20 is report
    // second 110-120. Only that stretch is fast, so any other window reads 60.
    const readings = reports(200)
    for (let i = 110; i < 120; i++) readings[i] = { atSec: i, bpm: 120 }

    const result = questionHeartRatesFromReadings(readings, 100, [entry(1, 10, 20)])!
    expect(result.byNumber.get(1)!.meanBpm).toBe(120)
  })

  it('counts from the first report, wherever the device clock started', () => {
    // The same stream stamped from 37.5 s must slice exactly as from zero.
    const fromZero = questionHeartRatesFromReadings(reports(100), 0, [entry(1, 10, 40)])!
    const shifted = questionHeartRatesFromReadings(
      reports(100, 37.5), 0, [entry(1, 10, 40)],
    )!
    expect(shifted.byNumber.get(1)!.points).toEqual(fromZero.byNumber.get(1)!.points)
  })

  it('returns null with too few reports to draw anything', () => {
    expect(questionHeartRatesFromReadings(reports(4), 0, [entry(1, 0, 30)])).toBeNull()
  })
})
