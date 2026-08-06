/**
 * StartPage.tsx — stage 1: choose where the heart data comes from.
 *
 * Stage 3 of the build lays out the columns only. The controls arrive in the
 * next stage, once there is device state for them to act on.
 */

import { Card } from '../components/Card'
import type { ModeDefinition } from '../app/modes'

interface StageProps {
  mode: ModeDefinition
}

export function StartPage({ mode }: StageProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <Card title={mode.runsInterview ? 'Siapkan perangkatmu' : 'Siapkan data'}>
        <p className="text-sm text-ink-muted">
          {mode.runsInterview
            ? 'Pakai heart rate monitor atau smartwatch, lalu sambungkan melalui Bluetooth sebelum mulai berlatih.'
            : 'Sambungkan perangkat lewat Bluetooth, atau unggah berkas rekaman interval RR.'}
        </p>
        <p className="mt-6 rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
          Pilihan sumber data dan modalitas ditambahkan di tahap berikutnya.
        </p>
      </Card>

      <Card title="Status koneksi">
        <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
          Daftar perangkat dan kualitas sinyal ditambahkan di tahap berikutnya.
        </p>
      </Card>
    </div>
  )
}
