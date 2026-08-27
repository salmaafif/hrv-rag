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
 *     where the sensor was worn;
 *   - what survives a retry after a failure.
 *
 * None of those announce themselves on screen. Sending the wrong recording still
 * produces a complete, confident report — about the wrong session.
 */

import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSessionState } from './useSessionState'
import { MODES } from './modes'
import type { DeviceConnection } from './useDeviceConnection'

const V1 = MODES.v1
const V3 = MODES.v3

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
  const timeline = vi.fn().mockResolvedValue({ timeline: [], summary: {} })
  const session = vi.fn().mockResolvedValue({ questions: [] })
  vi.doMock('../api/client', () => ({
    analyzeTimeline: timeline,
    analyzeSession: session,
    ApiError: class extends Error {},
  }))
  return { timeline, session }
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

describe('choosing which recording to send', () => {
  it('sends live beats when the sensor collected them', async () => {
    const { timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [856, 842, 871] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.run(V1) })

    await waitFor(() => expect(timeline).toHaveBeenCalled())
    const sent = timeline.mock.calls[0]![0]
    expect(sent.rr_ms).toEqual([856, 842, 871])
    expect(sent.csv).toBeUndefined()
  })

  it('sends the uploaded file when no sensor beats exist', async () => {
    const { timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const { result } = renderHook(() => hook(noDevice()))
    act(() => { result.current.setFile(recording('900\n910\n')) })
    act(() => { result.current.setFileWornAt('chest') })
    act(() => { result.current.run(V1) })

    await waitFor(() => expect(timeline).toHaveBeenCalled())
    const sent = timeline.mock.calls[0]![0]
    expect(sent.csv).toBe('900\n910\n')
    expect(sent.rr_ms).toBeUndefined()
  })

  it('sends live beats rather than the file when both are present', async () => {
    // The dangerous case. Both are valid recordings, both produce a complete
    // report, and only one of them is the session the person just did.
    const { timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [800, 810] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.setFile(recording('999\n998\n')) })
    act(() => { result.current.run(V1) })

    await waitFor(() => expect(timeline).toHaveBeenCalled())
    const sent = timeline.mock.calls[0]![0]
    expect(sent.rr_ms).toEqual([800, 810])
    expect(sent.csv).toBeUndefined()
  })

  it('always states the resting duration and the modality', async () => {
    const { timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [850] })
    const { result } = renderHook(() => hook(device))
    act(() => { result.current.run(V1) })

    await waitFor(() => expect(timeline).toHaveBeenCalled())
    const sent = timeline.mock.calls[0]![0]
    // Without these the backend cannot say where the baseline ends, nor how much
    // to trust the signal.
    expect(sent.modality).toBe('ECG')
    expect(sent.baseline_minutes).toBeGreaterThan(0)
  })

  it('refuses to run at all while the modality is unknown', async () => {
    const { timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const { result } = renderHook(() => hook(noDevice()))
    act(() => { result.current.run(V1) })

    expect(timeline).not.toHaveBeenCalled()
    expect(result.current.status).toBe('idle')
  })

  it('routes the interview mode to the session endpoint with its timeline', async () => {
    const { session, timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')

    const device = connectedDevice({ rrIntervals: [850] })
    const { result } = renderHook(() => hook(device))
    act(() => {
      result.current.setQuestionTimeline([
        {
          number: 1, text: 'Ceritakan tentang dirimu', type: 'behavioural',
          answer_start_sec: 120, answer_end_sec: 210, gap_end_sec: 270,
          is_difficult: false,
        },
      ])
    })
    act(() => { result.current.run(V3) })

    await waitFor(() => expect(session).toHaveBeenCalled())
    expect(timeline).not.toHaveBeenCalled()
    const sent = session.mock.calls[0]![0]
    expect(sent.questions).toHaveLength(1)
    // Times are already measured from the start of the recording.
    expect(sent.questions[0].answer_start_sec).toBe(120)
  })
})

describe('the resting duration', () => {
  it('refuses a value below the floor', () => {
    // Below two minutes the backend gets no baseline windows at all, so the
    // whole session becomes unscoreable. Clamping here stops that reaching it.
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setBaselineMinutes(0) })
    expect(result.current.baselineMinutes).toBeGreaterThanOrEqual(2)
  })

  it('refuses an absurdly long value', () => {
    const { result } = renderHook(() => useSessionState(noDevice()))
    act(() => { result.current.setBaselineMinutes(600) })
    expect(result.current.baselineMinutes).toBeLessThanOrEqual(8)
  })

  it('ignores a value that is not a number', () => {
    // An empty number input yields NaN. Storing it would send NaN minutes to the
    // backend and produce a baseline of nothing.
    const { result } = renderHook(() => useSessionState(noDevice()))
    const before = result.current.baselineMinutes
    act(() => { result.current.setBaselineMinutes(Number.NaN) })
    expect(result.current.baselineMinutes).toBe(before)
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
    const { analyzeSession } = await import('../api/client')
    const { session } = spyOnApi()
    void analyzeSession
    const { useSessionState: hook } = await import('./useSessionState')

    // 200 beats of 900 ms = 180 seconds of sitting still before pressing start.
    const beats = Array.from({ length: 200 }, () => 900)
    const { result } = renderHook(() => hook(connectedDevice({ rrIntervals: beats })))

    act(() => { result.current.markSessionStart() })
    act(() => { result.current.run(V3) })

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
    act(() => { result.current.run(V3) })

    await waitFor(() => expect(session).toHaveBeenCalled())
    expect(session.mock.calls[0][0].offset_sec).toBe(0)
  })

  it('sends zero for an uploaded file, where the clocks coincide', async () => {
    const { timeline } = spyOnApi()
    const { useSessionState: hook } = await import('./useSessionState')
    const { result } = renderHook(() => hook(noDevice()))

    act(() => { result.current.setFile(recording()) })
    act(() => { result.current.setFileWornAt('chest') })
    act(() => { result.current.run(V1) })

    await waitFor(() => expect(timeline).toHaveBeenCalled())
    expect(timeline.mock.calls[0][0].offset_sec).toBe(0)
  })
})
