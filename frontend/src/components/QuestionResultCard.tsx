/**
 * QuestionResultCard.tsx — one question's result, as the person sees it.
 *
 * WHAT IS ABSENT IS THE DESIGN. No percentages, no RMSSD, no score, no
 * evidence lines. Those live in the developer panel. A person practising for an
 * interview cannot act on "RMSSD 41% below baseline", and showing it invites
 * them to compare a number against other people's numbers — which is exactly
 * what mandatory rule #2 says this system does not do.
 *
 * TWO THINGS ARE SAID OUT LOUD instead.
 *
 * When recovery could not be measured, the card says so. It does not translate
 * the missing measurement into a phrase like "pulih lambat", and it certainly
 * does not show 0%. The gap was too short to see anything; that is a statement
 * about the recording, not about the person.
 *
 * When the two markers disagree, the card says the reading is less certain.
 * Hiding that would present a shaky result with the same confidence as a firm
 * one.
 */

import { LevelBadge } from './LevelBadge'
import { formatQuestionType } from '../lib/format'
import type { QuestionResult } from '../types/api'

/**
 * The backend's `recovery_note` is a sentence fragment written to follow a
 * colon, so it starts lowercase. Here it follows a full stop instead.
 */
function asSentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function QuestionResultCard({ result }: { result: QuestionResult }) {
  const recoveryUnmeasured = result.recovery_pct === null

  return (
    <div className="rounded-xl border border-hairline bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-canvas text-xs font-semibold text-ink-muted"
          >
            {result.number}
          </span>
          <div>
            <p className="font-semibold text-navy">{result.text}</p>
            <p className="text-xs text-ink-muted">
              {formatQuestionType(result.type)}
            </p>
          </div>
        </div>
        <LevelBadge level={result.level} />
      </div>

      <p className="mt-4 text-sm">{result.penjelasan}</p>

      <p className="mt-3 rounded-lg bg-brand-soft px-4 py-3 text-sm text-navy">
        <span className="font-semibold">Saran: </span>
        {result.saran}
      </p>

      {(recoveryUnmeasured || result.features_disagree) && (
        <ul className="mt-3 space-y-1.5">
          {recoveryUnmeasured && (
            <li className="rounded-lg bg-unknown-bg px-3 py-2 text-xs text-unknown">
              <span className="font-semibold">Pemulihan tidak diukur.</span>{' '}
              {result.recovery_note
                ? asSentence(result.recovery_note)
                : 'Tidak ada jeda yang cukup panjang setelah pertanyaan ini.'}
            </li>
          )}
          {result.features_disagree && (
            <li className="rounded-lg bg-level-moderate-bg px-3 py-2 text-xs text-level-moderate">
              <span className="font-semibold">Pembacaan kurang tegas.</span>{' '}
              Dua tanda tubuh menunjuk arah berbeda di pertanyaan ini, jadi
              hasilnya lebih tidak pasti daripada yang lain.
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
