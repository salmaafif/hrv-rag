/**
 * useDeviceConnection.ts — connecting to a heart sensor over Web Bluetooth.
 *
 * WHAT THIS COLLECTS, AND WHY IT IS NOT THE HEART RATE. The number on screen is
 * only there to show the sensor is alive. What the analysis actually needs is the
 * RR-interval series: the gap between one beat and the next, in milliseconds.
 * RMSSD is defined as the variation BETWEEN successive beats, so a device that
 * reports only an averaged bpm has destroyed the quantity rather than coarsened
 * it — no amount of processing downstream can recover it.
 *
 * Whether a device sends intervals is not a property of its brand. It is one bit
 * in every packet, and this hook surfaces it as `sendsRrIntervals` so a device
 * that cannot support HRV says so immediately, rather than after someone has sat
 * through a fifteen-minute session.
 *
 * MODALITY MAKES NO DIFFERENCE HERE. A chest strap and an optical armband both
 * speak the same standard Heart Rate Service, and both hand over intervals their
 * own firmware already derived. The chest/wrist distinction survives only as a
 * label, carried onward so the model can weigh an optical reading more cautiously
 * — it changes nothing about how this file works.
 *
 * BROWSER LIMITS, WHICH ARE REAL AND NOT WORKED AROUND. Web Bluetooth exists only
 * in Chromium browsers (Chrome, Edge, Opera) on desktop and Android, and only
 * over HTTPS or localhost. It does not exist on iOS at all — every browser there
 * is built on WebKit, so Chrome on an iPhone cannot do this either. `isSupported`
 * reports that honestly so the interface can offer the file-upload path instead
 * of failing at the moment someone presses a button.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { parseHeartRateMeasurement } from './heartRateProtocol'
import { mockDiscoveredDevices } from '../mocks/devices'
import { DEMO_RR_MS, SIMULATION_SPEED } from '../mocks/recording'
import { recogniseWearLocation, type WearLocation } from '../types/device'
import type { HeartDevice } from '../types/device'

export type ConnectionStatus = 'idle' | 'scanning' | 'listed' | 'connected'

/**
 * How trustworthy the incoming signal looks.
 *
 * Kept separate from the stress result on purpose: this describes the sensor,
 * not the person. A poor signal is a reason to fix the strap, not a finding
 * about how someone is coping.
 *
 * Judged from the share of intervals that fall outside human physiology, using
 * the same 0.3-2.0 second bounds the Python pipeline applies. That keeps the
 * on-screen warning and the analysis speaking about the same thing.
 */
export type SignalQuality = 'good' | 'fair' | 'poor'

/** Physiological bounds, matching `QualityConfig` on the Python side. */
const RR_MIN_MS = 300
const RR_MAX_MS = 2000

/** How many recent intervals the quality estimate looks at. */
const QUALITY_WINDOW = 60

export interface DeviceConnection {
  /** False when the browser cannot do Web Bluetooth at all. */
  isSupported: boolean
  status: ConnectionStatus
  devices: HeartDevice[]
  connected: HeartDevice | null
  /**
   * Where the connected device is worn. Null while unknown — either nothing is
   * connected, or the device was not recognised and the person has not answered
   * yet. Never guessed.
   */
  wornAt: WearLocation | null
  signalQuality: SignalQuality | null
  /** Live beats per minute. Shown as evidence the sensor is reading. */
  bpm: number | null
  /**
   * Whether this device actually sends beat-to-beat intervals.
   *
   * Null until the first packet arrives. False means HRV cannot be computed from
   * it at all, however good its heart rate looks.
   */
  sendsRrIntervals: boolean | null
  /** Every interval collected since connecting, in milliseconds. */
  rrIntervals: number[]
  /** Discard the collected intervals — used when a session restarts. */
  clearIntervals: () => void
  scan: () => void
  connect: (deviceId: string) => void
  disconnect: () => void
  setWornAt: (location: WearLocation) => void
}

function bluetoothAvailable(): boolean {
  return typeof navigator !== 'undefined' && 'bluetooth' in navigator
}

function judgeQuality(recent: number[]): SignalQuality | null {
  if (recent.length < 10) return null
  const implausible = recent.filter(
    (ms) => ms < RR_MIN_MS || ms > RR_MAX_MS,
  ).length
  const ratio = implausible / recent.length
  // 10% is the threshold at which the Python pipeline discards a whole segment,
  // so anything above it is already unusable rather than merely untidy.
  if (ratio > 0.1) return 'poor'
  if (ratio > 0.02) return 'fair'
  return 'good'
}

/**
 * The beat at `index` of the playback recording, or undefined once it runs out.
 *
 * Running out is reported rather than papered over. Looping would replay the
 * same stress response as though it had happened twice, and holding the last
 * value would feed a flat line into RMSSD — both would keep the demo running
 * while quietly describing something that never happened.
 */
function recordedInterval(index: number): number | undefined {
  return DEMO_RR_MS[index]
}

/**
 * @param simulate  Run without hardware, for `?dev=1`.
 *
 *   Needed because the moment this hook started speaking real Bluetooth, no part
 *   of the interface could be opened without physically wearing a strap — which
 *   blocks working on screens while the sensor is still on order, and leaves no
 *   fallback if it fails during a demo. The simulation is deliberately behind
 *   the URL flag rather than an automatic fallback: silently inventing beats
 *   when a sensor fails to connect would produce a complete, confident report
 *   about a person from data that describes nobody.
 */
export function useDeviceConnection(simulate = false): DeviceConnection {
  const [status, setStatus] = useState<ConnectionStatus>('idle')
  const [connected, setConnected] = useState<HeartDevice | null>(null)
  const [wornAt, setWornAtState] = useState<WearLocation | null>(null)
  const [bpm, setBpm] = useState<number | null>(null)
  const [sendsRrIntervals, setSendsRr] = useState<boolean | null>(null)
  const [rrIntervals, setRrIntervals] = useState<number[]>([])
  const [signalQuality, setSignalQuality] = useState<SignalQuality | null>(null)

  const deviceRef = useRef<BluetoothDevice | null>(null)

  const handleMeasurement = useCallback((event: Event) => {
    const characteristic = event.target as BluetoothRemoteGATTCharacteristic
    if (!characteristic.value) return

    const sample = parseHeartRateMeasurement(characteristic.value)
    setBpm(sample.bpm)
    setSendsRr((known) => known ?? sample.hasRrIntervals)

    if (sample.rrMs.length) {
      setRrIntervals((collected) => {
        const next = [...collected, ...sample.rrMs]
        setSignalQuality(judgeQuality(next.slice(-QUALITY_WINDOW)))
        return next
      })
    }
  }, [])

  /**
   * Web Bluetooth has no scan-then-pick step available to a page.
   *
   * The browser owns the chooser: `requestDevice` opens the operating system's
   * own dialog, and the page only ever learns about the one device the person
   * selected. So this connects directly rather than listing anything, and the
   * returned `devices` array holds at most that single choice — which keeps the
   * shape the screens were written against.
   *
   * It must also be called from a real click. A browser rejects a Bluetooth
   * request that a page makes on its own.
   */
  const scan = useCallback(async () => {
    if (simulate) {
      const entry = mockDiscoveredDevices[0]!
      setConnected(entry)
      setWornAtState(entry.wornAt)
      setSendsRr(true)
      setStatus('connected')
      return
    }
    if (!bluetoothAvailable()) return
    setStatus('scanning')

    try {
      const device = await navigator.bluetooth.requestDevice({
        filters: [{ services: ['heart_rate'] }],
      })

      const name = device.name ?? 'Sensor tanpa nama'
      const entry: HeartDevice = {
        id: device.id,
        name,
        wornAt: recogniseWearLocation(name),
      }

      deviceRef.current = device
      device.addEventListener('gattserverdisconnected', () => {
        setStatus('idle')
        setConnected(null)
        setBpm(null)
        setSignalQuality(null)
      })

      const server = await device.gatt?.connect()
      if (!server) throw new Error('GATT server unavailable')
      const service = await server.getPrimaryService('heart_rate')
      const characteristic = await service.getCharacteristic(
        'heart_rate_measurement',
      )
      characteristic.addEventListener(
        'characteristicvaluechanged',
        handleMeasurement,
      )
      await characteristic.startNotifications()

      setConnected(entry)
      // Only adopt a wear location we actually recognised. For an unknown
      // device this stays null and the screen asks.
      setWornAtState(entry.wornAt)
      setStatus('connected')
    } catch {
      // Covers the person closing the chooser, the device being out of range,
      // and the common case of another app already holding the one connection
      // most straps allow. None of these deserve a crash.
      setStatus('idle')
    }
  }, [handleMeasurement, simulate])

  // Feed the simulation, once connected. One beat at a time, as a real sensor
  // notifies, rather than in bursts — the quality check reads the last few
  // intervals and would see a different series if they arrived in clumps.
  //
  // A CHAINED TIMEOUT, NOT AN INTERVAL. Each wait is as long as the beat that
  // just played, divided by the speed factor, so the playback keeps the
  // recording's own rhythm: a fast stretch of the TSST arrives fast. A fixed
  // interval would flatten exactly the variation the whole system measures.
  useEffect(() => {
    if (!simulate || status !== 'connected') return

    // The played series is kept here rather than read back out of state.
    //
    // The first version computed the quality INSIDE the `setRrIntervals`
    // updater, which is where the live sensor path does it. That is already
    // questionable — an updater is meant to be pure — and here it broke
    // outright: React runs the updater when it chooses, so the quality set on
    // the final beat could land AFTER the end-of-recording signal and overwrite
    // it. The demo then ran out of recording while still reporting a good
    // signal, which is the exact failure this playback is supposed to make
    // visible. A test caught it.
    const played: number[] = []
    let timer = 0

    const emit = () => {
      const beat = recordedInterval(played.length)
      if (beat === undefined) {
        // The recording is finished. Say so, rather than inventing beats to
        // keep a demo looking alive.
        setSignalQuality('poor')
        setBpm(null)
        return
      }
      played.push(beat)
      setBpm(Math.round(60000 / beat))
      setRrIntervals([...played])
      setSignalQuality(judgeQuality(played.slice(-QUALITY_WINDOW)))
      timer = window.setTimeout(emit, beat / SIMULATION_SPEED)
    }

    emit()
    return () => window.clearTimeout(timer)
  }, [simulate, status])

  const disconnect = useCallback(() => {
    deviceRef.current?.gatt?.disconnect()
    deviceRef.current = null
    setConnected(null)
    setWornAtState(null)
    setBpm(null)
    setSignalQuality(null)
    setSendsRr(null)
    setStatus('idle')
  }, [])

  const clearIntervals = useCallback(() => setRrIntervals([]), [])

  const setWornAt = useCallback((location: WearLocation) => {
    setWornAtState(location)
  }, [])

  // Release the radio when the app closes. A strap left connected stays
  // unavailable to every other app until it times out.
  useEffect(() => () => { deviceRef.current?.gatt?.disconnect() }, [])

  return {
    isSupported: bluetoothAvailable(),
    status,
    devices: connected ? [connected] : [],
    connected,
    wornAt,
    signalQuality,
    bpm,
    sendsRrIntervals,
    rrIntervals,
    clearIntervals,
    scan: () => { void scan() },
    // The browser's own chooser already performed the selection, so there is
    // nothing left to choose between. Kept so the screens need no changes.
    connect: () => {},
    disconnect,
    setWornAt,
  }
}
