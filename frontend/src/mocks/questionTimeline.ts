/**
 * questionTimeline.ts — a stand-in question timeline.
 *
 * V2 gets this from an editor the person fills in, and V3 from the interview
 * the app runs itself. Neither exists yet, so until they do this fixture is
 * what gets sent to the session endpoint. Sending an empty list instead would
 * be worse than a placeholder: the request would look valid and come back
 * describing nothing.
 *
 * The timings are consistent with `session.ts`. In particular question 3 is
 * followed by a gap of only 20 seconds, which is why its recovery comes back
 * as null rather than as a number — the fixture and the timeline that would
 * have produced it agree.
 */

import type { QuestionTimelineEntry, QuestionType } from '../types/api'

interface Seed {
  text: string
  type: QuestionType
  /** Seconds spent answering. */
  answerSec: number
  /** Quiet seconds before the next question. Recovery is measured here. */
  gapSec: number
  isDifficult: boolean
}

const SEEDS: Seed[] = [
  { text: 'Ceritakan tentang dirimu', type: 'introduction', answerSec: 90, gapSec: 60, isDifficult: false },
  { text: 'Kenapa kami harus memilihmu?', type: 'behavioural', answerSec: 100, gapSec: 60, isDifficult: false },
  { text: 'Sebutkan kekuranganmu', type: 'behavioural', answerSec: 110, gapSec: 20, isDifficult: true },
  { text: 'Ceritakan konflik di tim dan cara mengatasinya', type: 'situational', answerSec: 120, gapSec: 60, isDifficult: true },
  { text: 'Berapa ekspektasi gajimu?', type: 'numerical', answerSec: 80, gapSec: 60, isDifficult: true },
  { text: 'Ada pertanyaan untuk kami?', type: 'introduction', answerSec: 70, gapSec: 60, isDifficult: false },
]

/** The interview starts after the resting period, not at second zero. */
const FIRST_QUESTION_SEC = 240

export const mockQuestionTimeline: QuestionTimelineEntry[] = (() => {
  let cursor = FIRST_QUESTION_SEC
  return SEEDS.map((seed, index) => {
    const answerStart = cursor
    const answerEnd = answerStart + seed.answerSec
    const gapEnd = answerEnd + seed.gapSec
    cursor = gapEnd
    return {
      number: index + 1,
      text: seed.text,
      type: seed.type,
      answer_start_sec: answerStart,
      answer_end_sec: answerEnd,
      gap_end_sec: gapEnd,
      is_difficult: seed.isDifficult,
    }
  })
})()
