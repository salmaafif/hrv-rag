/**
 * QuestionSlider.tsx — one question's result at a time, not six stacked.
 *
 * The per-question detail is the working behind the summary, not the summary
 * itself (see the reading-order note in `SessionResult.tsx`). Somebody who
 * already has the headline three figures does not need to scroll past six
 * full verdicts to get to "practice again" — they need to be able to check
 * one question, then the next, at their own pace. A slider says that; a
 * stacked list says "read all of this now."
 *
 * The dots double as both a position indicator and a jump target, so the
 * six-question case (fixed by the interview script) never needs more than
 * one row.
 */

import { useState } from 'react'
import { QuestionResultCard } from './QuestionResultCard'
import type { QuestionResult } from '../types/api'

function NavButton({
  direction,
  onClick,
  disabled,
  label,
}: {
  direction: 'prev' | 'next'
  onClick: () => void
  disabled: boolean
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-full ' +
        'border border-hairline bg-surface text-navy transition-colors ' +
        'hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40'
      }
    >
      {direction === 'prev' ? '‹' : '›'}
    </button>
  )
}

export function QuestionSlider({
  questions,
}: {
  questions: QuestionResult[]
}) {
  const [index, setIndex] = useState(0)
  const current = questions[index]!

  return (
    <div>
      <QuestionResultCard result={current} />

      <div className="mt-4 flex items-center justify-center gap-4">
        <NavButton
          direction="prev"
          onClick={() => setIndex((i) => i - 1)}
          disabled={index === 0}
          label="Pertanyaan sebelumnya"
        />

        <div className="flex items-center gap-2" role="group" aria-label="Pilih pertanyaan">
          {questions.map((question, i) => (
            <button
              key={question.number}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Ke pertanyaan ${question.number}`}
              aria-current={i === index}
              className={
                'h-2 rounded-full transition-all ' +
                (i === index
                  ? 'w-6 bg-navy'
                  : 'w-2 bg-hairline hover:bg-ink-muted')
              }
            />
          ))}
        </div>

        <NavButton
          direction="next"
          onClick={() => setIndex((i) => i + 1)}
          disabled={index === questions.length - 1}
          label="Pertanyaan berikutnya"
        />
      </div>
    </div>
  )
}
