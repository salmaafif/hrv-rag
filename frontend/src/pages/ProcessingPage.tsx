/**
 * ProcessingPage.tsx — the wait while the recording is analysed.
 *
 * Given a screen of its own rather than a spinner over the results, because the
 * wait is genuinely long: `docs/frontend_plan.md` section 6 warns that a free
 * host cold-starting scipy, numpy and neurokit2 can take 30 to 60 seconds. A
 * bare spinner for a minute reads as a hang, and whoever is demonstrating this
 * will reload the page halfway through.
 *
 * Two query parameters exist so the awkward outcomes can be looked at on
 * purpose rather than discovered by accident:
 *
 *   ?gagal=1     the analysis fails
 *   ?baseline=goyah   the resting period comes back too unsteady to trust
 */

import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import type { StageContext } from '../app/stageContext'

export function ProcessingPage({ mode, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()
  const [params] = useSearchParams()
  const startedRef = useRef(false)

  // Kick the analysis off once. The ref rather than the status guards against
  // React's development-mode double effect, which would otherwise fire two
  // requests before the first had moved the status off "idle".
  useEffect(() => {
    if (startedRef.current) return
    if (session.status !== 'idle') return
    startedRef.current = true
    session.run(mode, {
      devMode: params.get('dev') === '1',
      simulateError: params.get('gagal') === '1',
      simulateUnstableBaseline: params.get('baseline') === 'goyah',
    })
  }, [session, mode, params])

  useEffect(() => {
    if (session.status === 'done') {
      // `replace` so the back button from the results does not land on a
      // processing screen that would immediately re-run the analysis.
      navigate(`/${mode.id}/hasil`, { replace: true })
    }
  }, [session.status, mode.id, navigate])

  // Nothing to analyse — someone opened this URL directly.
  if (session.status === 'idle' && !session.isReady) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  if (session.status === 'error' && session.error) {
    return (
      <Card title="Analisis gagal">
        <p className="text-sm text-ink-muted">{session.error.message}</p>
        {session.error.serverDetail && (
          <p className="mt-2 rounded-lg bg-canvas px-3 py-2 font-mono text-xs text-ink-muted">
            {session.error.serverDetail}
          </p>
        )}
        <div className="mt-5 flex flex-wrap gap-3">
          {session.error.retryable && (
            <Button
              variant="accent"
              onClick={() => {
                startedRef.current = false
                session.reset()
              }}
            >
              Coba lagi
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => {
              // Clear the failure on the way out, not just the screen showing
              // it. Navigating away used to leave `status` on "error", so the
              // effect above refused to start anything the next time round: the
              // person picked a corrected file, pressed "Mulai analisis", and
              // was shown the OLD error with no retry button. On a
              // non-retryable failure that was the only exit, which made it a
              // dead end until the whole page was reloaded.
              startedRef.current = false
              session.reset()
              navigate(`/${mode.id}/mulai`)
            }}
          >
            Kembali ke awal
          </Button>
        </div>
      </Card>
    )
  }

  return (
    <Card title="Sedang menganalisis">
      <p className="text-sm text-ink-muted">
        Rekamanmu sedang diproses. Kalau server baru bangun dari kondisi idle,
        langkah ini bisa memakan waktu sampai satu menit — biarkan halaman ini
        terbuka.
      </p>

      <ol className="mt-5 space-y-2 text-sm text-ink-muted">
        <li>Membersihkan sinyal dan membuang denyut yang menyimpang</li>
        <li>Menghitung fitur dari periode tenang sebagai pembanding</li>
        <li>Menilai tiap bagian rekaman terhadap pembanding itu</li>
        <li>Menyusun penjelasan dalam bahasa sehari-hari</li>
      </ol>

      <div
        role="status"
        aria-live="polite"
        className="mt-6 h-1.5 w-full overflow-hidden rounded-full bg-canvas"
      >
        <span className="block h-full w-1/3 animate-pulse rounded-full bg-brand" />
        <span className="sr-only">Sedang menganalisis rekaman</span>
      </div>
    </Card>
  )
}
