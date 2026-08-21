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
 * KETAHANAN SITS BETWEEN THE TWO, and its position is an argument rather than a
 * layout preference. It is DERIVED from reaction size and recovery speed, so it
 * cannot share a chart with its own components — that was the radar's mistake —
 * and it cannot come before them either, because a conclusion read before its
 * inputs is just an assertion. But it used to sit below the per-question detail,
 * after all the working, where one of the document's three headline outputs read
 * as an afterthought. Now it follows its inputs immediately and precedes the
 * working, and it carries the word "Ketahanan", which did not appear anywhere on
 * this screen before.
 *
 * WHAT IS DELIBERATELY ABSENT. No RMSSD, no percentage change against baseline,
 * no score out of four, no feature name anywhere (decision K4). Those all exist
 * in the response and all stay behind the developer panel. The rule cannot be
 * enforced by the API as it stands — it can only be enforced here, on the screen
 * that renders it, which is why A6 in `docs/ARSITEKTUR_KARIRLINK_HRV.md` moves
 * the enforcement into the response shape before the web team rebuilds this.
 *
 * THE FIRST THING ON SCREEN IS THE `penyemangat` CARD, not the session summary
 * (decision A13, position half). Telling someone that a body's stress spike is
 * a resource rather than a warning sign — reappraisal — is the one part of this
 * screen with experimental evidence it changes what happens next (Jamieson et
 * al.: d = 0.55 on performance, d = 0.53 on evaluation anxiety, effects that
 * held up months later). Nothing else on this screen can make that claim, so it
 * is read before anything else can compete for attention. A13's other half —
 * steering what the LLM actually writes there toward reappraisal framing — is a
 * prompt change, not a layout one, and is tracked separately.
 */

import { Card } from './Card'
import { QuestionResultCard } from './QuestionResultCard'
import { RecoveryBars } from './RecoveryBars'
import { ResilienceQuadrant } from './ResilienceQuadrant'
import { StressTimeline } from './StressTimeline'
import {
  headlines,
  pressureTimeline,
  resilienceCell,
  sessionTrend,
} from '../lib/sessionInsights'
import type { SessionResponse } from '../types/api'

export function SessionResult({ result }: { result: SessionResponse }) {
  const timeline = pressureTimeline(result)
  const stats = headlines(result)
  const cell = resilienceCell(result.summary.resilience)
  const trend = sessionTrend(result)

  return (
    <>
      <Card>
        <p className="text-sm text-navy">{result.narrative.penyemangat}</p>
      </Card>

      <Card eyebrow="Ringkasan sesi kamu">
        <p className="text-lg font-semibold text-navy">
          {result.narrative.ringkasan_sesi}
        </p>
      </Card>

      <div className="space-y-2 rounded-lg bg-unknown-bg px-4 py-3 text-xs text-unknown">
        {/*
          Decision A14. A CHI 2021 study of 17 stress-tracker wearable users
          found the main reason people stopped wearing them was not accuracy
          — it was a mismatch between how they understand stress
          (psychologically) and how the device measures it (physiologically).
          One sentence here says that mismatch is expected, before the reader
          hits any number that might surprise them.
        */}
        <p>
          Kalau ini terasa tidak cocok dengan yang kamu rasakan, itu wajar —
          alat ini membaca reaksi tubuh, yang tidak selalu sama dengan
          perasaan.
        </p>
        {/*
          Decision A16. HRV touches one of MASI's five dimensions of interview
          anxiety (Communication, Appearance, Social, Performance,
          Behavioral/autonomic). Without this line the screen can be read as
          measuring "interview anxiety" whole, which it does not, and tension
          here can be misread as a forecast of a poor interview.
        */}
        <p>
          Alat ini cuma membaca satu dari beberapa sisi kecemasan wawancara —
          reaksi tubuhmu. Tegang di sini tidak berarti tampilmu buruk.
        </p>
      </div>

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

      <Card title="Naik-turun sepanjang sesi">
        <StressTimeline points={timeline} />
        {/*
          The direction the session took, in one sentence, under the picture that
          already shows it. It used to be a third radar axis scaled 0-100 with 50
          meaning "no change" — a midpoint that reads as a mediocre score on a
          chart where every other midpoint meant "half".
        */}
        {trend && <p className="mt-4 text-sm text-ink-muted">{trend}</p>}
      </Card>

      <Card title="Ketahanan">
        <p className="mb-5 text-sm text-ink-muted">
          Besar reaksi tubuhmu, dan seberapa cepat ia kembali tenang.
        </p>
        <ResilienceQuadrant cell={cell} />
        {cell === null && (
          <p className="mt-4 rounded-lg bg-unknown-bg px-4 py-3 text-xs text-unknown">
            Pemulihanmu belum terukur, jadi polanya belum bisa disimpulkan.
          </p>
        )}
      </Card>

      <Card title="Balik tenang setelah tiap pertanyaan">
        <RecoveryBars questions={result.questions} />
      </Card>

      {/*
        "Yang paling bikin tegang" used to be repeated here, in a card below the
        per-question list, having already been the first of the three figures at
        the top. One fact, twice, several screens apart.
      */}
      <Card title="Rincian per pertanyaan">
        <ul className="space-y-3">
          {result.questions.map((question) => (
            <QuestionResultCard key={question.number} result={question} />
          ))}
        </ul>
      </Card>
    </>
  )
}
