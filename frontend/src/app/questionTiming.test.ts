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
import { buildQuestionTimeline, type AnsweredQuestion } from './questionTiming'
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
