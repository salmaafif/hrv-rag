/**
 * CandidateCheckIn.tsx — one question back to the candidate (decision A15,
 * docs/ARSITEKTUR_KARIRLINK_HRV.md §4).
 *
 * Assessment feedback only helps performance when it is personal and involves
 * the recipient (d = 0.42) — a one-way readout does not. "Ini cocok tidak
 * dengan yang kamu rasakan tadi?" does two things at once: it makes the
 * screen personal instead of a report handed down, and in a product with
 * somewhere to put the answer it would harvest a subjective label worth
 * validating the rule against.
 *
 * CAPTURE-ONLY, NOT YET PERSISTED. The answer lives in this component's own
 * state and goes nowhere else — it is lost the moment this screen unmounts.
 * `backend/hrv_api/` is stateless HTTP with no database, and deciding where a
 * real product would store a candidate's subjective label is a stack
 * decision on its own, not something to fold quietly into a UI change. This
 * comment is the marker for that follow-up; do not read the thank-you
 * message below as confirmation that anything was saved.
 */

import { useState } from 'react'
import { Card } from './Card'

type CheckInAnswer = 'cocok' | 'sebagian' | 'tidak_cocok'

const OPTIONS: { value: CheckInAnswer; label: string }[] = [
  { value: 'cocok', label: 'Cocok' },
  { value: 'sebagian', label: 'Sebagian cocok' },
  { value: 'tidak_cocok', label: 'Tidak cocok' },
]

export function CandidateCheckIn() {
  const [answer, setAnswer] = useState<CheckInAnswer | null>(null)

  return (
    <Card>
      <p className="text-sm font-semibold text-navy">
        Ini cocok tidak dengan yang kamu rasakan tadi?
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setAnswer(option.value)}
            aria-pressed={answer === option.value}
            className={
              'rounded-full border px-4 py-2 text-sm font-medium transition-colors ' +
              (answer === option.value
                ? 'border-brand bg-brand-soft text-navy'
                : 'border-hairline bg-surface text-ink-muted hover:bg-canvas')
            }
          >
            {option.label}
          </button>
        ))}
      </div>
      {answer && (
        <p className="mt-3 text-xs text-ink-muted">
          Makasih sudah kasih tahu.
        </p>
      )}
    </Card>
  )
}
