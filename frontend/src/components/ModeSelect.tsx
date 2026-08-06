/**
 * ModeSelect.tsx — the V1 / V2 / V3 picker in the header.
 *
 * Switching mode navigates to that mode's first stage rather than trying to
 * keep the current stage. The stages are not equivalent across modes — V3's
 * "sesi latihan" has no counterpart in V1 — and landing someone on a stage
 * whose prerequisites were never met would show an empty screen with no
 * explanation.
 *
 * The `?dev=1` flag is carried across, because losing the developer panel every
 * time you compare two modes would make it useless for the comparison it exists
 * to support.
 */

import { useLocation, useNavigate } from 'react-router'
import { MODES, MODE_IDS, type ModeId } from '../app/modes'

interface ModeSelectProps {
  current: ModeId
}

export function ModeSelect({ current }: ModeSelectProps) {
  const navigate = useNavigate()
  const { search } = useLocation()

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-ink-muted">Versi</span>
      <select
        value={current}
        onChange={(event) => {
          navigate(`/${event.target.value}/mulai${search}`)
        }}
        className="rounded-lg border border-hairline bg-surface px-3 py-1.5 text-sm font-semibold text-navy"
      >
        {MODE_IDS.map((id) => (
          <option key={id} value={id}>
            {MODES[id].label}
          </option>
        ))}
      </select>
    </label>
  )
}
