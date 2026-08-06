/**
 * questionTiming.ts — turns what happened during the session into a timeline.
 *
 * V3 knows exactly when each answer began and ended, because it asked the
 * questions. That is real information, computed here rather than guessed, and
 * it is what makes V3's per-question results trustworthy in a way a
 * hand-entered timeline never quite is.
 *
 * ABOUT THE CLOCK, which used to be the part that could go wrong.
 *
 * Every time here is already measured from the START OF THE RECORDING, not from
 * the first question. `SessionPage` runs one clock beginning the moment the
 * person starts the session, and it runs the resting period ITSELF before
 * showing anything — so the resting minutes are inside the same clock rather
 * than being assumed to have happened beforehand.
 *
 * This file used to add `baselineMinutes * 60` to every timestamp instead. That
 * shift was a guess about the person's own behaviour: it assumed they had sat
 * still for exactly the stated number of minutes before opening the interview.
 * If they started early or late, every question landed on the wrong stretch of
 * recording, and nothing downstream could detect it — the numbers would simply
 * describe the wrong moments, confidently.
 *
 * One assumption remains, and it is much smaller: that the recording on the
 * person's own device began when they pressed the button. The screen asks for
 * exactly that, in that order, and it is a single instant to get right rather
 * than a duration to judge.
 */

import type { QuestionTimelineEntry } from '../types/api'
import type { BankQuestion } from '../mocks/questionBank'

export interface AnsweredQuestion {
  question: BankQuestion
  /** Seconds after the RECORDING began, when this question appeared. */
  startedAtSec: number
  /** Seconds after the RECORDING began, when the person moved on. */
  endedAtSec: number
}

export function buildQuestionTimeline(
  answered: AnsweredQuestion[],
): QuestionTimelineEntry[] {
  return answered.map((entry, index) => {
    const answerStart = Math.round(entry.startedAtSec)
    const answerEnd = Math.round(entry.endedAtSec)
    const next = answered[index + 1]

    // The quiet stretch after an answer runs until the next question appears.
    //
    // For the LAST question there is no next question, and we do not know
    // whether the recording continued. Claiming a gap we did not observe would
    // invent a recovery measurement, so the gap is left at zero: the backend
    // then reports recovery as null — "not measurable" — which is the truth.
    const gapEnd = next ? Math.round(next.startedAtSec) : answerEnd

    return {
      number: index + 1,
      text: entry.question.text,
      type: entry.question.type,
      answer_start_sec: answerStart,
      answer_end_sec: answerEnd,
      gap_end_sec: gapEnd,
      is_difficult: entry.question.isDifficult,
    }
  })
}
