/**
 * @vitest-environment jsdom
 *
 * useSessionState.test.tsx — what gets sent for analysis, and when.
 *
 * This hook decides three things that are easy to get wrong quietly:
 *
 *   - WHICH recording travels to the backend when both a sensor and an uploaded
 *     file are present;
 *   - whether the analysis is allowed to start at all, which hinges on knowing
 *     where the sensor was worn and on an interview having been run;
 *   - what survives a retry after a failure.
 *
 * None of those announce themselves on screen. Sending the wrong recording still
 * produces a complete, confident report — about the wrong session.
 */

import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { INTERVIEW_REST_MINUTES, useSessionState } from './useSessionState'
import type { DeviceConnection } from './useDeviceConnection'
import type { QuestionTimelineEntry } from '../types/api'

/** What an interview leaves behind: when each question was asked. */
const TIMELINE: QuestionTimelineEntry[] = [
  {
    number: 1, text: 'Ceritakan tentang dirimu', type: 'behavioural',
    answer_start_sec: 120, answer_end_sec: 210, gap_end_sec: 270,
    is_difficult: false,
  },
]

/** A disconnected sensor: the state every session starts from. */
function noDevice(): DeviceConnection {
  return {
    isSupported: true,
    status: 'idle',
    devices: [],
    connected: null,
    wornAt: null,
    signalQuality: null,
    streamStalled: false,
    bpm: null,
    sendsRrIntervals: null,
    rrIntervals: [],
    bpmReadings: [],
    clearIntervals: () => {},
    scan: () => {},
    connect: () => {},
    disconnect: () => {},
    setWornAt: () => {},
  }
}

function connectedDevice(
  overrides: Partial<DeviceConnection> = {},
): DeviceConnection {
  return {
    ...noDevice(),
    status: 'connected',
    connected: { id: 'x', name: 'Coospo H808S', wornAt: 'chest' },
    wornAt: 'chest',
    bpm: 70,
    sendsRrIntervals: true,
    ...overrides,
  }
}

/** A CSV upload, as the file picker would hand it over. */
function recording(text = '856\n842\n871\n') {
  return { name: 'rekaman.csv', text: async () => text } as unknown as File
}

/** Capture what the API layer was asked to send. */
function spyOnApi() {
  const session = vi.fn().mockResolvedValue({ questions: [] })
  vi.doMock('../api/client', () => ({
    analyzeSession: session,
    ApiError: class extends Error {},
  }))
  return { session }
}

beforeEach(() => {
  vi.resetModules()
  vi.restoreAllMocks()
})

describe('knowing whether analysis can start', () => {
  it('is not ready with nothing at all', () => {
    const { result } = renderHook(() => useSessionState(noDevice()))
    expect(result.current.isReady).toBe(false)
    expect(result.current.modality).toBeNull()
  })

  it('is not ready with a file whose wear location is unanswered', () => {
    // The file exists, but nobody has said where the sensor sat. Guessing would
    // send the wrong modality to the model, which is what decides how much to
    // discount an optical reading.
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setFile(recording()) })

    expect(result.current.fileName).toBe('rekaman.csv')
    expect(result.current.isReady).toBe(false)
  })

  it('becomes ready once the wear location is answered', () => {
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('wrist') })

    expect(result.current.modality).toBe('PPG')
    expect(result.current.isReady).toBe(true)
  })

  it('is not ready when a connected sensor was not recognised', () => {
    // A device is plugged in, but its name told us nothing. Same rule: ask,
    // never assume.
    const device = connectedDevice({ wornAt: null })
    const { result } = renderHook(() => useSessionState(device))
    expect(result.current.isReady).toBe(false)
  })

  it('lets a recognised chest strap through as ECG', () => {
    const { result } = renderHook(() => useSessionState(connectedDevice()))
    expect(result.current.modality).toBe('ECG')
    expect(result.current.isReady).toBe(true)
  })

  it('cannot analyse a connected sensor before an interview has run', () => {
    // The state "latihan lagi" leaves behind: sensor still on, timeline gone.
    // Ready to record, yet nothing to score — the processing screen used to
    // spin forever here waiting for a request that was never sent.
    const { result } = renderHook(() => useSessionState(connectedDevice()))
    expect(result.current.isReady).toBe(true)
    expect(result.current.canAnalyse).toBe(false)
  })

  it('can analyse once the interview has left its timeline', () => {
    const { result } = renderHook(() => useSessionState(connectedDevice()))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    expect(result.current.canAnalyse).toBe(true)
  })

  it('prefers the connected sensor over a stale uploaded file', () => {
    // Connecting a sensor is the later, more deliberate act. If a file from an
    // earlier attempt still sat in state, its wear location must not win.
    const device = connectedDevice({ wornAt: 'chest' })
    const { result } = renderHook(() => useSessionState(device))
    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('wrist') })

    expect(result.current.modality).toBe('ECG')
  })
})

describe('choosing what to send', () => {
  it('sends live beats when the sensor collected them', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [856, 842, 871] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.rr_ms).toEqual([856, 842, 871])
    expect(sent.csv).toBeUndefined()
  })

  it('sends the uploaded file when no sensor beats exist', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const { result } = renderHook(() => hook(noDevice()))
    act(() => { result.current.setFile(recording('900\n910\n')) })
    act(() => { result.current.setFileWornAt('chest') })
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.csv).toBe('900\n910\n')
    expect(sent.rr_ms).toBeUndefined()
  })

  it('sends live beats rather than the file when both are present', async () => {
    // The dangerous case. Both are valid recordings, both produce a complete
    // report, and only one of them is the session the person just did.
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [800, 810] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.setFile(recording('999\n998\n')) })
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.rr_ms).toEqual([800, 810])
    expect(sent.csv).toBeUndefined()
  })

  it('sends the timeline the interview recorded', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [850] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    // Times are already measured from the start of the recording.
    expect(sent.questions).toEqual(TIMELINE)
  })

  it('states the resting period the session screen actually ran', async () => {
    // One constant drives both the countdown and this field. A setting that
    // could hold a different value is how the screen once waited four minutes
    // while the backend was told two.
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [850] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.baseline_minutes).toBe(INTERVIEW_REST_MINUTES)
    expect(sent.modality).toBe('ECG')
  })

  it('refuses to run at all while the modality is unknown', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const { result } = renderHook(() => hook(noDevice()))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    expect(session).not.toHaveBeenCalled()
    expect(result.current.status).toBe('idle')
  })

  it('refuses to run before an interview has produced a timeline', async () => {
    // There is no question to score, and sending an empty list would come back
    // looking valid while describing nothing.
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [850] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.run() })

    expect(session).not.toHaveBeenCalled()
    expect(result.current.status).toBe('idle')
  })
})

describe('a watch that reports heart rate only', () => {
  /** One report a second, from the second the watch connected. */
  const reports = (count: number, bpm = 72) =>
    Array.from({ length: count }, (_, i) => ({ atSec: i, bpm }))

  it('sends its heart-rate reports, and no intervals it never had', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const watch = connectedDevice({
      sendsRrIntervals: false, rrIntervals: [], bpmReadings: reports(200),
    })
    const { result } = renderHook(() => hook(watch))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.bpm_samples).toHaveLength(200)
    expect(sent.bpm_samples[0]).toEqual({ at_sec: 0, bpm: 72 })
    expect(sent.rr_ms).toBeUndefined()
    expect(sent.csv).toBeUndefined()
    expect(sent.rr_coverage).toBe(0)
  })

  it('measures how long it streamed before the session on its own clock', async () => {
    // THE BUG THIS PREVENTS. The interval buffer of a watch is empty, so an
    // offset read from it is zero however long the watch had been streaming —
    // and every question would land that many seconds early.
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    // 181 reports, one a second: 180 s of sitting still before pressing start.
    const watch = connectedDevice({
      sendsRrIntervals: false, rrIntervals: [], bpmReadings: reports(181),
    })
    const { result } = renderHook(() => hook(watch))
    act(() => { result.current.markSessionStart() })
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.offset_sec).toBe(180)
    expect(sent.bpm_offset_sec).toBe(180)
    // Exposed too: the result screen places the watch's chart with it.
    expect(result.current.sessionBpmOffsetSec).toBe(180)
  })

  it('sends both streams from a strap, with the coverage that decides', async () => {
    // The backend chooses the path. It can only choose with both in hand.
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const strap = connectedDevice({
      rrIntervals: Array.from({ length: 200 }, () => 900),   // 180 s
      bpmReadings: reports(181),                             // 180 s span
    })
    const { result } = renderHook(() => hook(strap))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.rr_ms).toHaveLength(200)
    expect(sent.bpm_samples).toHaveLength(181)
    expect(sent.rr_coverage).toBeCloseTo(1, 5)
  })

  it('does not send a single report as if it were a stream', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const strap = connectedDevice({ rrIntervals: [850, 860], bpmReadings: reports(1) })
    const { result } = renderHook(() => hook(strap))
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    const sent = session.mock.calls[0]![0]
    expect(sent.bpm_samples).toBeUndefined()
    expect(sent.rr_coverage).toBeUndefined()
    expect(sent.rr_ms).toEqual([850, 860])
  })
})

describe('recovering from a failure', () => {
  it('keeps the recording so a retry does not ask for it again', async () => {
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('chest') })

    act(() => { result.current.reset() })

    expect(result.current.fileName).toBe('rekaman.csv')
    expect(result.current.isReady).toBe(true)
  })

  it('clears the recording when starting over deliberately', () => {
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('chest') })

    act(() => { result.current.restart() })

    expect(result.current.fileName).toBeNull()
    expect(result.current.isReady).toBe(false)
  })

  it('asks again where a NEW file was worn', () => {
    // A different recording may well have come from a different device, and the
    // modality decides how much the whole reading is trusted.
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('chest') })
    act(() => { result.current.setFile(recording('700\n')) })

    expect(result.current.fileWornAt).toBeNull()
    expect(result.current.isReady).toBe(false)
  })
})

describe('the two clocks', () => {
  // The sensor streams from the moment it pairs; the session clock starts when
  // the person presses start. Nothing ever cleared the buffer between those two
  // instants, so the array could begin minutes before every timestamp describing
  // it — and the report stayed complete while describing different minutes.

  it('reports how much recording preceded the session', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    // 200 beats of 900 ms = 180 seconds of sitting still before pressing start.
    const beats = Array.from({ length: 200 }, () => 900)
    const { result } = renderHook(() => hook(connectedDevice({ rrIntervals: beats })))

    act(() => { result.current.markSessionStart() })
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    expect(session.mock.calls[0][0].offset_sec).toBeCloseTo(180, 1)
  })

  it('sends zero when the session started with an empty buffer', async () => {
    // Beats that arrive AFTER the session began are session data, not prelude.
    // The offset is fixed once, at the instant the clocks diverge.
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const { result, rerender } = renderHook(
      ({ device }: { device: DeviceConnection }) => hook(device),
      { initialProps: { device: connectedDevice({ rrIntervals: [] }) } },
    )
    act(() => { result.current.markSessionStart() })

    rerender({
      device: connectedDevice({
        rrIntervals: Array.from({ length: 100 }, () => 900),
      }),
    })
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    expect(session.mock.calls[0][0].offset_sec).toBe(0)
  })

  it('sends zero for an uploaded file, where the clocks coincide', async () => {
    const { session } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')
    const { result } = renderHook(() => hook(noDevice()))

    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('chest') })
    act(() => { result.current.setQuestionTimeline(TIMELINE) })
    act(() => { result.current.run() })

    await waitFor(() => expect(session).toHaveBeenCalled())
    expect(session.mock.calls[0][0].offset_sec).toBe(0)
  })
})
