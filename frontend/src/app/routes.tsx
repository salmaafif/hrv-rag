/**
 * routes.tsx — the URL map.
 *
 * Every stage of every mode has its own address. That was the point of taking
 * on a router at all: the back button works, and a result can be sent to a
 * supervisor as a link rather than as a description of which buttons to press.
 *
 * One consequence to know about while the data is still mocked: opening a
 * result URL directly works today because the fixtures are imported, but once
 * a real analysis is involved the result will live in memory and a cold load of
 * `/v2/hasil` will have nothing to show. That case gets handled when the API is
 * wired up — it redirects back to the start of the mode rather than rendering
 * an empty screen.
 */

import { createBrowserRouter, Navigate } from 'react-router'
import { AppLayout } from './AppLayout'
import { StageRouter } from './StageRouter'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/v1/mulai" replace />,
  },
  {
    path: '/:mode',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="mulai" replace /> },
      { path: ':stage', element: <StageRouter /> },
    ],
  },
  {
    // Anything else, including a mistyped mode, lands on the first screen.
    path: '*',
    element: <Navigate to="/v1/mulai" replace />,
  },
])
