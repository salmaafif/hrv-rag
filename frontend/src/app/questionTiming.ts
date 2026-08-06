/**
 * questionTiming.ts — turns what happened during the interview into a timeline.
 *
 * V3 knows exactly when each answer began and ended, because it asked the
 * questions. That is real information, computed here rather than guessed, and
 * it is what makes V3's per-question results trustworthy in a way a
 * hand-entered timeline never quite is.
 *
 * THE OFFSET, which is the part that can go wrong.
 *
 * The interview clock starts at zero when the first question appears. The
 * recording's clock started earlier — when the person began recording and sat
 * still for the resting period. So every interview time has to be shifted by
 * the length of that resting period to line up with the recording.
 *
 * This assumes the person did what the start screen asked: start recording,
 * sit quietly for the stated number of minutes, then begin the interview. If
 * they begin the interview early or late, every question lands on the wrong
 * stretch of recording, and nothing downstream can detect it — the numbers
 * would simply describe the wrong moments. That is why the instruction is
 * given prominently rather than in passing.
 */

import type { QuestionTimelineEntry } from '../types/api'
import type { BankQuestion } from '../mocks/questionBank'

export interface AnsweredQuestion {
  question: BankQuestion
  /** Seconds after the interview began, when this question appeared. */
  startedAtSec: number
  /** Seconds after the interview began, when the person moved on. */
  endedAtSec: number
}

export function buildQuestionTimeline(
  answered: AnsweredQuestion[],
  baselineMinutes: number,
): QuestionTimelineEntry[] {
  const offsetSec = Math.round(baselineMinutes * 60)

  return answered.map((entry, index) => {
    const answerStart = offsetSec + Math.round(entry.startedAtSec)
    const answerEnd = offsetSec + Math.round(entry.endedAtSec)
    const next = answered[index + 1]

    // The quiet stretch after an answer runs until the next question appears.
    //
    // For the LAST question there is no next question, and we do not know
    // whether the recording continued. Claiming a gap we did not observe would
    // invent a recovery measurement, so the gap is left at zero: the backend
    // then reports recovery as null — "not measurable" — which is the truth.
    const gapEnd = next ? offsetSec + Math.round(next.startedAtSec) : answerEnd

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
