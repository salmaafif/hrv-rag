/**
 * StageRouter.tsx — picks the screen for `/:mode/:stage`.
 *
 * One route with a switch rather than four sibling routes, so that every rule
 * about which stages exist for which mode lives in one readable place. The rule
 * that matters: `sesi` belongs to V3 alone, because only V3 runs the interview.
 * Reaching it in V1 or V2 is not an error the person made — it is a stale link
 * or a typed URL — so it redirects instead of showing a failure.
 */

import { Navigate, useOutletContext, useParams } from 'react-router'
import type { ModeDefinition, StageSegment } from './modes'
import { StartPage } from '../pages/StartPage'
import { SessionPage } from '../pages/SessionPage'
import { ProcessingPage } from '../pages/ProcessingPage'
import { ResultPage } from '../pages/ResultPage'

const STAGES: readonly StageSegment[] = ['mulai', 'sesi', 'proses', 'hasil']

function isStage(value: string | undefined): value is StageSegment {
  return STAGES.includes(value as StageSegment)
}

export function StageRouter() {
  const mode = useOutletContext<ModeDefinition>()
  const { stage } = useParams<{ stage: string }>()

  if (!isStage(stage)) return <Navigate to={`/${mode.id}/mulai`} replace />
  if (stage === 'sesi' && !mode.runsInterview) {
    return <Navigate to={`/${mode.id}/mulai`} replace />
  }

  switch (stage) {
    case 'mulai':
      return <StartPage mode={mode} />
    case 'sesi':
      return <SessionPage />
    case 'proses':
      return <ProcessingPage mode={mode} />
    case 'hasil':
      return <ResultPage mode={mode} />
  }
}
