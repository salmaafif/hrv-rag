/**
 * StressTimeline.tsx — pressure across the interview, question by question.
 *
 * The one thing the per-question cards cannot show: shape. Cards are read one
 * at a time, so a session that climbed steadily and one that spiked once in the
 * middle look identical scrolling past them. That difference is the actionable
 * part — it decides whether somebody should practise pacing or practise one
 * kind of question.
 *
 * THE Y AXIS IS LABELLED IN WORDS, not numbers. The three labels are ordered,
 * but nothing measured says "high" is exactly twice "moderate", so printing 0,
 * 50 and 100 up the side would invent a precision the scale does not have. It
 * would also put a score on screen, which K4 keeps away from a user.
 */

import {
  CategoryScale,
  Chart,
  Filler,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartOptions,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { formatLevel } from '../lib/format'
import type { TimelinePoint } from '../lib/sessionInsights'
import type { StressLevel } from '../types/api'

Chart.register(CategoryScale, LinearScale, PointElement, LineElement, Filler,
               Tooltip)

const token = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim()

const LEVEL_TOKEN: Record<StressLevel, string> = {
  low: '--color-level-low',
  moderate: '--color-level-moderate',
  high: '--color-level-high',
}

export function StressTimeline({ points }: { points: TimelinePoint[] }) {
  const navy = token('--color-navy') || '#16234d'
  const hairline = token('--color-hairline') || '#dde3ef'
  const muted = token('--color-ink-muted') || '#6b7591'

  const data = {
    labels: points.map((point) => point.label),
    datasets: [
      {
        data: points.map((point) => point.pressure),
        borderColor: navy,
        borderWidth: 2,
        tension: 0.3,
        fill: true,
        backgroundColor: 'rgba(22, 35, 77, 0.06)',
        // Each point wears its own label's colour, so the line and the badges
        // on the cards below cannot tell different stories.
        pointBackgroundColor: points.map(
          (point) => token(LEVEL_TOKEN[point.level]) || navy,
        ),
        pointBorderColor: points.map(
          (point) => token(LEVEL_TOKEN[point.level]) || navy,
        ),
        pointRadius: 5,
        pointHoverRadius: 7,
      },
    ],
  }

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { grid: { display: false }, ticks: { color: muted } },
      y: {
        min: 0,
        max: 100,
        grid: { color: hairline },
        ticks: {
          stepSize: 50,
          color: muted,
          callback: (value) =>
            value === 0 ? 'Rendah' : value === 50 ? 'Sedang' : 'Tinggi',
        },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => `Pertanyaan ${points[items[0]!.dataIndex]!.number}`,
          label: (item) => formatLevel(points[item.dataIndex]!.level),
        },
      },
    },
  }

  return (
    <div className="h-56" role="img"
         aria-label={points
           .map((p) => `Pertanyaan ${p.number}: ${formatLevel(p.level)}`)
           .join('. ')}>
      <Line data={data} options={options} />
    </div>
  )
}
