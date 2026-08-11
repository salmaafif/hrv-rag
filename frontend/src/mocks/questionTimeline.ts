/**
 * questionTimeline.ts — a stand-in question timeline, for V2 only.
 *
 * V3 no longer needs this. It runs the interview itself, so it records when
 * each answer actually started and ended and sends those real timings — see
 * `buildQuestionTimeline` in `app/questionTiming.ts`.
 *
 * V2 will get its timeline from an editor the person fills in afterwards, and
 * until that exists this fixture is what gets sent. Sending an empty list
 * instead would be worse than a placeholder: the request would look valid and
 * come back describing nothing.
 *
 * The timings are consistent with `session.ts`. In particular question 3 is
 * followed by a gap of only 20 seconds, which is why its recovery comes back
 * as null rather than as a number — the fixture and the timeline that would
 * have produced it agree.
 */

import type { QuestionTimelineEntry } from '../types/api'
import { questionBank } from './questionBank'

/** Seconds spent answering, then quiet seconds before the next question. */
const PACING: ReadonlyArray<readonly [number, number]> = [
  [90, 60],
  [100, 60],
  [110, 20],
  [120, 60],
  [80, 60],
  [70, 60],
]

/** The interview starts after the resting period, not at second zero. */
const FIRST_QUESTION_SEC = 240

export const mockQuestionTimeline: QuestionTimelineEntry[] = (() => {
  let cursor = FIRST_QUESTION_SEC
  return questionBank.map((question, index) => {
    const [answerSec, gapSec] = PACING[index] ?? [90, 60]
    const answerStart = cursor
    const answerEnd = answerStart + answerSec
    const gapEnd = answerEnd + gapSec
    cursor = gapEnd
    return {
      number: index + 1,
      text: question.text,
      type: question.type,
      answer_start_sec: answerStart,
      answer_end_sec: answerEnd,
      gap_end_sec: gapEnd,
      is_difficult: question.isDifficult,
    }
  })
})()
