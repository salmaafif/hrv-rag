/**
 * routes.tsx — the URL map.
 *
 * Every stage of the session has its own address. That was the point of taking
 * on a router at all: the back button works, and a result can be sent to a
 * supervisor as a link rather than as a description of which buttons to press.
 *
 * All redirects go through `NavigateKeepingSearch` so that `?dev=1` survives
 * being corrected — a redirect that silently drops the query makes the
 * developer panel look broken.
 *
 * Old links from the three-version demo (`/v3/hasil` and the like) fall through
 * to the start screen rather than to an error.
 */

import { createBrowserRouter } from 'react-router'
import { AppLayout } from './AppLayout'
import { ErrorScreen } from './ErrorScreen'
import { NavigateKeepingSearch } from './NavigateKeepingSearch'
import { StageRouter } from './StageRouter'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    // Without this, a crash inside any stage screen renders React Router's
    // bare fallback — which in a production build is close to a blank page.
    errorElement: <ErrorScreen />,
    children: [
      { index: true, element: <NavigateKeepingSearch to="/mulai" /> },
      { path: ':stage', element: <StageRouter /> },
    ],
  },
  {
    path: '*',
    element: <NavigateKeepingSearch to="/mulai" />,
  },
])
