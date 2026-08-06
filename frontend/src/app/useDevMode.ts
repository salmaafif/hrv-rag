/**
 * useDevMode.ts — the developer panel switch.
 *
 * `docs/frontend_plan.md` says the technical numbers — delta_rmssd_pct, score,
 * evidence — must not reach the end user, and belong in a developer view. This
 * hook is that view's on/off switch.
 *
 * The state lives in the URL as `?dev=1` rather than in React state or
 * localStorage. Three reasons, in order of how much they matter here:
 *
 *   - it survives a reload, so a screen being inspected during the defence does
 *     not silently revert to the user view halfway through;
 *   - it can be sent to someone — "look at this with ?dev=1" is a complete
 *     instruction, which matters because the whole point of choosing a router
 *     was shareable URLs;
 *   - it is visible. A hidden developer mode that persists in localStorage is
 *     exactly how technical numbers end up in a screenshot meant for a user.
 */

import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

const PARAM = 'dev'

export function useDevMode(): [boolean, (enabled: boolean) => void] {
  const [params, setParams] = useSearchParams()
  const enabled = params.get(PARAM) === '1'

  const setEnabled = useCallback(
    (next: boolean) => {
      const updated = new URLSearchParams(params)
      if (next) updated.set(PARAM, '1')
      else updated.delete(PARAM)
      // `replace` so that toggling the panel does not fill the back button's
      // history with states the person never navigated to.
      setParams(updated, { replace: true })
    },
    [params, setParams],
  )

  return [enabled, setEnabled]
}
