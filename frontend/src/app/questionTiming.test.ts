/**
 * questionTiming.test.ts — locks the alignment between session and recording.
 *
 * These timings decide which stretch of heart data each question is judged on.
 * Get them wrong and every result describes the wrong moment, with nothing on
 * screen to indicate it. That failure is silent, which is why it is pinned here.
 *
 * The fixture times are RECORDING times, because `SessionPage` now runs the
 * resting period on its own clock and hands over timestamps already measured
 * from the start of the recording. This file used to add `baselineMinutes * 60`
 * itself — a shift that assumed, without any way to check, that the person had
 * sat still for exactly that long before opening the interview.
 */

import { describe, expect, it } from 'vitest'
import { DEMO_RR_MS, SIMULATION_SPEED } from '../mocks/recording'
import { buildQuestionTimeline, sessionElapsedSec, type AnsweredQuestion } from './questionTiming'
import type { BankQuestion } from '../mocks/questionBank'

const q = (text: string, isDifficult = false): BankQuestion => ({
  text,
  type: 'behavioural',
  isDifficult,
  tip: '',
})

// A four-minute resting period ran first, so the first question opens at 240.
const answered: AnsweredQuestion[] = [
  { question: q('Satu'), startedAtSec: 240, endedAtSec: 300 },
  { question: q('Dua', true), startedAtSec: 340, endedAtSec: 430 },
  { question: q('Tiga'), startedAtSec: 460, endedAtSec: 540 },
]

describe('buildQuestionTimeline', () => {
  it('passes recording times through without shifting them', () => {
    // No offset is added here any more: the times arrive already aligned to the
    // recording, because the resting period was run by the session screen rather
    // than assumed to have happened before it.
    const timeline = buildQuestionTimeline(answered)
    expect(timeline[0]!.answer_start_sec).toBe(240)
    expect(timeline[0]!.answer_end_sec).toBe(300)
    expect(timeline[1]!.answer_start_sec).toBe(340)
  })

  it('runs each gap up to the next question', () => {
    const timeline = buildQuestionTimeline(answered)
    expect(timeline[0]!.gap_end_sec).toBe(340)
    expect(timeline[1]!.gap_end_sec).toBe(460)
  })

  it('leaves the last question with no gap at all', () => {
    // Nothing was observed after the final answer, and we do not know whether
    // the recording even continued. A zero-length gap makes the backend report
    // recovery as null rather than inventing a number from a period we never
    // saw.
    const timeline = buildQuestionTimeline(answered)
    const last = timeline[timeline.length - 1]!
    expect(last.gap_end_sec).toBe(last.answer_end_sec)
  })

  it('numbers questions from one and carries their metadata', () => {
    const timeline = buildQuestionTimeline(answered)
    expect(timeline.map((entry) => entry.number)).toEqual([1, 2, 3])
    expect(timeline[1]!.is_difficult).toBe(true)
    expect(timeline[1]!.text).toBe('Dua')
  })

  it('rounds sub-second times, since the clock ticks four times a second', () => {
    const timeline = buildQuestionTimeline([
      { question: q('Satu'), startedAtSec: 120.4, endedAtSec: 180.6 },
    ])
    expect(timeline[0]!.answer_start_sec).toBe(120)
    expect(timeline[0]!.answer_end_sec).toBe(181)
  })

  it('returns nothing when no question was answered', () => {
    expect(buildQuestionTimeline([])).toEqual([])
  })
})

describe('the session clock', () => {
  it('runs at real speed with a real sensor', () => {
    expect(sessionElapsedSec(12_000, false)).toBe(12)
    expect(sessionElapsedSec(125_400, false)).toBe(125)
  })

  it('runs at the playback speed in dev mode', () => {
    expect(sessionElapsedSec(12_000, true)).toBe(12 * SIMULATION_SPEED)
  })

  it('agrees with the recording the simulated sensor is playing', () => {
    /**
     * THE ONE THAT MATTERS, and the only test here that could not be satisfied
     * by copying a constant from one file to another.
     *
     * Both sides are worked out independently. The clock is asked how many
     * seconds of recording have passed; the recording is replayed beat by beat
     * at the same speed and asked the same thing. If either side stops scaling,
     * or scales by a different factor, the two answers separate — and in the
     * running app nothing would look wrong: the questions would simply be
     * scored against minutes the person was never in.
     */
    const REAL_MS = 30_000

    const clockSays = sessionElapsedSec(REAL_MS, true)

    let realSpent = 0
    let recordingMs = 0
    for (const beat of DEMO_RR_MS) {
      const cost = beat / SIMULATION_SPEED
      if (realSpent + cost > REAL_MS) break
      realSpent += cost
      recordingMs += beat
    }

    // Within one beat: the playback loop can only stop on a beat boundary.
    expect(Math.abs(clockSays - recordingMs / 1000)).toBeLessThan(1.5)
  })

  it('leaves the resting period exactly as long as it claims to be', () => {
    /**
     * Two minutes of RECORDING, whatever the playback speed. If the rest ended
     * after two minutes of wall clock in dev mode, it would cover twenty minutes
     * of recording and swallow the whole stressor into the baseline — the
     * questions would then be compared against the stress they were meant to
     * reveal.
     */
    const restSec = 2 * 60
    const realMsNeeded = (restSec * 1000) / SIMULATION_SPEED

    expect(sessionElapsedSec(realMsNeeded, true)).toBe(restSec)
    expect(sessionElapsedSec(realMsNeeded - 1000, true)).toBeLessThan(restSec)
  })
})
