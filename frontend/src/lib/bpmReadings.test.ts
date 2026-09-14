/**
 * bpmReadings.test.ts — the heart-rate stream a watch leaves behind.
 *
 * Every function here feeds a decision the backend makes about the whole
 * session: which path it takes, and where its questions sit in time. A wrong
 * coverage silently moves a chest-strap session onto the heart-rate path, and a
 * wrong origin silently moves every question.
 */

import { describe, expect, it } from 'vitest'
import {
  appendReading,
  MAX_REPORTED_BPM,
  MIN_REPORTED_BPM,
  rrCoverage,
  streamElapsedSec,
  toBpmSamples,
  type BpmReading,
} from './bpmReadings'

const steady = (count: number, bpm = 72, stepSec = 1): BpmReading[] =>
  Array.from({ length: count }, (_, i) => ({ atSec: i * stepSec, bpm }))

describe('keeping a report', () => {
  it('keeps a plausible heart rate with its time', () => {
    expect(appendReading([], 3, 70)).toEqual([{ atSec: 3, bpm: 70 }])
  })

  it('drops the zero a watch sends while it has lost contact', () => {
    const kept = steady(2)
    // Returned untouched, not copied: a dropped packet must not re-render.
    expect(appendReading(kept, 5, 0)).toBe(kept)
  })

  it('drops anything outside the range the backend accepts', () => {
    const kept = steady(1)
    expect(appendReading(kept, 5, MIN_REPORTED_BPM - 1)).toBe(kept)
    expect(appendReading(kept, 5, MAX_REPORTED_BPM + 1)).toBe(kept)
    expect(appendReading(kept, 5, MIN_REPORTED_BPM)).toHaveLength(2)
    expect(appendReading(kept, 5, MAX_REPORTED_BPM)).toHaveLength(2)
  })

  it('matches the bounds the backend derives from its interval physiology', () => {
    // 60000 / 2000 ms and 60000 / 300 ms. Drift here and a whole session is
    // refused over a single report the browser thought was fine.
    expect(MIN_REPORTED_BPM).toBe(60000 / 2000)
    expect(MAX_REPORTED_BPM).toBe(60000 / 300)
  })

  it('drops a report that does not move forward in time', () => {
    const kept = steady(3)
    expect(appendReading(kept, 2, 70)).toBe(kept)
    expect(appendReading(kept, 1, 70)).toBe(kept)
  })
})

describe('measuring coverage', () => {
  it('is zero for a watch that sends no intervals', () => {
    expect(rrCoverage([], steady(181))).toBe(0)
  })

  it('is one for a strap that delivers every beat', () => {
    // 180 s of reports, 200 beats of 900 ms = 180 s of intervals.
    const beats = Array.from({ length: 200 }, () => 900)
    expect(rrCoverage(beats, steady(181))).toBeCloseTo(1, 5)
  })

  it('is a half when half the stream lost its beats', () => {
    const beats = Array.from({ length: 100 }, () => 900)
    expect(rrCoverage(beats, steady(181))).toBeCloseTo(0.5, 5)
  })

  it('never exceeds one', () => {
    const beats = Array.from({ length: 400 }, () => 900)
    expect(rrCoverage(beats, steady(181))).toBe(1)
  })

  it('claims nothing when there is no span to cover', () => {
    expect(rrCoverage([900, 900], steady(1))).toBe(0)
    expect(rrCoverage([900, 900], [])).toBe(0)
  })
})

describe('the request shape', () => {
  it('counts seconds from the first report, whatever clock stamped it', () => {
    const readings = [{ atSec: 12.5, bpm: 70 }, { atSec: 13.5, bpm: 71 }]
    expect(toBpmSamples(readings)).toEqual([
      { at_sec: 0, bpm: 70 },
      { at_sec: 1, bpm: 71 },
    ])
  })

  it('measures elapsed time on the same origin', () => {
    expect(streamElapsedSec([{ atSec: 12.5, bpm: 70 }, { atSec: 42.5, bpm: 71 }]))
      .toBe(30)
    expect(streamElapsedSec(steady(1))).toBe(0)
  })
})
