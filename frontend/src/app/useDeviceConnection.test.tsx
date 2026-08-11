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
