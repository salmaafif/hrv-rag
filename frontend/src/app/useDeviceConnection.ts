/**
 * useDeviceConnection.ts — connecting to a heart sensor.
 *
 * The scan and the heart rate are currently mocked; the browser capability
 * check is not. That split is deliberate. Web Bluetooth only exists in
 * Chromium browsers and only over HTTPS or localhost, and finding that out on
 * the day of the defence would be an expensive surprise — so the real check
 * runs from the start, even though nothing is connected to yet.
 *
 * Everything the rest of the app needs is returned from here, so the day the
 * real Web Bluetooth calls replace the mocked ones, no screen has to change.
 */

import { useCallback, useEffect, useState } from 'react'
import { MOCK_SCAN_MS, mockDiscoveredDevices } from '../mocks/devices'
import type { HeartDevice, WearLocation } from '../types/device'

export type ConnectionStatus = 'idle' | 'scanning' | 'listed' | 'connected'

/**
 * How trustworthy the incoming signal looks.
 *
 * Kept separate from the stress result on purpose: this describes the sensor,
 * not the person. A poor signal is a reason to fix the strap, not a finding
 * about how someone is coping.
 */
export type SignalQuality = 'good' | 'fair' | 'poor'

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
  scan: () => void
  connect: (deviceId: string) => void
  disconnect: () => void
  setWornAt: (location: WearLocation) => void
}

function bluetoothAvailable(): boolean {
  return typeof navigator !== 'undefined' && 'bluetooth' in navigator
}

export function useDeviceConnection(): DeviceConnection {
  const [status, setStatus] = useState<ConnectionStatus>('idle')
  const [devices, setDevices] = useState<HeartDevice[]>([])
  const [connected, setConnected] = useState<HeartDevice | null>(null)
  const [wornAt, setWornAtState] = useState<WearLocation | null>(null)
  const [bpm, setBpm] = useState<number | null>(null)

  const scan = useCallback(() => {
    setStatus('scanning')
    window.setTimeout(() => {
      setDevices(mockDiscoveredDevices)
      setStatus('listed')
    }, MOCK_SCAN_MS)
  }, [])

  const connect = useCallback(
    (deviceId: string) => {
      const device = devices.find((candidate) => candidate.id === deviceId)
      if (!device) return
      setConnected(device)
      // Only adopt a wear location we actually recognised. For an unknown
      // device this stays null and the screen asks.
      setWornAtState(device.wornAt)
      setStatus('connected')
    },
    [devices],
  )

  const disconnect = useCallback(() => {
    setConnected(null)
    setWornAtState(null)
    setBpm(null)
    setStatus(devices.length > 0 ? 'listed' : 'idle')
  }, [devices.length])

  const setWornAt = useCallback((location: WearLocation) => {
    setWornAtState(location)
  }, [])

  // Simulated heart rate while connected. Wanders gently around a resting value
  // instead of holding a constant, so it is visibly live rather than a label.
  useEffect(() => {
    if (status !== 'connected') return
    setBpm(72)
    const timer = window.setInterval(() => {
      setBpm((previous) => {
        const base = previous ?? 72
        const drift = Math.round((Math.random() - 0.5) * 4)
        return Math.min(84, Math.max(62, base + drift))
      })
    }, 1200)
    return () => window.clearInterval(timer)
  }, [status])

  return {
    isSupported: bluetoothAvailable(),
    status,
    devices,
    connected,
    wornAt,
    signalQuality: status === 'connected' ? 'good' : null,
    bpm,
    scan,
    connect,
    disconnect,
    setWornAt,
  }
}
