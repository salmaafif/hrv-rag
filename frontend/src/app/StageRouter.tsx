/**
 * StageRouter.tsx — picks the screen for `/:stage`.
 *
 * One route with a switch rather than five sibling routes, so the list of
 * screens lives in one readable place. An unknown stage is a stale link or a
 * typed URL, not an error the person made, so it redirects instead of showing a
 * failure.
 */

import { useOutletContext, useParams } from 'react-router'
import { isStage } from './stages'
import type { StageContext } from './stageContext'
import { NavigateKeepingSearch } from './NavigateKeepingSearch'
import { StartPage } from '../pages/StartPage'
import { SessionPage } from '../pages/SessionPage'
import { UploadPage } from '../pages/UploadPage'
import { ProcessingPage } from '../pages/ProcessingPage'
import { ResultPage } from '../pages/ResultPage'

export function StageRouter() {
  const context = useOutletContext<StageContext>()
  const { stage } = useParams<{ stage: string }>()

  if (!isStage(stage)) {
    return <NavigateKeepingSearch to="/mulai" />
  }

  switch (stage) {
    case 'mulai':
      return <StartPage {...context} />
    case 'sesi':
      return <SessionPage {...context} />
    case 'unggah':
      return <UploadPage {...context} />
    case 'proses':
      return <ProcessingPage {...context} />
    case 'hasil':
      return <ResultPage {...context} />
  }
}
