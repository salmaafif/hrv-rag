/**
 * StartPage.tsx — stage 1: getting ready.
 *
 * What this screen offers depends on when the recording comes into being.
 *
 * V1 and V2 analyse a recording that already exists, made before anyone opened
 * this app, so their file picker belongs here. V3 records DURING the interview
 * it is about to run, so there is nothing to upload yet — its file picker lives
 * on a later screen, and V3 can start with no sensor connected at all.
 *
 * The quiet period is stated here rather than in a footnote on the results,
 * because every number the system produces is a comparison against this
 * person's own resting state. If the recording does not start calm there is
 * nothing meaningful to compare against, and that cannot be repaired
 * afterwards.
 *
 * The wear location decides the modality, and the modality decides how much
 * confidence the reading earns. Nobody is asked about ECG or PPG — they are
 * asked where they wear the thing, which they cannot get wrong.
 */

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DevicePanel } from '../components/DevicePanel'
import { RecordingUpload } from '../components/RecordingUpload'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import {
  BASELINE_MAX_MINUTES,
  BASELINE_MIN_MINUTES,
} from '../app/useSessionState'
import type { StageContext } from '../app/stageContext'

const STEPS = [
  'Kenakan perangkat dengan pas.',
  'Pastikan Bluetooth di perangkatmu sudah aktif.',
  'Tekan tombol di bawah untuk mencari perangkat.',
]

export function StartPage({ mode, device, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()

  // V3 can begin without a sensor: the recording is made on the person's own
  // device and handed over afterwards. V1 and V2 have nothing to analyse until
  // a source exists, so their button stays locked until it does.
  const canProceed = mode.runsInterview || session.isReady

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <Card title={mode.runsInterview ? 'Siapkan perangkatmu' : 'Siapkan data'}>
          <p className="text-sm text-ink-muted">
            {mode.runsInterview
              ? 'Pakai heart rate monitor atau smartwatch, lalu sambungkan melalui Bluetooth sebelum mulai berlatih.'
              : 'Sambungkan perangkat lewat Bluetooth, atau unggah berkas rekaman yang sudah kamu punya.'}
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

          {mode.runsInterview ? (
            <p className="mt-4 rounded-xl bg-canvas p-4 text-sm text-ink-muted">
              Tidak punya perangkat yang bisa disambungkan? Sesi latihan tetap
              bisa dijalankan. Rekam detak jantungmu dengan alatmu sendiri, lalu
              unggah berkasnya setelah sesi selesai.
            </p>
          ) : (
            <>
              <div className="my-5 flex items-center gap-3 text-xs text-ink-muted">
                <span className="h-px flex-1 bg-hairline" />
                atau
                <span className="h-px flex-1 bg-hairline" />
              </div>
              <RecordingUpload session={session} />
            </>
          )}
        </Card>

        {/*
          Only the upload modes ask about the resting period.

          V3 runs it on its own clock for a fixed two minutes, so there is
          nothing for the person to set and nothing they need to understand
          before pressing start. Explaining why a baseline exists is our
          reasoning, not their task — and the session screen says the one thing
          they actually have to do, at the moment they have to do it.

          V1 and V2 are different: those recordings were made outside the app, so
          only the person knows how much of the file is quiet. The number below
          is what tells the backend where the baseline ends. Fixing it would
          silently mislabel the rest of a longer quiet period as interview data.
        */}
        {!mode.runsInterview && (
          <Card title="Periode tenang di awal">
            <p className="text-sm text-ink-muted">
              Beberapa menit pertama rekaman dipakai sebagai pembanding untuk
              seluruh sesi. Duduk diam dan bernapas biasa selama menit-menit itu{' '}
              <strong>di awal rekaman</strong>. Kalau bagian ini tidak tenang,
              sisa hasilnya kehilangan acuan.
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
        )}

        <Button
          variant="accent"
          full
          disabled={!canProceed}
          onClick={() => navigate(`/${mode.id}/${mode.nextAfterStart}`)}
        >
          {mode.runsInterview ? 'Mulai sesi latihan' : 'Mulai analisis'}
        </Button>

        {!canProceed && (
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
