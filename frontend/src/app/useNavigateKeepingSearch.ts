/**
 * useNavigateKeepingSearch.ts — the imperative half of query-preserving navigation.
 *
 * Separate from the `<NavigateKeepingSearch>` component only because Fast
 * Refresh requires a module to export components or other things, not both.
 * The reasoning behind them is the same one, and lives in the component's file.
 */

import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router'
import type { NavigateOptions } from 'react-router'

export function useNavigateKeepingSearch() {
  const navigate = useNavigate()
  const { search } = useLocation()

  return useCallback(
    (to: string, options?: NavigateOptions) => {
      navigate(`${to}${search}`, options)
    },
    [navigate, search],
  )
}
