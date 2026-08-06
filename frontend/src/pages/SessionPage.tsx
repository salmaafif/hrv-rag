/**
 * SessionPage.tsx — stage 2 of V3: the interview itself, running here.
 *
 * Only V3 reaches this screen. In V2 the person supplies the question timeline
 * afterwards; in V1 there is no timeline at all.
 *
 * WHAT THIS SCREEN IS ACTUALLY FOR. It looks like a question display, but its
 * real job is recording when each answer started and ended. Those timings are
 * what let the backend judge each question against the right stretch of heart
 * data — and they are the one thing V3 knows that V2 can only be told.
 *
 * WHAT IT DELIBERATELY DOES NOT SHOW. The Figma frame paired the live heart
 * rate with a "mulai tegang" badge. That badge is gone. Telling someone
 * mid-answer that they are getting tense changes how tense they are, which
 * would leave the measurement partly caused by the screen reporting it. The
 * bare number stays, because it is the only evidence the sensor is still
 * reading — and it is absent entirely when nothing is connected, rather than
 * being faked.
 */

import { useEffect, useRef, useState } from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import { buildQuestionTimeline, type AnsweredQuestion } from '../app/questionTiming'
import { questionBank } from '../mocks/questionBank'
import { formatClock } from '../lib/format'
import type { StageContext } from '../app/stageContext'

export function SessionPage({ mode, device, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()
  const [current, setCurrent] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const answeredRef = useRef<AnsweredQuestion[]>([])
  const questionStartRef = useRef(0)
  const finishedRef = useRef(false)

  // One clock for the whole interview, started when this screen mounts. Each
  // question's times are read from it, so they cannot drift apart the way
  // separate per-question timers would.
  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000))
    }, 250)
    return () => window.clearInterval(timer)
  }, [])

  if (!mode.runsInterview) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  const question = questionBank[current]!
  const isLast = current === questionBank.length - 1
  const sinceQuestion = Math.max(0, elapsed - questionStartRef.current)

  const advance = () => {
    if (finishedRef.current) return

    answeredRef.current.push({
      question,
      startedAtSec: questionStartRef.current,
      endedAtSec: elapsed,
    })

    if (!isLast) {
      questionStartRef.current = elapsed
      setCurrent((index) => index + 1)
      return
    }

    finishedRef.current = true
    session.setQuestionTimeline(
      buildQuestionTimeline(answeredRef.current, session.baselineMinutes),
    )
    // With a sensor connected the recording is already in hand, so the analysis
    // can start. Without one, the recording lives on the person's own device
    // and has to be uploaded before there is anything to analyse.
    navigate(`/${mode.id}/${device.connected ? 'proses' : 'unggah'}`)
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <Card>
        <div className="flex items-center justify-between">
          <p className="text-sm text-ink-muted">
            Pertanyaan {current + 1} dari {questionBank.length}
          </p>
          <span className="rounded-full bg-level-high-bg px-3 py-1 text-sm font-semibold text-level-high">
            {formatClock(sinceQuestion)}
          </span>
        </div>

        <h2 className="mt-4 text-3xl font-bold tracking-tight text-navy">
          {question.text}
        </h2>

        <ol className="mt-6 flex flex-wrap gap-2" aria-label="Kemajuan pertanyaan">
          {questionBank.map((entry, index) => {
            const isDone = index < current
            const isCurrent = index === current
            return (
              <li
                key={entry.text}
                aria-current={isCurrent ? 'step' : undefined}
                className={
                  'flex h-10 w-10 items-center justify-center rounded-full border text-sm font-semibold ' +
                  (isCurrent
                    ? 'border-amber text-navy'
                    : isDone
                      ? 'border-navy bg-navy text-white'
                      : 'border-hairline text-ink-muted')
                }
              >
                {index + 1}
                <span className="sr-only">
                  {isCurrent ? ' (sedang ditanyakan)' : isDone ? ' (selesai)' : ''}
                </span>
              </li>
            )
          })}
        </ol>

        <div className="mt-8 flex justify-end gap-3">
          <Button variant="outline" onClick={advance}>
            Lewati
          </Button>
          <Button onClick={advance}>
            {isLast ? 'Selesai' : 'Lanjut'}
          </Button>
        </div>
      </Card>

      <div className="space-y-6">
        <Card>
          <p className="mb-2 text-xs font-semibold tracking-wider text-amber uppercase">
            Tips
          </p>
          <p className="rounded-xl bg-amber-soft p-4 text-sm text-level-moderate">
            {question.tip}
          </p>
        </Card>

        <Card title="Detak jantung">
          {device.bpm !== null ? (
            <p className="text-navy">
              <span className="text-4xl font-bold">{device.bpm}</span>
              <span className="ml-1 text-sm font-semibold text-ink-muted">bpm</span>
            </p>
          ) : (
            <p className="text-sm text-ink-muted">
              Tidak ada perangkat tersambung. Rekam detak jantungmu dengan alat
              sendiri, lalu unggah berkasnya setelah sesi ini selesai.
            </p>
          )}
        </Card>

        <Card title="Waktu sesi">
          <p className="text-2xl font-semibold text-navy">
            {formatClock(elapsed)}
          </p>
          <p className="mt-1 text-sm text-ink-muted">
            Dihitung sejak pertanyaan pertama muncul.
          </p>
        </Card>
      </div>
    </div>
  )
}
