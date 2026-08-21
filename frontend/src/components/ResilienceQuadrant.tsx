/**
 * ResilienceQuadrant.tsx — Ketahanan, as the two things it is made of.
 *
 * REPLACES THE RADAR, and not for cosmetic reasons. The radar plotted Calm and
 * Recovery beside a third axis that had to exist for the shape to close, and
 * Ketahanan — the thing the design document promised as one of three outputs —
 * appeared nowhere on screen under that name. Here the picture IS Ketahanan:
 * its two axes are reaction size and recovery speed, which is exactly how
 * `resilience_quadrant()` defines it on the Python side.
 *
 * NO DOT, THE WHOLE CELL LIGHTS UP. A dot would place the session at a point,
 * and a point is a precision nobody measured — the backend reports which of four
 * cells the session fell in, not where inside it. Highlighting the cell says
 * precisely what is known and nothing more. It also removes the temptation to
 * read coordinates off the axes, which is the readback K4 exists to prevent.
 *
 * NO BEST CORNER. All four cells carry the same neutral treatment, and the
 * occupied one differs by tint alone rather than by a colour that ranks it.
 * Mandatory Rule #4 puts this system on the side of describing a physiological
 * response, not grading a person; a green corner and a red corner would grade,
 * whatever the caption underneath said. "Reaksi besar, pulih cepat" is a
 * description of what a body did for an hour, not a verdict on who it belongs
 * to.
 */

import type { ResilienceCell } from '../lib/sessionInsights'

/** The four cells in reading order: top row first, left to right. */
const CELLS: ReadonlyArray<ResilienceCell & { label: string }> = [
  { reaction: 'kecil', recovery: 'cepat', label: 'Reaksi kecil, pulih cepat' },
  { reaction: 'besar', recovery: 'cepat', label: 'Reaksi besar, pulih cepat' },
  { reaction: 'kecil', recovery: 'lambat', label: 'Reaksi kecil, pulih lambat' },
  { reaction: 'besar', recovery: 'lambat', label: 'Reaksi besar, pulih lambat' },
]

export function ResilienceQuadrant({ cell }: { cell: ResilienceCell | null }) {
  const active = CELLS.find(
    (c) => cell && c.reaction === cell.reaction && c.recovery === cell.recovery,
  )

  return (
    <div>
      <div className="flex gap-3">
        {/* Vertical axis, read bottom-up like the grid it labels. */}
        <div className="flex w-6 shrink-0 flex-col items-center justify-between py-1">
          <span className="text-xs whitespace-nowrap text-ink-muted [writing-mode:vertical-rl] rotate-180">
            pulih cepat
          </span>
          <span className="text-xs whitespace-nowrap text-ink-muted [writing-mode:vertical-rl] rotate-180">
            pulih lambat
          </span>
        </div>

        <div className="flex-1">
          <div
            role="img"
            aria-label={
              active
                ? `Ketahanan sesi ini: ${active.label.toLowerCase()}`
                : 'Ketahanan belum dapat disimpulkan karena pemulihan tidak terukur'
            }
            className="grid grid-cols-2 gap-2"
          >
            {CELLS.map((c) => {
              const isActive = c === active
              return (
                <div
                  key={c.label}
                  className={
                    'flex min-h-24 items-center justify-center rounded-xl border p-3 text-center text-sm transition-colors ' +
                    (isActive
                      ? 'border-navy bg-brand-soft font-semibold text-navy'
                      : 'border-hairline bg-canvas text-ink-muted')
                  }
                >
                  {c.label}
                </div>
              )
            })}
          </div>

          {/* Horizontal axis, under the columns it labels. */}
          <div className="mt-2 flex justify-between px-1">
            <span className="text-xs text-ink-muted">reaksi kecil</span>
            <span className="text-xs text-ink-muted">reaksi besar</span>
          </div>
        </div>
      </div>

      {/*
        The caption travels with the picture rather than sitting in a paragraph
        further down, for the same reason the radar's did: a screenshot crops,
        and a 2×2 with one cell lit reads as a category somebody was sorted into
        unless something says otherwise right there.
      */}
      <p className="mt-4 text-xs text-ink-muted">
        Ini gambaran <strong>sesi tadi</strong>, bukan gambaran dirimu. Tidak ada
        kotak yang lebih baik dari kotak lain — keempatnya cuma cara tubuh yang
        berbeda dalam menghadapi tekanan.
      </p>
    </div>
  )
}
