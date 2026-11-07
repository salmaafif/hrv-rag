/**
 * StartPage.tsx — stage 1: getting ready.
 *
 * The recording is made DURING the interview this app is about to run, so there
 * is nothing to upload yet. The file picker lives on a later screen, and the
 * interview can start with no sensor connected at all.
 *
 * The resting period is not set here either. The session screen runs it on its
 * own clock for a fixed two minutes, so there is nothing for the person to
 * decide, and asking would only make this screen longer.
 *
 * The wear location decides the modality, and the modality decides how much
 * confidence the reading earns. Nobody is asked about ECG or PPG — they are
 * asked where they wear the thing, which they cannot get wrong.
 */

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DevicePanel } from '../components/DevicePanel'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import type { StageContext } from '../app/stageContext'

const STEPS = [
  'Kenakan perangkat dengan pas.',
  'Pastikan Bluetooth di perangkatmu sudah aktif.',
  'Tekan tombol di bawah untuk mencari perangkat.',
]

export function StartPage({ device, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <Card title="Siapkan perangkatmu">
          <p className="text-sm text-ink-muted">
            Pakai heart rate monitor atau smartwatch, lalu sambungkan melalui
            Bluetooth sebelum mulai berlatih.
          </p>

          <ol className="mt-5 space-y-3">
            {STEPS.map((step, index) => (
              <li key={step} className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-canvas text-xs font-semibold text-ink-muted"
                >
                  {index + 1}
                </span>
                <span className="text-sm">{step}</span>
              </li>
            ))}
          </ol>

          <div className="mt-6">
            <Button
              full
              onClick={device.scan}
              disabled={device.status === 'scanning'}
            >
              {device.status === 'scanning'
                ? 'Mencari perangkat…'
                : 'Hubungkan Perangkat'}
            </Button>
          </div>

          <p className="mt-4 rounded-xl bg-canvas p-4 text-sm text-ink-muted">
            Tidak punya perangkat yang bisa disambungkan? Sesi latihan tetap
            bisa dijalankan. Rekam detak jantungmu dengan alatmu sendiri, lalu
            unggah berkasnya setelah sesi selesai.
          </p>
        </Card>

        {/*
          Consent to keep the recording, asked HERE — before anything records —
          and never pre-ticked. The wording states the three things consent law
          and decency both require: what is kept (the heart data), what for
          (research and module improvement), and what is not attached (their
          name — the module only ever receives an opaque session id, A1).
          The unticked state is a complete, respected answer: the session runs
          identically and nothing is stored.
        */}
        <Card className="p-4!">
          <label className="flex cursor-pointer items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-navy"
              checked={session.storeConsented}
              onChange={(event) => session.setStoreConsented(event.target.checked)}
            />
            <span className="text-ink-muted">
              Saya setuju data detak jantung sesi ini{' '}
              <span className="font-semibold text-navy">disimpan untuk riset</span>{' '}
              dan perbaikan modul. Tanpa nama — hanya rekaman denyut dan hasil
              analisisnya. Kalau tidak dicentang, sesi tetap jalan penuh dan
              tidak ada yang disimpan.
            </span>
          </label>
        </Card>

        <Button variant="accent" full onClick={() => navigate('/sesi')}>
          Mulai sesi latihan
        </Button>
      </div>

      <DevicePanel device={device} />
    </div>
  )
}
