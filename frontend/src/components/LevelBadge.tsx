/**
 * LevelBadge.tsx — the low / moderate / high marker.
 *
 * Always renders the word, never the colour alone. The three tints in this
 * palette are close enough in lightness that they are not distinguishable in
 * greyscale or under red-green colour blindness — measured, not assumed, in
 * `index.css`. The colour is reinforcement; the text is the signal.
 */

import { formatLevel } from '../lib/format'
import type { StressLevel } from '../types/api'

const STYLE: Record<StressLevel, string> = {
  low: 'bg-level-low-bg text-level-low',
  moderate: 'bg-level-moderate-bg text-level-moderate',
  high: 'bg-level-high-bg text-level-high',
}

export function LevelBadge({ level }: { level: StressLevel }) {
  return (
    <span
      className={
        'inline-block shrink-0 rounded-full px-3 py-1 text-xs font-semibold ' +
        STYLE[level]
      }
    >
      {formatLevel(level)}
    </span>
  )
}
