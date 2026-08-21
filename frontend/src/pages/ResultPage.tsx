/**
 * ResultPage.tsx — stage 3: what the analysis found.
 *
 * Two shapes come back from the two endpoints, so this page picks between two
 * views. V2 and V3 share `SessionResult` unchanged, since both report one
 * result per question from the same endpoint. V1's timeline view arrives next.
 *
 * The result lives in memory, so opening this URL cold has nothing to show.
 * That redirects back to the start of the mode rather than rendering an empty
 * shell, which would look like the analysis had produced nothing.
 */

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { SessionResult } from '../components/SessionResult'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import type { StageContext } from '../app/stageContext'

export function ResultPage({ mode, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()
  const result = session.result

  if (result === null) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  return (
    <div className="space-y-6">
      {!result.meta.trustworthy && (
        <Card className="border-level-high/40 bg-level-high-bg">
          <p className="text-sm font-semibold text-level-high">
            Penjelasan di bawah belum dapat dipercaya sepenuhnya
          </p>
          <p className="mt-1 text-sm text-level-high">
            Pemeriksaan otomatis menemukan kalimat yang tidak didukung data.
            Tingkat tekanannya sendiri tetap sah — itu dari aturan, bukan LLM.
          </p>
        </Card>
      )}

      {'questions' in result ? (
        <SessionResult result={result} />
      ) : (
        <Card title="Tekanan per menit">
          <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
            Grafik linimasa ditambahkan di tahap berikutnya.
          </p>
        </Card>
      )}

      <Button
        variant="accent"
        onClick={() => {
          session.restart()
          navigate(`/${mode.id}/mulai`)
        }}
      >
        Latihan lagi
      </Button>
    </div>
  )
}
