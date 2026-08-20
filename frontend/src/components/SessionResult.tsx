/**
 * SessionResult.tsx — the per-question dashboard, for V2 and V3.
 *
 * READING ORDER IS THE DESIGN. Somebody who just finished an interview wants
 * one thing first: how did that go. So the sentence answering it comes before
 * any chart, the three figures they can act on come next, and the picture of
 * the shape follows. The per-question detail sits last, because it is the
 * working behind the answer rather than the answer — and because scrolling
 * straight into six verdicts is a bad way to be told anything.
 *
 * WHAT IS DELIBERATELY ABSENT. No RMSSD, no percentage change against baseline,
 * no score out of four, no feature name anywhere (decision K4). Those all exist
 * in the response and all stay behind the developer panel. The rule cannot be
 * enforced by the API — it can only be enforced here, on the screen that
 * renders it.
 */

import { Card } from './Card'
import { QuestionResultCard } from './QuestionResultCard'
import { RecoveryBars } from './RecoveryBars'
import { ResponseRadar } from './ResponseRadar'
import { StressTimeline } from './StressTimeline'
import { formatResilience } from '../lib/format'
import {
  headlines,
  pressureTimeline,
  responseDimensions,
} from '../lib/sessionInsights'
import type { SessionResponse } from '../types/api'

export function SessionResult({ result }: { result: SessionResponse }) {
  const triggering = result.questions.find(
    (question) => question.number === result.summary.most_triggering_question,
  )
  const dimensions = responseDimensions(result)
  const timeline = pressureTimeline(result)
  const stats = headlines(result)

  return (
    <>
      <Card eyebrow="Ringkasan sesi kamu">
        <p className="text-lg font-semibold text-navy">
          {result.narrative.ringkasan_sesi}
        </p>
      </Card>

      {/* The three figures somebody can act on tomorrow. */}
      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label} className="p-5!">
            <p className="text-xs font-semibold tracking-wider text-ink-muted uppercase">
              {stat.label}
            </p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-navy">
              {stat.value}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">
              {stat.hint}
            </p>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Gambaran sesi kamu">
          <ResponseRadar dimensions={dimensions} />
        </Card>

        <Card title="Naik-turun sepanjang sesi">
          <StressTimeline points={timeline} />
        </Card>
      </div>

      <Card title="Balik tenang setelah tiap pertanyaan">
        <RecoveryBars questions={result.questions} />
      </Card>

      <Card title="Rincian per pertanyaan">
        <ul className="space-y-3">
          {result.questions.map((question) => (
            <QuestionResultCard key={question.number} result={question} />
          ))}
        </ul>
      </Card>

      <Card title="Pola keseluruhan">
        <dl className="space-y-3 text-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-canvas px-4 py-3">
            <dt className="text-ink-muted">Besar reaksi dan kecepatan pulih</dt>
            <dd className="font-semibold text-navy">
              {formatResilience(result.summary.resilience)}
            </dd>
          </div>

          <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-canvas px-4 py-3">
            <dt className="text-ink-muted">Yang paling bikin tegang</dt>
            <dd className="font-semibold text-navy">
              {triggering
                ? `${triggering.number}. ${triggering.text}`
                : 'Belum kelihatan'}
            </dd>
          </div>
        </dl>

        {result.summary.resilience === null && (
          <p className="mt-3 rounded-lg bg-unknown-bg px-4 py-3 text-xs text-unknown">
            Pemulihanmu belum terukur, jadi polanya belum bisa disimpulkan.
          </p>
        )}
      </Card>

      <Card>
        <p className="text-sm text-navy">{result.narrative.penyemangat}</p>
      </Card>
    </>
  )
}
