/**
 * RecoveryBars.tsx — how quickly the pressure eased after each question.
 *
 * "NOT MEASURED" IS DRAWN DIFFERENTLY FROM ZERO, and that distinction is the
 * reason this component exists rather than another column in a table. Zero
 * means the person did not settle at all; null means the pause after that
 * question was too short to tell. Rendering the second as an empty bar states
 * the first, about somebody it was never measured on — which is why the API
 * keeps the two apart all the way from `features/dynamics.py`, and why throwing
 * the difference away at the last step would waste the care taken everywhere
 * before it.
 */

import type { QuestionResult } from '../types/api'

export function RecoveryBars({ questions }: { questions: QuestionResult[] }) {
  return (
    <ul className="space-y-3">
      {questions.map((question) => {
        const measured = question.recovery_pct !== null
        const width = measured
          ? Math.max(0, Math.min(100, question.recovery_pct!))
          : 0

        return (
          <li key={question.number}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="text-navy">
                <span className="font-semibold">{question.number}.</span>{' '}
                <span className="text-ink-muted">{question.text}</span>
              </span>
              <span
                className={
                  'shrink-0 text-xs font-semibold ' +
                  (measured ? 'text-navy' : 'text-unknown')
                }
              >
                {measured ? `turun ${Math.round(width)}%` : 'belum terukur'}
              </span>
            </div>

            {measured ? (
              <div className="mt-1.5 h-2 rounded-full bg-canvas">
                <div
                  className="h-2 rounded-full bg-level-low"
                  style={{ width: `${width}%` }}
                />
              </div>
            ) : (
              // A dashed outline rather than an empty track: an empty track is
              // a bar at zero, and zero is a claim nobody measured.
              <div className="mt-1.5 h-2 rounded-full border border-dashed border-hairline" />
            )}
          </li>
        )
      })}

      {questions.every((question) => question.recovery_pct === null) && (
        <li className="rounded-lg bg-unknown-bg px-4 py-3 text-xs text-unknown">
          Jeda antar pertanyaanmu kependekan buat mengukur pemulihan. Bukan
          berarti kamu tidak pulih.
        </li>
      )}
    </ul>
  )
}
