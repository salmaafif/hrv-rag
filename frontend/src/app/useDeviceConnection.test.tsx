/**
 * @vitest-environment jsdom
 *
 * useDeviceConnection.test.tsx — the live sensor path.
 *
 * This hook is the only place a real person's heartbeat enters the system, and
 * every failure it can have is quiet. A device that sends no intervals still
 * reports a believable heart rate. A decoder that drops beats still produces
 * intervals in the right range. Nothing on screen would look wrong.
 *
 * The Web Bluetooth API is replaced with a fake device here rather than mocked
 * loosely, so the tests exercise the real notification path: flags byte, packet
 * layout, accumulation, and the disconnect handler.
 */

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDeviceConnection } from './useDeviceConnection'
import { DEMO_RR_MS, SIMULATION_SPEED } from '../mocks/recording'

/** Encode milliseconds the way the spec does: units of 1/1024 second. */
const rr = (ms: number) => {
  const units = Math.round((ms / 1000) * 1024)
  return [units & 0xff, units >> 8]
}

/**
 * A stand-in strap that lets a test push packets at the page.
 *
 * Built as a working fake rather than a stub because the interesting failures
 * are in the wiring — subscribing to notifications, holding the listener, and
 * releasing the radio on disconnect — not in any single function.
 */
function fakeStrap(name = 'Coospo H808S') {
  let listener: ((event: Event) => void) | null = null
  const disconnect = vi.fn()

  const characteristic = {
    addEventListener: (_: string, fn: (event: Event) => void) => { listener = fn },
    startNotifications: vi.fn().mockResolvedValue(undefined),
  }
  const device = {
    id: 'fake-1',
    name,
    gatt: {
      connect: vi.fn().mockResolvedValue({
        getPrimaryService: vi.fn().mockResolvedValue({
          getCharacteristic: vi.fn().mockResolvedValue(characteristic),
        }),
      }),
      disconnect,
    },
    addEventListener: vi.fn(),
  }

  return {
    device,
    disconnect,
    install() {
      vi.stubGlobal('navigator', {
        ...globalThis.navigator,
        bluetooth: { requestDevice: vi.fn().mockResolvedValue(device) },
      })
    },
    /** Push one Heart Rate Measurement packet, as the strap would. */
    notify(...bytes: number[]) {
      const value = new DataView(new Uint8Array(bytes).buffer)
      listener?.({ target: { value } } as unknown as Event)
    },
  }
}

let strap: ReturnType<typeof fakeStrap>

beforeEach(() => {
  strap = fakeStrap()
  strap.install()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('connecting', () => {
  it('adopts a wear location it recognises from the device name', async () => {
    const { result } = renderHook(() => useDeviceConnection())
    await act(async () => { result.current.scan() })

    await waitFor(() => expect(result.current.status).toBe('connected'))
    expect(result.current.connected?.name).toBe('Coospo H808S')
    // H series is a chest strap; the HW series is not.
    expect(result.current.wornAt).toBe('chest')
  })

  it('leaves the wear location unset for a name it does not recognise', async () => {
    // Guessing here would silently mislabel the modality, and modality is what
    // tells the model how much to trust an optical reading.
    strap = fakeStrap('HRM-2938')
    strap.install()

    const { result } = renderHook(() => useDeviceConnection())
    await act(async () => { result.current.scan() })

    await waitFor(() => expect(result.current.status).toBe('connected'))
    expect(result.current.wornAt).toBeNull()
  })

  it('stays idle when the person closes the chooser', async () => {
    vi.stubGlobal('navigator', {
      ...globalThis.navigator,
      bluetooth: { requestDevice: vi.fn().mockRejectedValue(new Error('cancelled')) },
    })

    const { result } = renderHook(() => useDeviceConnection())
    await act(async () => { result.current.scan() })

    await waitFor(() => expect(result.current.status).toBe('idle'))
    expect(result.current.connected).toBeNull()
  })

  it('reports the browser as unsupported when Bluetooth is absent', () => {
    vi.stubGlobal('navigator', {})
    const { result } = renderHook(() => useDeviceConnection())
    // Every browser on iOS lands here, which is why the file-upload path exists.
    expect(result.current.isSupported).toBe(false)
  })
})

describe('collecting intervals', () => {
  async function connected() {
    const hook = renderHook(() => useDeviceConnection())
    await act(async () => { hook.result.current.scan() })
    await waitFor(() => expect(hook.result.current.status).toBe('connected'))
    return hook
  }

  it('accumulates every interval the strap sends', async () => {
    const { result } = await connected()

    await act(async () => { strap.notify(0x10, 70, ...rr(900), ...rr(880)) })
    await act(async () => { strap.notify(0x10, 71, ...rr(870)) })

    expect(result.current.rrIntervals.map(Math.round)).toEqual([900, 880, 870])
    expect(result.current.bpm).toBe(71)
  })

  it('announces immediately when a device sends no intervals', async () => {
    // The single fact that decides whether HRV is possible at all. Finding it
    // out from the first packet is the difference between telling someone now
    // and telling them after a fifteen-minute session.
    const { result } = await connected()

    await act(async () => { strap.notify(0x00, 68) })

    expect(result.current.sendsRrIntervals).toBe(false)
    expect(result.current.bpm).toBe(68)
    expect(result.current.rrIntervals).toEqual([])
  })

  it('announces when the device does send intervals', async () => {
    const { result } = await connected()
    await act(async () => { strap.notify(0x10, 70, ...rr(850)) })
    expect(result.current.sendsRrIntervals).toBe(true)
  })

  it('does not let a later packet overturn the first verdict', async () => {
    // Straps drop the RR field in individual packets when contact is briefly
    // poor. Flipping the verdict back and forth would make the interface flicker
    // between "this works" and "this cannot work" during a session.
    const { result } = await connected()

    await act(async () => { strap.notify(0x10, 70, ...rr(850)) })
    await act(async () => { strap.notify(0x00, 70) })

    expect(result.current.sendsRrIntervals).toBe(true)
  })
})

describe('signal quality', () => {
  async function connected() {
    const hook = renderHook(() => useDeviceConnection())
    await act(async () => { hook.result.current.scan() })
    await waitFor(() => expect(hook.result.current.status).toBe('connected'))
    return hook
  }

  it('withholds a verdict until there is enough to judge', async () => {
    const { result } = await connected()
    await act(async () => { strap.notify(0x10, 70, ...rr(850), ...rr(860)) })
    // Two beats say nothing about a sensor. Null means "not yet known", which is
    // a different statement from "good".
    expect(result.current.signalQuality).toBeNull()
  })

  it('calls a clean series good', async () => {
    const { result } = await connected()
    for (let i = 0; i < 20; i++) {
      await act(async () => { strap.notify(0x10, 70, ...rr(850)) })
    }
    expect(result.current.signalQuality).toBe('good')
  })

  it('calls a series poor once implausible intervals pass the 10% gate', async () => {
    // 10% is where the Python pipeline discards a whole segment, so beyond it the
    // data is already unusable rather than merely untidy — the two sides of the
    // system have to agree on that number.
    const { result } = await connected()
    for (let i = 0; i < 16; i++) {
      await act(async () => { strap.notify(0x10, 70, ...rr(850)) })
    }
    for (let i = 0; i < 4; i++) {
      // 200 ms is 300 bpm: not a heartbeat, a detection failure.
      await act(async () => { strap.notify(0x10, 70, ...rr(200)) })
    }
    expect(result.current.signalQuality).toBe('poor')
  })
})

describe('disconnecting', () => {
  it('releases the radio, so other apps can reach the strap again', async () => {
    // Straps generally allow one connection. A page that keeps its grip after
    // the person has moved on makes the device unusable until it times out.
    const { result } = renderHook(() => useDeviceConnection())
    await act(async () => { result.current.scan() })
    await waitFor(() => expect(result.current.status).toBe('connected'))

    await act(async () => { result.current.disconnect() })

    expect(strap.disconnect).toHaveBeenCalled()
    expect(result.current.connected).toBeNull()
    expect(result.current.bpm).toBeNull()
  })

  it('releases the radio when the component unmounts', async () => {
    const { result, unmount } = renderHook(() => useDeviceConnection())
    await act(async () => { result.current.scan() })
    await waitFor(() => expect(result.current.status).toBe('connected'))

    unmount()
    expect(strap.disconnect).toHaveBeenCalled()
  })
})

describe('simulation mode', () => {
  it('connects without any hardware and produces beats', async () => {
    // Behind `?dev=1` so a simulated session cannot be mistaken for a real one:
    // the flag is visible in the URL.
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useDeviceConnection(true))
      await act(async () => { result.current.scan() })
      expect(result.current.status).toBe('connected')

      await act(async () => { vi.advanceTimersByTime(3000) })
      expect(result.current.rrIntervals.length).toBeGreaterThan(0)
      expect(result.current.bpm).toBeGreaterThan(40)
    } finally {
      vi.useRealTimers()
    }
  })

  it('produces beats that vary, so a flattened series cannot hide', async () => {
    // A constant interval gives RMSSD exactly zero, which would mask any bug
    // that destroys beat-to-beat variation.
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useDeviceConnection(true))
      await act(async () => { result.current.scan() })
      await act(async () => { vi.advanceTimersByTime(10000) })

      const unique = new Set(result.current.rrIntervals)
      expect(unique.size).toBeGreaterThan(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not touch Bluetooth at all', async () => {
    const requestDevice = vi.fn()
    vi.stubGlobal('navigator', { ...globalThis.navigator, bluetooth: { requestDevice } })

    const { result } = renderHook(() => useDeviceConnection(true))
    await act(async () => { result.current.scan() })

    expect(requestDevice).not.toHaveBeenCalled()
  })
})

describe('the simulated sensor', () => {
  /**
   * The simulation exists so a fifteen-minute session can be checked without
   * sitting through fifteen minutes. Two things have to hold for that to be
   * worth anything, and both are quiet when broken: the beats must be real
   * measurements rather than noise, and the clock they imply must agree with
   * the one that stamps the questions.
   */
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const connectSimulated = async () => {
    const view = renderHook(() => useDeviceConnection(true))
    // In simulation `scan` IS the connection: there is no chooser to open.
    await act(async () => {
      view.result.current.scan()
      await vi.advanceTimersByTimeAsync(0)
    })
    return view
  }

  it('plays a real recording rather than inventing numbers', async () => {
    const view = await connectSimulated()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    const collected = view.result.current.rrIntervals
    expect(collected.length).toBeGreaterThan(5)
    // The exact opening beats of WESAD S2. Random intervals would match the
    // range but never the sequence, which is the difference between a demo that
    // shows the system working and one that only shows it running.
    expect(collected.slice(0, 5)).toEqual(DEMO_RR_MS.slice(0, 5))
  })

  it('advances the recording at exactly the shared speed factor', async () => {
    const view = await connectSimulated()

    const REAL_MS = 6_000
    await act(async () => {
      await vi.advanceTimersByTimeAsync(REAL_MS)
    })

    const played = view.result.current.rrIntervals.reduce((a, b) => a + b, 0)

    // THE INVARIANT THE WHOLE FEATURE RESTS ON. After six real seconds the
    // recording must have advanced sixty of its own. `SessionPage` scales its
    // clock by the same constant, so the question stamps and the beat positions
    // describe the same moments. Drop the factor from either side and the
    // windows silently move to the wrong minutes.
    //
    // Tolerance is one beat, not a fudge factor: the beat currently playing is
    // already counted while its own delay is still running. Anything wrong with
    // the speed misses by a multiple, not by a beat — no factor at all lands on
    // six seconds, and thirty times lands on a hundred and eighty.
    const expected = (REAL_MS / 1000) * SIMULATION_SPEED
    expect(Math.abs(played / 1000 - expected)).toBeLessThan(1.5)
  })

  it('stops when the recording runs out instead of inventing more', async () => {
    const view = await connectSimulated()

    // Long past the fourteen minutes of recording, at ten times speed.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5 * 60_000)
    })
    const atEnd = view.result.current.rrIntervals.length

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })

    expect(atEnd).toBe(DEMO_RR_MS.length)
    expect(view.result.current.rrIntervals.length).toBe(atEnd)
    // Looping would replay one person's stress response as though it happened
    // twice; holding the last value would feed a flat line into RMSSD. Both
    // keep the demo moving while describing something that never happened.
    expect(view.result.current.signalQuality).toBe('poor')
  })

  it('produces intervals that actually vary, so RMSSD means something', async () => {
    const view = await connectSimulated()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000)
    })

    const unique = new Set(view.result.current.rrIntervals)
    expect(unique.size).toBeGreaterThan(10)
  })
})

describe('the beat-stream watchdog', () => {
  /**
   * The failure it exists for: another app takes the sensor mid-session. No
   * `gattserverdisconnected` fires — the connection stays "up" and the
   * notifications simply stop. The third real pilot session died this way,
   * silently, and cost fifteen minutes before anything said so.
   */
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const connectReal = async () => {
    const view = renderHook(() => useDeviceConnection(false))
    await act(async () => {
      view.result.current.scan()
      await vi.advanceTimersByTimeAsync(0)
    })
    return view
  }

  it('raises the alarm when beats stop arriving on a live connection', async () => {
    const view = await connectReal()

    // Beats flow: no alarm.
    await act(async () => {
      strap.notify(0x10, 60, ...rr(850))
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(view.result.current.streamStalled).toBe(false)

    // Another app takes the sensor: silence, connection still "up".
    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000)
    })
    expect(view.result.current.streamStalled).toBe(true)
  })

  it('clears the alarm the moment beats return', async () => {
    const view = await connectReal()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000)
    })
    expect(view.result.current.streamStalled).toBe(true)

    await act(async () => {
      strap.notify(0x10, 60, ...rr(850))
    })
    expect(view.result.current.streamStalled).toBe(false)
  })

  it('does not cry wolf while merely connecting', async () => {
    const view = await connectReal()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)     // under the threshold
    })
    expect(view.result.current.streamStalled).toBe(false)
  })
})
