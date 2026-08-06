/**
 * AppLayout.tsx — the frame every screen sits in.
 *
 * Owns the header and the left rail; the stage screens fill the rest through
 * the outlet. Keeping the rail here rather than in each screen means the sense
 * of "where am I in this session" cannot drift between stages, which is the one
 * thing a stepper exists to prevent.
 */

import { Navigate, Outlet, useParams } from 'react-router'
import { MODES, toModeId, type StageSegment } from './modes'
import { useDevMode } from './useDevMode'
import { ModeSelect } from '../components/ModeSelect'
import { StepRail } from '../components/StepRail'

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center rounded-xl bg-navy"
      >
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none">
          <path
            d="M2 12h4l2-6 4 12 3-8 2 2h5"
            stroke="var(--color-amber)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="text-xl font-bold tracking-tight text-navy">
        KARIRLINK
      </span>
    </div>
  )
}

function DevModeToggle() {
  const [enabled, setEnabled] = useDevMode()
  return (
    <label className="flex items-center gap-2 text-sm text-ink-muted">
      <input
        type="checkbox"
        checked={enabled}
        onChange={(event) => setEnabled(event.target.checked)}
        className="h-4 w-4 accent-[var(--color-brand)]"
      />
      Mode pengembang
    </label>
  )
}

export function AppLayout() {
  const params = useParams<{ mode: string; stage: string }>()
  const modeId = toModeId(params.mode)

  // An unrecognised mode in the URL is a dead end, not an error worth a screen.
  if (modeId === null) return <Navigate to="/v1/mulai" replace />

  const mode = MODES[modeId]
  const stage = (params.stage ?? 'mulai') as StageSegment
  const activeStep = mode.stepOfSegment[stage] ?? null

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <Logo />
        <div className="flex items-center gap-5">
          <DevModeToggle />
          <ModeSelect current={modeId} />
        </div>
      </header>

      <p className="mb-5 text-sm text-ink-muted">{mode.tagline}</p>

      <div className="grid gap-6 lg:grid-cols-[17rem_1fr]">
        <StepRail mode={mode} activeStep={activeStep} deviceName={null} />
        {/* The mode travels down through the outlet so stage screens never have
            to re-parse and re-validate it from the URL. */}
        <Outlet context={mode} />
      </div>
    </div>
  )
}
