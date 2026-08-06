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
 * IT RUNS THE RESTING PERIOD TOO, before the first question. That is not a
 * courtesy countdown. Reactivity is defined against the person's own resting
 * baseline (Mandatory Rule #2), so those minutes are the reference every later
 * number is divided by — and the app used to merely ASSUME they had happened,
 * off-screen, for the stated duration, before the interview was opened. Someone
 * who sat still for one minute instead of four, or who opened the interview and
 * then wandered off, produced a timeline that pointed at the wrong stretch of
 * recording, and nothing downstream could tell. Running the clock here makes the
 * duration a fact rather than a hope, and it means every timestamp this screen
 * produces is already measured from the start of the recording.
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
import { useDevMode } from '../app/useDevMode'
import { INTERVIEW_REST_MINUTES } from '../app/useSessionState'
import { questionBank } from '../mocks/questionBank'
import { formatClock } from '../lib/format'
import type { StageContext } from '../app/stageContext'

export function SessionPage({ mode, device, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()
  const [devMode] = useDevMode()
  const [current, setCurrent] = useState(0)
  const [ticks, setTicks] = useState(0)
  const [skippedSec, setSkippedSec] = useState(0)
  const answeredRef = useRef<AnsweredQuestion[]>([])
  const finishedRef = useRef(false)

  // V3's resting period is fixed, so this screen reads the constant rather than
  // whatever `baselineMinutes` happens to hold. Setting it from the start screen's
  // button looked equivalent and was not: opening /v3/sesi directly, or simply
  // reloading it, skips the click and left the countdown on the V1/V2 default —
  // four minutes of waiting while the backend was told two.
  const restSec = INTERVIEW_REST_MINUTES * 60
  const setBaselineMinutes = session.setBaselineMinutes

  // The same number has to reach the backend, because it is what marks where the
  // baseline ends in the recording. Written on mount so no entry path can miss it.
  useEffect(() => {
    setBaselineMinutes(INTERVIEW_REST_MINUTES)
  }, [setBaselineMinutes])

  // The first question opens the moment the resting period ends, so its start
  // time is known before the screen has even rendered. A ref rather than state
  // because reading it must never lag a render behind the clock.
  const questionStartRef = useRef(restSec)

  // ONE clock for everything — resting period and interview alike — started when
  // this screen mounts, which is when the person was asked to start recording.
  // Every time it produces is therefore already in the recording's own
  // coordinates, and `buildQuestionTimeline` has nothing left to guess at.
  //
  // Separate timers per phase, or per question, would each drift a little and
  // the errors would accumulate across a fifteen-minute session.
  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setTicks(Math.floor((Date.now() - startedAt) / 1000))
    }, 250)
    return () => window.clearInterval(timer)
  }, [])

  if (!mode.runsInterview) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  const elapsed = ticks + skippedSec
  const restRemaining = restSec - elapsed
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
    session.setQuestionTimeline(buildQuestionTimeline(answeredRef.current))
    // The test is `wornAt`, not `connected`. A sensor whose name we could not
    // place leaves the wear location unknown, so the modality is unknown too and
    // there is nothing analysable — even though a device is plugged in.
    //
    // Routing on `connected` alone sent those people to the processing screen,
    // which bounced them straight back to the V3 start screen. That screen has no
    // file upload, so their only way forward was to answer the wear-location
    // question and press "Mulai sesi latihan" — restarting the whole interview
    // from question 1 and discarding the timeline they had just recorded.
    const ready = device.connected !== null && device.wornAt !== null
    navigate(`/${mode.id}/${ready ? 'proses' : 'unggah'}`)
  }

  // The resting period. No question is shown, and none can be reached early —
  // the interview opens on the clock, not on a button. A "saya siap" button
  // would hand the duration back to the person, which is the very thing this
  // phase exists to take out of their hands.
  const restingPanel = (
    <Card>
      <p className="text-sm font-semibold tracking-wider text-amber uppercase">
        Periode tenang
      </p>
      <p
        className="mt-4 text-6xl font-bold tabular-nums tracking-tight text-navy"
        role="timer"
        aria-live="off"
      >
        {formatClock(Math.max(0, restRemaining))}
      </p>
      <p className="mt-5 text-sm text-ink-muted">
        Duduk diam dan bernapas seperti biasa. Menit-menit ini jadi pembanding
        untuk seluruh sesi, jadi semakin tenang bagian ini, semakin bermakna
        hasilnya. Pertanyaan pertama muncul sendiri saat waktunya habis — tidak
        perlu menekan apa pun.
      </p>
      <p className="mt-4 rounded-xl bg-canvas p-4 text-sm text-ink-muted">
        Pastikan perekaman di alatmu sudah berjalan sejak tadi. Kalau belum,
        mulai sekarang dan ulangi sesi ini dari awal — periode tenang yang tidak
        ikut terekam tidak bisa diperbaiki setelahnya.
      </p>

      {devMode && (
        <div className="mt-6 border-t border-hairline pt-4">
          <Button
            variant="outline"
            onClick={() => setSkippedSec(Math.max(0, restRemaining))}
          >
            Lewati periode tenang (mode pengembang)
          </Button>
          <p className="mt-2 text-xs text-ink-muted">
            Memajukan jam sesi seolah periode tenang sudah selesai. Untuk
            memeriksa tampilan saja — rekaman sungguhan tidak akan punya menit
            tenang ini, sehingga hasilnya kehilangan acuan.
          </p>
        </div>
      )}
    </Card>
  )

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      {restRemaining > 0 ? restingPanel : (
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
      )}

      <div className="space-y-6">
        {restRemaining <= 0 && (
          <Card>
            <p className="mb-2 text-xs font-semibold tracking-wider text-amber uppercase">
              Tips
            </p>
            <p className="rounded-xl bg-amber-soft p-4 text-sm text-level-moderate">
              {question.tip}
            </p>
          </Card>
        )}

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
            Dihitung sejak sesi dimulai, termasuk periode tenang — supaya cocok
            dengan jam rekamanmu.
          </p>
        </Card>
      </div>
    </div>
  )
}
