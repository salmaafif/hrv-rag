/**
 * ResultPage.tsx — stage 3: what the analysis found.
 *
 * V2 and V3 share this screen unchanged, since both report one result per
 * question from the same endpoint. V1 reports one result per minute and gets
 * the timeline chart instead — the chart drawn in the Figma results frame
 * actually belongs here, because only the timeline endpoint returns the
 * continuous series it needs.
 */

import { Card } from '../components/Card'
import type { ModeDefinition } from '../app/modes'

interface StageProps {
  mode: ModeDefinition
}

export function ResultPage({ mode }: StageProps) {
  const perQuestion = mode.endpoint.endsWith('session')

  return (
    <div className="space-y-6">
      <Card eyebrow="Ringkasan sesi kamu">
        <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
          Kalimat ringkasan dari LLM ditambahkan di tahap berikutnya.
        </p>
      </Card>

      <Card title={perQuestion ? 'Tekanan per pertanyaan' : 'Tekanan per menit'}>
        <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
          {perQuestion
            ? 'Daftar pertanyaan dengan tingkat tekanan, penjelasan, dan catatan pemulihan.'
            : 'Grafik linimasa per menit sepanjang rekaman.'}
        </p>
      </Card>

      <Card title="Rekomendasi latihan">
        <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
          Saran dari LLM ditambahkan di tahap berikutnya.
        </p>
      </Card>
    </div>
  )
}
