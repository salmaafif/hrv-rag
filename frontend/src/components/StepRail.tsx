/**
 * StepRail.tsx — the left column: where you are in the session, and on what device.
 *
 * The rail reports progress; it does not offer navigation. Steps are not links
 * because they are not freely reachable: you cannot look at results before a
 * recording has been analysed, and a step that looks clickable but is not is
 * worse than one that never invited the click.
 *
 * Completed steps are marked with a word as well as a colour, so the state does
 * not depend on telling green from amber.
 */

import { Card } from './Card'
import type { ModeDefinition } from '../app/modes'

interface StepRailProps {
  mode: ModeDefinition
  /** Index into `mode.steps`, or null on a stage that has no step of its own. */
  activeStep: number | null
  /** Device name once one is connected. Null before that. */
  deviceName: string | null
}

export function StepRail({ mode, activeStep, deviceName }: StepRailProps) {
  return (
    <Card eyebrow="Tahapan sesi">
      <ol className="space-y-1">
        {mode.steps.map((label, index) => {
          const isActive = activeStep === index
          const isDone = activeStep !== null && index < activeStep

          return (
            <li key={label} className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className={
                  'h-6 w-0.5 shrink-0 rounded-full ' +
                  (isActive
                    ? 'bg-amber'
                    : isDone
                      ? 'bg-level-low'
                      : 'bg-hairline')
                }
              />
              <span
                className={
                  'py-1 text-sm ' +
                  (isActive
                    ? 'font-semibold text-navy'
                    : isDone
                      ? 'text-ink-muted'
                      : 'text-ink-muted/70')
                }
              >
                {index + 1}. {label}
              </span>
              {isDone && <span className="sr-only">(selesai)</span>}
              {isActive && <span className="sr-only">(sedang berjalan)</span>}
            </li>
          )
        })}
      </ol>

      <hr className="my-5 border-hairline" />

      <p className="mb-2 text-xs font-semibold tracking-wider text-ink-muted uppercase">
        Perangkat
      </p>
      {deviceName ? (
        <p className="rounded-lg bg-canvas px-3 py-2 text-sm font-semibold text-navy">
          {deviceName}
        </p>
      ) : (
        <p className="rounded-lg bg-canvas px-3 py-2 text-sm text-ink-muted">
          Belum dipilih
        </p>
      )}
    </Card>
  )
}
