/**
 * ResultPage.tsx — stage 3: what the analysis found.
 *
 * V2 and V3 share this screen unchanged, since both report one result per
 * question from the same endpoint. V1 reports one result per minute and gets
 * the timeline chart instead — the chart drawn in the Figma results frame
 * actually belongs here, because only the timeline endpoint returns the
 * continuous series it needs.
 *
 * The result lives in memory, so opening this URL cold has nothing to show.
 * That redirects back to the start of the mode rather than rendering an empty
 * shell, which would look like the analysis had produced nothing.
 */

import { Card } from '../components/Card'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import type { StageContext } from '../app/stageContext'

export function ResultPage({ mode, session }: StageContext) {
  const result = session.result
  if (result === null) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  // Bound to a local so the narrowing survives; reading `session.result` again
  // would widen it back to the union on every access.
  const perQuestion = 'questions' in result
  const ringkasan = 'questions' in result
    ? result.narrative.ringkasan_sesi
    : result.narrative.ringkasan

  return (
    <div className="space-y-6">
      {!result.baseline.is_stable && (
        <Card className="border-level-moderate/40 bg-level-moderate-bg">
          <p className="text-sm font-semibold text-level-moderate">
            Periode tenang di awal rekaman kurang stabil
          </p>
          <p className="mt-1 text-sm text-level-moderate">
            {result.baseline.warning}
          </p>
          <p className="mt-2 text-sm text-level-moderate">
            Seluruh penilaian di bawah membandingkan ke periode itu, jadi
            bacalah hasilnya dengan lebih hati-hati.
          </p>
        </Card>
      )}

      <Card eyebrow="Ringkasan sesi kamu">
        <p className="text-lg font-semibold text-navy">{ringkasan}</p>
      </Card>

      <Card title={perQuestion ? 'Tekanan per pertanyaan' : 'Tekanan per menit'}>
        <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
          {perQuestion
            ? 'Daftar pertanyaan ditambahkan di tahap berikutnya.'
            : 'Grafik linimasa ditambahkan di tahap berikutnya.'}
        </p>
      </Card>
    </div>
  )
}
