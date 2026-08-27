/**
 * QuestionHeartRateChart.tsx — one question's stretch of the heart recording.
 *
 * Same guardrails as the live trace: one neutral colour, no zones, no words
 * about stress. The verdict already sits right above this chart as a badge —
 * the curve's job is to show WHAT the heart did during that answer, not to
 * repeat the judgement in colour.
 *
 * The y-scale is passed in, never computed here: every question's panel shares
 * one scale (see `lib/questionHeartRate.ts`), because "this answer ran higher
 * than that one" is the entire comparison being offered.
 */

import type { QuestionHeartRate } from '../lib/questionHeartRate'

const WIDTH = 560
const HEIGHT = 96

export function QuestionHeartRateChart({ series, domain }: {
  series: QuestionHeartRate
  domain: { min: number; max: number }
}) {
  const span = Math.max(1, domain.max - domain.min)
  const duration = Math.max(1, series.points[series.points.length - 1]!.t)

  const path = series.points
    .map((p) => {
      const x = (p.t / duration) * WIDTH
      const y = HEIGHT - ((p.bpm - domain.min) / span) * HEIGHT
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <div className="mt-3 rounded-lg bg-canvas px-3 py-2">
      <div className="flex items-baseline justify-between text-xs text-ink-muted">
        <span>Detak jantung selama menjawab</span>
        <span>
          rata-rata{' '}
          <span className="font-semibold tabular-nums text-navy">
            {Math.round(series.meanBpm)}
          </span>{' '}
          bpm
        </span>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mt-1 h-24 w-full"
        role="img"
        aria-label={`Detak jantung selama menjawab, rata-rata ${Math.round(series.meanBpm)} bpm`}
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
      <div className="flex justify-between text-[10px] text-ink-muted">
        <span>{Math.round(domain.min)} bpm</span>
        <span>{Math.round(duration)} detik</span>
        <span>{Math.round(domain.max)} bpm</span>
      </div>
    </div>
  )
}
