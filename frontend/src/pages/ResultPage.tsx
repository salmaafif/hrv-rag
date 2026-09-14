/**
 * ResultPage.tsx — stage 3: what the analysis found.
 *
 * The result lives in memory, so opening this URL cold has nothing to show.
 * That redirects back to the start rather than rendering an empty shell, which
 * would look like the analysis had produced nothing.
 */

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { SessionResult } from '../components/SessionResult'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import {
  questionHeartRates,
  questionHeartRatesFromReadings,
} from '../lib/questionHeartRate'
import type { StageContext } from '../app/stageContext'

export function ResultPage({ device, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()
  const result = session.result

  if (result === null) {
    return <NavigateKeepingSearch to="/mulai" />
  }

  // Beat intervals when the device sent them; otherwise the watch's own
  // heart-rate reports, each placed with the offset from its own clock.
  const timeline = session.questionTimeline
  const heartRate =
    timeline === null
      ? null
      : device.rrIntervals.length
        ? questionHeartRates(device.rrIntervals, session.sessionOffsetSec, timeline)
        : questionHeartRatesFromReadings(
            device.bpmReadings,
            session.sessionBpmOffsetSec,
            timeline,
          )

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

      <SessionResult result={result} heartRate={heartRate} />

      <Button
        variant="accent"
        onClick={() => {
          session.restart()
          navigate('/mulai')
        }}
      >
        Latihan lagi
      </Button>
    </div>
  )
}
