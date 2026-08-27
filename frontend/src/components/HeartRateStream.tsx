/**
 * HeartRateStream.tsx — the live pulse trace shown while the interview runs.
 *
 * ONE COLOUR, NO ZONES, NO WORDS ABOUT STRESS. The reasoning lives in
 * `lib/heartStream.ts`: this trace exists to show the sensor is alive, not to
 * tell the person how they are doing — that feedback would alter the very
 * measurement the session exists to take.
 */

import { streamPath } from '../lib/heartStream'

const WIDTH = 280
const HEIGHT = 48

export function HeartRateStream({ rrIntervals, bpm }: {
  rrIntervals: number[]
  bpm: number | null
}) {
  const path = streamPath(rrIntervals, WIDTH, HEIGHT)
  if (path === '') return null

  return (
    <div className="mt-3 rounded-lg bg-canvas px-3 py-2">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-ink-muted">Detak jantung</span>
        {bpm !== null && (
          <span className="text-sm font-semibold tabular-nums text-navy">
            {bpm} <span className="text-xs font-normal text-ink-muted">bpm</span>
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mt-1 h-12 w-full"
        aria-label="Grafik detak jantung berjalan"
        role="img"
      >
        <polyline
          points={path}
          fill="none"
          stroke="var(--color-navy)"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )
}
