/**
 * NavigateKeepingSearch.tsx — a redirect that does not throw the query away.
 *
 * Plain `<Navigate to="/v1/mulai" />` and plain `navigate('/v1/proses')` each
 * replace the whole location, search string included. That quietly defeats
 * `?dev=1`: turn the developer panel on, press the button that starts the
 * analysis, and the panel is off again on the next screen — which looks like
 * the panel is broken rather than like the link was rewritten. The same applies
 * to the `?gagal=1` and `?baseline=goyah` switches used to reach the awkward
 * outcomes on purpose.
 *
 * Every move in this app goes through here or through
 * `useNavigateKeepingSearch`, so it cannot be right in one place and wrong in
 * another.
 */

import { Navigate, useLocation } from 'react-router'

interface NavigateKeepingSearchProps {
  /** Path to go to. The current query string is appended to it. */
  to: string
}

export function NavigateKeepingSearch({ to }: NavigateKeepingSearchProps) {
  const { search } = useLocation()
  return <Navigate to={`${to}${search}`} replace />
}
