/**
 * App.tsx — mounts the router.
 *
 * Nothing else belongs here. Anything shared across screens goes in
 * `app/AppLayout.tsx`, which is inside the router and can therefore read the
 * current mode and stage.
 */

import { RouterProvider } from 'react-router'
import { router } from './app/routes'

export default function App() {
  return <RouterProvider router={router} />
}
