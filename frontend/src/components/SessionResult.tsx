/**
 * SessionResult.tsx — the per-question result screen, for V2 and V3.
 *
 * Order matters here. The session summary comes first because it is the answer
 * to the question the person actually asked — "how did I do?" — and the
 * per-question detail follows as the working behind it. The overall pattern and
 * the encouragement come last, so the screen does not open on a verdict.
 */

import { Card } from './Card'
import { QuestionResultCard } from './QuestionResultCard'
import { formatResilience } from '../lib/format'
import type { SessionResponse } from '../types/api'

export function SessionResult({ result }: { result: SessionResponse }) {
  const triggering = result.questions.find(
    (question) => question.number === result.summary.most_triggering_question,
  )

  return (
    <>
      <Card eyebrow="Ringkasan sesi kamu">
        <p className="text-lg font-semibold text-navy">
          {result.narrative.ringkasan_sesi}
        </p>
      </Card>

      <Card title="Tekanan per pertanyaan">
        <ul className="space-y-3">
          {result.questions.map((question) => (
            <QuestionResultCard key={question.number} result={question} />
          ))}
        </ul>
      </Card>

      <Card title="Pola keseluruhan">
        <dl className="space-y-3 text-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-canvas px-4 py-3">
            <dt className="text-ink-muted">Ukuran reaksi dan pemulihan</dt>
            <dd className="font-semibold text-navy">
              {formatResilience(result.summary.resilience)}
            </dd>
          </div>

          <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-canvas px-4 py-3">
            <dt className="text-ink-muted">Pertanyaan paling memicu</dt>
            <dd className="font-semibold text-navy">
              {triggering
                ? `${triggering.number}. ${triggering.text}`
                : 'Belum dapat ditentukan'}
            </dd>
          </div>
        </dl>

        {result.summary.resilience === null && (
          <p className="mt-3 rounded-lg bg-unknown-bg px-4 py-3 text-xs text-unknown">
            Pola ini butuh dua hal: seberapa besar reaksinya dan seberapa cepat
            mereda. Karena tidak ada jeda yang cukup panjang untuk mengukur
            pemulihan, polanya belum bisa disimpulkan — dan menebaknya akan
            membuat kesimpulan terlihat lebih pasti daripada datanya.
          </p>
        )}
      </Card>

      <Card>
        <p className="text-sm text-navy">{result.narrative.penyemangat}</p>
      </Card>
    </>
  )
}
