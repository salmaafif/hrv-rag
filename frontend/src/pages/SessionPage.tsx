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
 * THIS SCREEN IS PART OF THE INSTRUMENT, so its own text is a source of error.
 * Every paragraph a person reads while being measured is cognitive load, load
 * raises arousal, and arousal is the quantity under measurement. That is the
 * reason for each of the following, and the reason none of them should be
 * reinstated without a better one:
 *
 *   NO PER-QUESTION STOPWATCH. There used to be a counter here in
 *   `bg-level-high-bg / text-level-high` — the exact pair `LevelBadge` uses for
 *   "Tinggi". A rising number in the stress colour, beside the question, for the
 *   whole answer. The Figma "mulai tegang" badge was cut for precisely this
 *   argument; the timer survived it only because nobody noticed it was the same
 *   thing with a clock attached. A quiet bar fills instead: it says the same
 *   thing about progress and says nothing about the person.
 *
 *   LIVE PULSE TRACE, UNDER GUARDRAILS (owner's decision, 26 Aug 2026 —
 *   revisits the earlier "no live bpm" rule). The trace exists because a
 *   person mid-interview needs evidence the sensor is alive, and after the
 *   first real pilot the owner judged a visible stream worth having. What made
 *   the original rule right is kept as constraints on HOW it draws, in
 *   `lib/heartStream.ts`: one neutral colour, no zones, no thresholds, no
 *   words about stress, and a FIXED y-scale — auto-fit would magnify a calm
 *   trace into drama, and the feedback loop the old rule feared comes from the
 *   interpretation, not from the number.
 *
 *   NO SEGMENT LENGTH ON SCREEN. The 60-second window is real and the button
 *   still waits for it, but the wait is now phrased as interview advice — take
 *   your time, answer fully — which is true regardless of the sensor. Naming the
 *   window taught people to stretch answers to satisfy the instrument, which
 *   quietly damages the recording it was meant to protect.
 *
 * The wording rule the rest of the screen follows: a sentence earns its place
 * only if it changes what the person does in the next ten seconds. Why the
 * system works this way belongs in `docs/`, not here.
 */

import { useEffect, useRef, useState } from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { HeartRateStream } from '../components/HeartRateStream'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import { buildQuestionTimeline, sessionElapsedSec,
         type AnsweredQuestion } from '../app/questionTiming'
import { useDevMode } from '../app/useDevMode'
import { INTERVIEW_REST_MINUTES } from '../app/useSessionState'

import { questionBank } from '../mocks/questionBank'
import { formatClock } from '../lib/format'
import type { StageContext } from '../app/stageContext'

/**
 * Seconds a question must run before it can be measured at all.
 *
 * The segment length the whole pipeline is built on: features are computed
 * over 60-second windows, so a shorter answer produces no segment rather than
 * a noisier one. Mirrors `SegmentationConfig.window_sec` on the Python side.
 */
const SEGMENT_SEC = 60

/**
 * How long the "is your recorder running?" reminder stays up.
 *
 * It is only actionable at the very beginning — noticing at second 5 that
 * nothing is recording is worth a restart, noticing at second 90 is not. Left
 * up for the whole resting period it stopped being a reminder and became two
 * minutes of being told the session might be wasted, during the one phase whose
 * entire purpose is that the person is calm.
 */
const RECORDER_REMINDER_SEC = 15

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
  const markSessionStart = session.markSessionStart

  // The same number has to reach the backend, because it is what marks where the
  // baseline ends in the recording. Written on mount so no entry path can miss it.
  useEffect(() => {
    setBaselineMinutes(INTERVIEW_REST_MINUTES)
    // The sensor has been streaming since it paired; this is the moment the
    // session clock starts, so this is where the distance between them is fixed.
    markSessionStart()
    // Deliberately mount-only: re-running it later would move the origin after
    // timestamps had already been recorded against the old one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
  // `sessionElapsedSec` rather than plain arithmetic: in dev mode the simulated
  // sensor plays its recording back faster than life, and this clock stamps
  // positions INSIDE that recording. The scaling rule lives beside the timeline
  // builder so a test can hold it — see the note there. Real sensors run at 1x.
  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setTicks(sessionElapsedSec(Date.now() - startedAt, devMode))
    }, 250)
    return () => window.clearInterval(timer)
  }, [devMode])

  if (!mode.runsInterview) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  const elapsed = ticks + skippedSec
  const restRemaining = restSec - elapsed
  const question = questionBank[current]!
  const isLast = current === questionBank.length - 1
  const sinceQuestion = Math.max(0, elapsed - questionStartRef.current)
  const answerProgress = Math.min(100, (sinceQuestion / SEGMENT_SEC) * 100)
  const canAdvance = sinceQuestion >= SEGMENT_SEC

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
        Duduk diam, bernapas seperti biasa. Pertanyaan pertama muncul sendiri.
      </p>

      {elapsed < RECORDER_REMINDER_SEC && (
        <p className="mt-4 rounded-xl bg-canvas p-4 text-sm text-ink-muted">
          Perekaman di alatmu sudah jalan?
        </p>
      )}

      {devMode && device.connected === null && (
        <div className="mt-6 border-t border-hairline pt-4">
          {/*
            SKIPPING IS OFFERED ONLY WHEN NOTHING IS RECORDING.

            The button moves the session clock and cannot move the beats with it —
            nothing here can, the sensor produces them at its own pace. With a
            device attached that desynchronises the two clocks completely: the
            timeline claims a question was answered at second 130 while the
            recording holds eight seconds of beats, and the backend rejects the
            whole session with "only N intervals found". Which is what happened,
            repeatedly, and looked like a broken server rather than a button doing
            exactly what it said.
          */}
          <Button
            variant="outline"
            onClick={() => setSkippedSec(Math.max(0, restRemaining))}
          >
            Lewati periode tenang
          </Button>
          <p className="mt-2 text-xs text-ink-muted">
            Mode pengembang. Rekamannya tidak ikut maju, jadi sesi ini tidak bisa
            dianalisis.
          </p>
        </div>
      )}

      {devMode && device.connected !== null && (
        <p className="mt-6 border-t border-hairline pt-4 text-xs text-ink-muted">
          Mode pengembang: sensor simulasi berjalan 10× lebih cepat.
        </p>
      )}
    </Card>
  )

  // The one warning allowed to be loud mid-session. Every other rule on this
  // screen keeps feedback about the PERSON off it; this is feedback about the
  // INSTRUMENT, and staying quiet is what turned the third pilot session into
  // fifteen wasted minutes: another app took the sensor, the badge stayed
  // green, and nothing said so until analysis failed.
  const stalled = device.connected !== null && device.streamStalled

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      {stalled && (
        <div className="rounded-xl border border-level-high/40 bg-level-high-bg p-4 xl:col-span-2"
             role="alert">
          <p className="text-sm font-semibold text-level-high">
            Denyut berhenti masuk
          </p>
          <p className="mt-1 text-sm text-level-high">
            Sensormu masih terdaftar, tapi datanya tidak mengalir. Biasanya ada
            aplikasi lain yang mengambil sambungannya — tutup aplikasi itu, atau
            lepas-pasang sensornya. Menit-menit tanpa denyut tidak bisa dinilai.
          </p>
        </div>
      )}
      {restRemaining > 0 ? restingPanel : (
      <Card>
        <h2 className="text-3xl font-bold tracking-tight text-navy">
          {question.text}
        </h2>

        {/*
          The dots are the only place the question number is stated. It used to be
          said three times over — "Pertanyaan 3 dari 6", then the dot row, then the
          filled dot — which is one fact in three encodings and two of them noise.
        */}
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

        {/*
          A QUESTION ANSWERED IN TEN SECONDS CANNOT BE MEASURED AT ALL — every HRV
          feature needs a 60-second window, so a shorter answer yields no segment
          rather than a weaker one, and six of them yield a session the backend
          rejects outright.

          The bar carries that constraint without naming it. Naming it produced
          people talking to a stopwatch instead of to the question, which is a
          worse recording than the one the rule was protecting. `aria-hidden`
          because the sentence below already says the same thing in words, and a
          screen reader announcing a percentage every 250 ms is its own problem.
        */}
        <div
          aria-hidden="true"
          className="mt-8 h-1 w-full overflow-hidden rounded-full bg-canvas"
        >
          <div
            className={
              'h-full rounded-full transition-[width] duration-500 ease-linear ' +
              (canAdvance ? 'bg-level-low' : 'bg-hairline')
            }
            style={{ width: `${answerProgress}%` }}
          />
        </div>

        <div className="mt-5 flex items-center justify-between gap-4">
          <p id="answer-hint" className="text-sm text-ink-muted">
            {canAdvance ? 'Sudah cukup. Lanjut kalau kamu siap.'
                        : 'Ambil waktumu, jawab selengkapnya.'}
          </p>
          <div className="flex shrink-0 gap-3">
            <Button variant="outline" onClick={advance}>
              Lewati
            </Button>
            <Button
              onClick={advance}
              disabled={!canAdvance}
              aria-describedby="answer-hint"
            >
              {isLast ? 'Selesai' : 'Lanjut'}
            </Button>
          </div>
        </div>
      </Card>
      )}

      <div className="space-y-6">
        {restRemaining <= 0 && (
          <Card>
            <p className="rounded-xl bg-amber-soft p-4 text-sm text-level-moderate">
              {question.tip}
            </p>
          </Card>
        )}

        {/*
          PROOF THE SENSOR IS READING, NOT A READOUT OF WHAT IT READS.

          A silent dropout mid-interview costs the whole session, so something has
          to show the stream is alive. It does not have to be the number. Outside
          developer mode this is a pulsing dot; the bpm itself appears only when
          `dev=1`, where the person watching is Salma and not a candidate.
        */}
        <Card title="Sensor">
          {device.connected === null ? (
            <p className="text-sm text-ink-muted">
              Tidak tersambung. Rekam dengan alatmu sendiri, unggah setelah sesi.
            </p>
          ) : device.bpm !== null ? (
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-level-low"
              />
              <p className="text-sm text-navy">
                Terbaca
                {devMode && (
                  <span className="ml-2 font-semibold tabular-nums text-ink-muted">
                    {device.bpm} bpm
                  </span>
                )}
              </p>
            </div>
          ) : (
            <p className="text-sm text-unknown">Menunggu denyut…</p>
          )}

          <HeartRateStream rrIntervals={device.rrIntervals} bpm={device.bpm} />
        </Card>

        {/*
          The session clock lives here in developer mode only. It is what Salma
          checks against the recorder's own clock while debugging; a candidate can
          do nothing with it, and a second running number on a screen that just
          lost its first one would put the arousal straight back.
        */}
        {devMode && (
          <Card title="Waktu sesi">
            <p className="text-2xl font-semibold tabular-nums text-navy">
              {formatClock(elapsed)}
            </p>
            <p className="mt-1 text-xs text-ink-muted">
              Termasuk periode tenang, agar cocok dengan jam rekaman.
            </p>
          </Card>
        )}
      </div>
    </div>
  )
}
