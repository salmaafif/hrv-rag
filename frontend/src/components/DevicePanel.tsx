/**
 * DevicePanel.tsx — the right column: what is connected and whether it reads.
 *
 * Two things here are deliberate.
 *
 * The heart rate is shown as a bare number with no judgement attached. The
 * Figma frame paired it with a "mulai tegang" badge; that badge is gone. Telling
 * someone mid-session that they are getting tense changes how tense they are,
 * which would leave the measurement partly caused by the screen reporting it.
 * The number stays because it is the only evidence the sensor is still reading.
 *
 * When a device is not recognised, the panel asks where it is worn rather than
 * assuming. That answer decides the modality, and the modality decides how much
 * confidence the whole session's reading is given.
 */

import { Button } from './Button'
import { Card } from './Card'
import { wearLabel, type WearLocation } from '../types/device'
import type { DeviceConnection } from '../app/useDeviceConnection'

const QUALITY_LABEL: Record<'good' | 'fair' | 'poor', string> = {
  good: 'Baik',
  fair: 'Cukup',
  poor: 'Kurang',
}

const WEAR_CHOICES: WearLocation[] = ['chest', 'wrist']

export function DevicePanel({ device }: { device: DeviceConnection }) {
  return (
    <Card title="Status koneksi">
      {!device.isSupported && (
        <p className="mb-4 rounded-lg bg-level-moderate-bg p-3 text-sm text-level-moderate">
          Peramban ini tidak mendukung sambungan Bluetooth. Pakai Chrome atau
          Edge, atau unggah berkas rekaman sebagai gantinya.
        </p>
      )}

      <p className="mb-2 text-xs font-semibold tracking-wider text-ink-muted uppercase">
        Perangkat terdeteksi
      </p>

      {device.devices.length === 0 ? (
        <p className="rounded-lg bg-canvas px-3 py-3 text-sm text-ink-muted">
          {device.status === 'scanning'
            ? 'Sedang mencari perangkat…'
            : 'Belum ada. Tekan tombol pencarian di sebelah kiri.'}
        </p>
      ) : (
        <ul className="space-y-2">
          {device.devices.map((candidate) => {
            const isConnected = device.connected?.id === candidate.id
            return (
              <li
                key={candidate.id}
                className={
                  'flex items-center justify-between gap-3 rounded-xl px-4 py-3 ' +
                  (isConnected ? 'bg-level-low-bg' : 'bg-canvas')
                }
              >
                <span className="text-sm font-semibold text-navy">
                  {candidate.name}
                </span>
                {isConnected ? (
                  <span className="rounded-full bg-level-low px-3 py-1 text-xs font-semibold text-white">
                    Terhubung
                  </span>
                ) : (
                  <Button
                    variant="accent"
                    className="px-3 py-1.5 text-xs"
                    onClick={() => device.connect(candidate.id)}
                  >
                    Hubungkan
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {device.connected && (
        <>
          {device.wornAt === null ? (
            <div className="mt-4 rounded-xl bg-level-moderate-bg p-4">
              <p className="text-sm font-semibold text-level-moderate">
                Perangkat ini belum kami kenali
              </p>
              <p className="mt-1 mb-3 text-sm text-level-moderate">
                Di mana kamu memakainya? Jawaban ini menentukan seberapa jauh
                hasilnya bisa diandalkan.
              </p>
              <div className="space-y-2">
                {WEAR_CHOICES.map((location) => (
                  <Button
                    key={location}
                    variant="outline"
                    full
                    className="text-left"
                    onClick={() => device.setWornAt(location)}
                  >
                    {wearLabel(location)}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-4 rounded-lg bg-canvas px-4 py-3 text-sm text-ink-muted">
              {wearLabel(device.wornAt)}
            </p>
          )}

          {device.signalQuality && (
            <p className="mt-3 flex items-center justify-between rounded-lg bg-canvas px-4 py-3 text-sm">
              <span className="text-ink-muted">Kualitas sinyal</span>
              <span className="font-semibold text-navy">
                {QUALITY_LABEL[device.signalQuality]}
              </span>
            </p>
          )}

          {device.bpm !== null && (
            <div className="mt-3 rounded-xl bg-level-low-bg px-4 py-4">
              <p className="text-sm text-level-low">Detak jantung terdeteksi</p>
              <p className="text-level-low">
                <span className="text-3xl font-bold">{device.bpm}</span>
                <span className="ml-1 text-sm font-semibold">bpm</span>
              </p>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
