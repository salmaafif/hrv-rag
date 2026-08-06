/**
 * StartPage.tsx — stage 1: where the heart data comes from.
 *
 * Two things on this screen are not decoration.
 *
 * The quiet period. Every number the system produces is a comparison against
 * this person's own resting state, so if the recording does not start calm
 * there is nothing meaningful to compare against. That is easy to forget and
 * impossible to repair afterwards, so it is stated here rather than in a
 * footnote on the results.
 *
 * The wear location. It decides the modality, and the modality decides how much
 * confidence the reading earns. The person is never asked about ECG or PPG —
 * they are asked where they wear the thing, which they cannot get wrong.
 *
 * None of the choices are held here: they belong to the session, which outlives
 * this screen and turns into the analysis request.
 */

import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DevicePanel } from '../components/DevicePanel'
import { wearLabel, type WearLocation } from '../types/device'
import type { StageContext } from '../app/stageContext'
import {
  BASELINE_MAX_MINUTES,
  BASELINE_MIN_MINUTES,
} from '../app/useSessionState'

const STEPS = [
  'Kenakan perangkat dengan pas.',
  'Pastikan Bluetooth di perangkatmu sudah aktif.',
  'Tekan tombol di bawah untuk mencari perangkat.',
]

const WEAR_CHOICES: WearLocation[] = ['chest', 'wrist']

export function StartPage({ mode, device, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <Card title={mode.runsInterview ? 'Siapkan perangkatmu' : 'Siapkan data'}>
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

          <div className="my-5 flex items-center gap-3 text-xs text-ink-muted">
            <span className="h-px flex-1 bg-hairline" />
            atau
            <span className="h-px flex-1 bg-hairline" />
          </div>

          <label className="block cursor-pointer rounded-xl border border-hairline bg-surface px-5 py-3 text-center text-sm font-semibold text-navy hover:bg-canvas">
            {session.fileName ?? 'Unggah berkas rekaman (CSV)'}
            <input
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={(event) => session.setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          {session.fileName !== null && session.fileWornAt === null && (
            <div className="mt-4 rounded-xl bg-level-moderate-bg p-4">
              <p className="mb-3 text-sm font-semibold text-level-moderate">
                Rekaman ini diambil dengan alat yang dipakai di mana?
              </p>
              <div className="space-y-2">
                {WEAR_CHOICES.map((location) => (
                  <Button
                    key={location}
                    variant="outline"
                    full
                    onClick={() => session.setFileWornAt(location)}
                  >
                    {wearLabel(location)}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {session.fileName !== null && session.fileWornAt !== null && (
            <p className="mt-3 rounded-lg bg-canvas px-4 py-3 text-sm text-ink-muted">
              {wearLabel(session.fileWornAt)}
            </p>
          )}
        </Card>

        <Card title="Periode tenang di awal">
          <p className="text-sm text-ink-muted">
            Beberapa menit pertama rekaman dipakai sebagai pembanding untuk
            seluruh sesi. Selama menit-menit itu, duduklah diam dan bernapas
            biasa. Kalau bagian ini tidak tenang, sisa hasilnya kehilangan
            acuan.
          </p>

          <label className="mt-4 flex items-center gap-3 text-sm">
            <span className="text-ink-muted">Lama periode tenang</span>
            <input
              type="number"
              min={BASELINE_MIN_MINUTES}
              max={BASELINE_MAX_MINUTES}
              value={session.baselineMinutes}
              onChange={(event) =>
                session.setBaselineMinutes(Number(event.target.value))
              }
              className="w-20 rounded-lg border border-hairline px-3 py-1.5 text-sm font-semibold text-navy"
            />
            <span className="text-ink-muted">menit</span>
          </label>
        </Card>

        <Button
          variant="accent"
          full
          disabled={!session.isReady}
          onClick={() => navigate(`/${mode.id}/${mode.nextAfterStart}`)}
        >
          {mode.runsInterview ? 'Mulai sesi latihan' : 'Mulai analisis'}
        </Button>

        {!session.isReady && (
          <p className="text-center text-sm text-ink-muted">
            Sambungkan perangkat atau unggah berkas dulu, lalu beri tahu di mana
            alatnya dipakai.
          </p>
        )}
      </div>

      <DevicePanel device={device} />
    </div>
  )
}
