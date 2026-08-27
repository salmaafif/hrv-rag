/**
 * ResponseRadar.tsx — the three-axis chart of how this session went.
 *
 * THE CAPTION IS PART OF THE COMPONENT, not decoration. A radar chart is read
 * as a personality profile whatever its axes are called — that is what the
 * shape means to anyone who has seen one before. This system produces an
 * indication of physiological pressure and explicitly not a judgement about a
 * person (Mandatory Rule #4), so the sentence that says which of the two this
 * is has to travel with the picture, not sit in a paragraph further down that a
 * screenshot would crop out.
 *
 * An axis this session could not measure is drawn at zero and NAMED as
 * unmeasured underneath. Leaving it out would silently reshape the polygon, and
 * a three-sided figure missing a side reads as a low score rather than as a gap
 * in the recording.
 */

import {
  Chart,
  Filler,
  LineElement,
  PointElement,
  RadialLinearScale,
  Tooltip,
  type ChartOptions,
} from 'chart.js'
import { Radar } from 'react-chartjs-2'
import type { Dimension } from '../lib/sessionInsights'

Chart.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip)

/** Read from the stylesheet so the chart cannot drift from the palette. */
const token = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim()

export function ResponseRadar({ dimensions }: { dimensions: Dimension[] }) {
  const navy = token('--color-navy') || '#16234d'
  const hairline = token('--color-hairline') || '#dde3ef'
  const muted = token('--color-ink-muted') || '#6b7591'

  const data = {
    labels: dimensions.map((d) => d.label),
    datasets: [
      {
        label: 'Sesi ini',
        data: dimensions.map((d) => d.value ?? 0),
        backgroundColor: 'rgba(22, 35, 77, 0.12)',
        borderColor: navy,
        borderWidth: 2,
        pointBackgroundColor: dimensions.map((d) =>
          d.value === null ? '#ffffff' : navy,
        ),
        pointBorderColor: navy,
        pointRadius: 4,
      },
    ],
  }

  const options: ChartOptions<'radar'> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        min: 0,
        max: 100,
        angleLines: { color: hairline },
        grid: { color: hairline },
        pointLabels: { color: navy, font: { size: 13, weight: 600 } },
        // The rings carry no meaning a person needs — the axes are shares of
        // this session, not a score anybody should read to the decimal — and
        // printing numbers around them invites exactly the cross-person
        // comparison the whole design avoids.
        ticks: { display: false, stepSize: 25 },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (item) => {
            const dimension = dimensions[item.dataIndex]!
            return dimension.meaning
          },
        },
      },
    },
  }

  return (
    <div>
      <div className="h-72" role="img"
           aria-label={dimensions
             .map((d) => `${d.label}: ${d.meaning}`)
             .join('. ')}>
        <Radar data={data} options={options} />
      </div>

      {/*
        The axis meanings sit under the chart they belong to, not in the panel
        beside it. Three one-word labels on a radar are a quiz otherwise — the
        first person to see this one asked what an axis meant, which is the only
        review a label ever really gets.
      */}
      <ul className="mt-4 space-y-1.5">
        {dimensions.map((dimension) => (
          <li key={dimension.key} className="text-sm">
            <span className="font-semibold text-navy">{dimension.label}</span>
            <span className="text-ink-muted">
              {' — '}
              {dimension.value === null ? dimension.unmeasured : dimension.meaning}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-xs" style={{ color: muted }}>
        Ini gambaran <strong>sesi tadi</strong>, bukan gambaran dirimu. Semuanya
        dihitung dari sesimu sendiri, tidak dibandingkan dengan siapa pun.
      </p>
    </div>
  )
}
