/**
 * heartStream.test.ts — the live trace's arithmetic, and its one design rule.
 *
 * The rule worth a test: the y-scale is FIXED to the physiological range. An
 * auto-fitted scale would magnify a calm person's tiny fluctuations into a
 * dramatic waveform — the calmer the person, the more anxious the line — which
 * is the exact feedback loop that got the old "mulai tegang" badge removed.
 */

import { describe, expect, it } from 'vitest'
import { STREAM_WINDOW_BEATS, streamPath, streamPoints } from './heartStream'

const W = 280
const H = 48

describe('the live pulse trace', () => {
  it('shows nothing until there are two beats to connect', () => {
    expect(streamPoints([], W, H)).toEqual([])
    expect(streamPoints([850], W, H)).toEqual([])
    expect(streamPath([850], W, H)).toBe('')
  })

  it('keeps a calm trace visually calm — the scale never auto-fits', () => {
    // 68 vs 72 bpm: a 4-bpm wiggle. On the fixed 40-160 scale that is a small
    // fraction of the height; an auto-fitted scale would stretch it to the
    // full height and make calm look frantic.
    const calm = [60000 / 68, 60000 / 72, 60000 / 68, 60000 / 72]
    const ys = streamPoints(calm, W, H).map((p) => p.y)
    const swing = Math.max(...ys) - Math.min(...ys)

    expect(swing).toBeLessThan(H * 0.1)
    expect(swing).toBeGreaterThan(0)      // still real, just not magnified
  })

  it('maps higher heart rate to a higher line', () => {
    // SVG y grows downward, so faster beats (higher bpm) must give SMALLER y.
    const [slow, fast] = streamPoints([60000 / 60, 60000 / 120], W, H)
    expect(fast!.y).toBeLessThan(slow!.y)
  })

  it('clamps artefact beats instead of letting them wreck the scale', () => {
    // A 200 ms interval reads as 300 bpm — an artefact, not a heart. It pins
    // to the top of the range rather than pushing everything else off-scale.
    const ys = streamPoints([850, 200, 850], W, H).map((p) => p.y)
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(0)
    expect(Math.max(...ys)).toBeLessThanOrEqual(H)
  })

  it('shows only the most recent window of beats', () => {
    const many = Array.from({ length: 500 }, () => 850)
    expect(streamPoints(many, W, H).length).toBe(STREAM_WINDOW_BEATS)
  })
})
