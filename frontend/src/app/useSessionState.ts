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

export interface SessionState {
  baselineMinutes: number
  setBaselineMinutes: (minutes: number) => void

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
  /** True when there is both a data source and a known wear location. */
  isReady: boolean

  status: AnalysisStatus
  result: TimelineResponse | SessionResponse | null
  error: ApiError | null
  run: (mode: ModeDefinition, options?: AnalyzeOptions) => void
  reset: () => void
}

export function useSessionState(device: DeviceConnection): SessionState {
  const [baselineMinutes, setBaselineMinutesRaw] = useState(4)
  const [file, setFileRaw] = useState<File | null>(null)
  const [fileWornAt, setFileWornAtState] = useState<WearLocation | null>(null)

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

  const run = useCallback(
    (mode: ModeDefinition, options: AnalyzeOptions = {}) => {
      if (modality === null) return
      setStatus('running')
      setError(null)

      const send = async () => {
        try {
          const base: AnalyzeRequest = {
            baseline_minutes: baselineMinutes,
            modality,
            // Real beat intervals and CSV text arrive with the Bluetooth and
            // file-parsing work; the dummy backend ignores both for now.
            ...(file ? { csv: await file.text() } : {}),
          }

          const analysed =
            mode.endpoint === '/api/v1/analyze/timeline'
              ? await analyzeTimeline(base, options)
              : await analyzeSession(
                  { ...base, questions: mockQuestionTimeline },
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
    [baselineMinutes, file, modality],
  )

  return {
    baselineMinutes,
    setBaselineMinutes,
    fileName: file?.name ?? null,
    setFile,
    fileWornAt,
    setFileWornAt,
    modality,
    isReady,
    status,
    result,
    error,
    run,
    reset,
  }
}
