/**
 * ProcessingPage.tsx — the wait while the recording is analysed.
 *
 * Given a screen of its own rather than a spinner over the results, because the
 * wait is genuinely long: `docs/frontend_plan.md` section 6 warns that a free
 * host cold-starting scipy, numpy and neurokit2 can take 30 to 60 seconds. A
 * bare spinner for a minute reads as a hang, and someone demonstrating this in
 * front of an examiner will reload the page.
 */

import { Card } from '../components/Card'
import type { ModeDefinition } from '../app/modes'

interface StageProps {
  mode: ModeDefinition
}

export function ProcessingPage({ mode }: StageProps) {
  return (
    <Card title="Sedang menganalisis">
      <p className="text-sm text-ink-muted">
        Rekaman sedang diproses lewat <code>{mode.endpoint}</code>.
      </p>
      <p className="mt-6 rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
        Rincian kemajuan per tahap ditambahkan bersama sambungan API.
      </p>
    </Card>
  )
}
