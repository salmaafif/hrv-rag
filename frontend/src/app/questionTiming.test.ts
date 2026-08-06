/**
 * questionTiming.test.ts — locks the alignment between interview and recording.
 *
 * These timings decide which stretch of heart data each question is judged on.
 * Get the offset wrong and every result is a description of the wrong moment,
 * with nothing on screen to indicate it. That failure is silent, which is why
 * it is pinned here.
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

const answered: AnsweredQuestion[] = [
  { question: q('Satu'), startedAtSec: 0, endedAtSec: 60 },
  { question: q('Dua', true), startedAtSec: 100, endedAtSec: 190 },
  { question: q('Tiga'), startedAtSec: 220, endedAtSec: 300 },
]

describe('buildQuestionTimeline', () => {
  it('shifts every time by the resting period', () => {
    // Four minutes of quiet came first, so interview second 0 is recording
    // second 240.
    const timeline = buildQuestionTimeline(answered, 4)
    expect(timeline[0]!.answer_start_sec).toBe(240)
    expect(timeline[0]!.answer_end_sec).toBe(300)
    expect(timeline[1]!.answer_start_sec).toBe(340)
  })

  it('runs each gap up to the next question', () => {
    const timeline = buildQuestionTimeline(answered, 4)
    // Question 1 ended at 300 and question 2 appeared at 340.
    expect(timeline[0]!.gap_end_sec).toBe(340)
    expect(timeline[1]!.gap_end_sec).toBe(460)
  })

  it('leaves the last question with no gap at all', () => {
    // Nothing was observed after the final answer, and we do not know whether
    // the recording even continued. A zero-length gap makes the backend report
    // recovery as null rather than inventing a number from a period we never
    // saw.
    const timeline = buildQuestionTimeline(answered, 4)
    const last = timeline[timeline.length - 1]!
    expect(last.gap_end_sec).toBe(last.answer_end_sec)
  })

  it('numbers questions from one and carries their metadata', () => {
    const timeline = buildQuestionTimeline(answered, 4)
    expect(timeline.map((entry) => entry.number)).toEqual([1, 2, 3])
    expect(timeline[1]!.is_difficult).toBe(true)
    expect(timeline[1]!.text).toBe('Dua')
  })

  it('handles a different resting period', () => {
    const timeline = buildQuestionTimeline(answered, 2)
    expect(timeline[0]!.answer_start_sec).toBe(120)
  })

  it('returns nothing when no question was answered', () => {
    expect(buildQuestionTimeline([], 4)).toEqual([])
  })
})
