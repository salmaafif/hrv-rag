/**
 * useSessionState.ts — everything about the session being prepared and run.
 *
 * Setup and analysis live in one hook because they are one thing: the choices
 * made on the start screen are precisely the request the analysis sends. Split
 * across two hooks, the request would have to be reassembled somewhere, and
 * that somewhere would be a screen.
 *
 * Lives in `AppLayout` so a result survives the move from `/proses` to
 * `/hasil`. That is also why the result screen has to cope with finding
 * nothing: a cold page load has no analysis in memory.
 */

import { useCallback, useState } from 'react'
import { analyzeSession, analyzeTimeline } from '../api/client'
import type { AnalyzeOptions } from '../api/dummy'
import { ApiError, toApiError } from '../api/errors'
import { mockQuestionTimeline } from '../mocks/questionTimeline'
import type {
  AnalyzeRequest,
  Modality,
  QuestionTimelineEntry,
  SessionResponse,
  TimelineResponse,
} from '../types/api'
import { modalityFor, type WearLocation } from '../types/device'
import type { ModeDefinition } from './modes'
import type { DeviceConnection } from './useDeviceConnection'

export type AnalysisStatus = 'idle' | 'running' | 'done' | 'error'

/** Bounds for the resting period, in minutes. */
export const BASELINE_MIN_MINUTES = 2
export const BASELINE_MAX_MINUTES = 8

/**
 * How long V3 sits quiet before the first question, in minutes.
 *
 * Fixed rather than offered as a setting: the app runs this period itself, so
 * there is nothing the person could usefully decide, and asking would put a
 * choice in front of them that only makes the screen longer.
 *
 * TWO MINUTES IS THE FLOOR, not a cautious choice that could be trimmed further.
 * Features are computed over 60-second windows, so a one-minute rest produces a
 * beat series spanning only about 59 seconds — measured first beat to last, not
 * from when the timer started. Nothing fits, and the result is not a weaker
 * baseline but NO baseline, which leaves the entire session unscoreable because
 * every number this system reports is a change relative to the person's own
 * quiet state.
 *
 * Two minutes works because the backend samples the resting period every 15
 * seconds rather than every 30, recovering roughly the window count that three
 * minutes gave before. That extracts a steadier value from the same data; it
 * does not conjure more of it.
 *
 * Must stay equal to `SessionConfig.calibration_sec` in the Python settings, so
 * the documented protocol and the one users actually perform are the same.
 */
export const INTERVIEW_REST_MINUTES = 2

export interface SessionState {
  baselineMinutes: number
  setBaselineMinutes: (minutes: number) => void

  /**
   * Seconds of RR already buffered when the session screen mounted.
   *
   * The sensor hook collects beats from the moment it connects, and nothing ever
   * cleared that buffer — so the array sent to the backend could begin minutes
   * before the timestamps describing it. Recording the distance is better than
   * discarding the beats: those early minutes are the person sitting still with
   * the sensor on, which is exactly what a two-minute baseline is short of.
   */
  sessionOffsetSec: number
  markSessionStart: () => void

  fileName: string | null
  setFile: (file: File | null) => void
  fileWornAt: WearLocation | null
  setFileWornAt: (location: WearLocation) => void

  /**
   * Which sensor kind the recording came from, or null while unknown.
   *
   * Null is never filled in with a default. Mandatory rule #5 has the modality
   * reaching the prompt so the model can weigh its confidence, and a guess here
   * would miscalibrate that silently.
   */
  modality: Modality | null
  /**
   * True when there is both a data source and a known wear location — that is,
   * when the analysis has something to work on.
   *
   * Not the same as being able to START a V3 interview. The interview can run
   * with no sensor connected at all, because the recording is made elsewhere
   * and uploaded once the interview is over.
   */
  isReady: boolean
  storeConsented: boolean
  setStoreConsented: (agreed: boolean) => void

  /**
   * When each question was actually asked, recorded by V3 as it ran.
   *
   * Null until an interview has been completed. V2 has no way to produce this
   * yet and falls back to a fixture.
   */
  questionTimeline: QuestionTimelineEntry[] | null
  setQuestionTimeline: (entries: QuestionTimelineEntry[]) => void

  status: AnalysisStatus
  result: TimelineResponse | SessionResponse | null
  error: ApiError | null
  run: (mode: ModeDefinition, options?: AnalyzeOptions) => void
  /**
   * Clear the analysis only, keeping the recording and the question timeline.
   *
   * This is what "coba lagi" needs after a failure: the inputs were fine, the
   * server was not. Clearing them too would make the person choose their file
   * again for no reason.
   */
  reset: () => void
  /**
   * Clear everything and start a fresh session.
   *
   * What "latihan lagi" needs. Keeping the previous recording here would be
   * worse than useless — the next interview's question timings would be matched
   * against the previous interview's heart data, and the result would look
   * perfectly ordinary while describing the wrong session entirely.
   */
  restart: () => void
}

export function useSessionState(device: DeviceConnection): SessionState {
  const [baselineMinutes, setBaselineMinutesRaw] = useState(4)
  const [sessionOffsetSec, setSessionOffsetSec] = useState(0)
  const [file, setFileRaw] = useState<File | null>(null)
  const [fileWornAt, setFileWornAtState] = useState<WearLocation | null>(null)
  const [questionTimeline, setQuestionTimelineState] = useState<
    QuestionTimelineEntry[] | null
  >(null)

  /**
   * Freeze the distance between the two clocks, at the instant they diverge.
   *
   * Called once when the session screen mounts. Measured from the beats the
   * sensor has already produced rather than from a wall clock, because it is the
   * ARRAY that has to be indexed correctly — a wall-clock difference would not
   * account for beats the sensor dropped while nobody was looking.
   */
  const markSessionStart = useCallback(() => {
    const buffered = device.rrIntervals.reduce((total, ms) => total + ms, 0)
    setSessionOffsetSec(buffered / 1000)
  }, [device.rrIntervals])

  // Consent to keep the recording for research. False until the person ticks
  // the box themselves — a session that never saw the checkbox sends false,
  // which is the correct statement about it.
  const [storeConsented, setStoreConsented] = useState(false)

  const [status, setStatus] = useState<AnalysisStatus>('idle')
  const [result, setResult] = useState<TimelineResponse | SessionResponse | null>(
    null,
  )
  const [error, setError] = useState<ApiError | null>(null)

  const setBaselineMinutes = useCallback((minutes: number) => {
    if (!Number.isFinite(minutes)) return
    setBaselineMinutesRaw(
      Math.min(BASELINE_MAX_MINUTES, Math.max(BASELINE_MIN_MINUTES, minutes)),
    )
  }, [])

  const setFile = useCallback((next: File | null) => {
    setFileRaw(next)
    // A new file says nothing about the previous answer, so the wear location
    // is asked again rather than carried over from the last recording.
    setFileWornAtState(null)
  }, [])

  const setFileWornAt = useCallback((location: WearLocation) => {
    setFileWornAtState(location)
  }, [])

  const setQuestionTimeline = useCallback((entries: QuestionTimelineEntry[]) => {
    setQuestionTimelineState(entries)
  }, [])

  // A connected device wins over an uploaded file: it is the more recent,
  // more deliberate choice.
  const wornAt: WearLocation | null =
    device.connected !== null ? device.wornAt : fileWornAt
  const hasSource = device.connected !== null || file !== null
  const modality = wornAt === null ? null : modalityFor(wornAt)
  const isReady = hasSource && modality !== null

  const reset = useCallback(() => {
    setStatus('idle')
    setResult(null)
    setError(null)
  }, [])

  const restart = useCallback(() => {
    setStatus('idle')
    setResult(null)
    setError(null)
    setFileRaw(null)
    setFileWornAtState(null)
    setQuestionTimelineState(null)
  }, [])

  const run = useCallback(
    (mode: ModeDefinition, options: AnalyzeOptions = {}) => {
      if (modality === null) return
      setStatus('running')
      setError(null)

      const send = async () => {
        try {
          // Beats collected live from the sensor take precedence over an
          // uploaded file, matching the rule above that a connected device wins:
          // it is the more deliberate, more recent choice, and its timing lines
          // up with the interview because the same clock produced both.
          const beats = device.rrIntervals
          const base: AnalyzeRequest = {
            store_consented: storeConsented,
            baseline_minutes: baselineMinutes,
            offset_sec: beats.length ? sessionOffsetSec : 0,
            modality,
            ...(beats.length
              ? { rr_ms: beats }
              : file
                ? { csv: await file.text() }
                : {}),
          }

          const analysed =
            mode.endpoint === '/api/v1/analyze/timeline'
              ? await analyzeTimeline(base, options)
              : await analyzeSession(
                  {
                    ...base,
                    // V3 supplies real timings recorded during the interview.
                    // V2 has no editor yet, so it falls back to the fixture.
                    questions: questionTimeline ?? mockQuestionTimeline,
                  },
                  options,
                )

          setResult(analysed)
          setStatus('done')
        } catch (cause) {
          setError(toApiError(cause))
          setStatus('error')
        }
      }

      void send()
    },
    [baselineMinutes, device.rrIntervals, file, modality, questionTimeline,
     storeConsented,
     sessionOffsetSec],
  )

  return {
    baselineMinutes,
    setBaselineMinutes,
    sessionOffsetSec,
    markSessionStart,
    fileName: file?.name ?? null,
    setFile,
    fileWornAt,
    setFileWornAt,
    modality,
    isReady,
    storeConsented,
    setStoreConsented,
    questionTimeline,
    setQuestionTimeline,
    status,
    result,
    error,
    run,
    reset,
    restart,
  }
}
