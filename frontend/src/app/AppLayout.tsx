/**
 * AppLayout.tsx — the frame every screen sits in.
 *
 * Owns the header, the left rail, and the device connection. The connection
 * lives here because it has to survive moving between stages: you connect a
 * sensor on stage one and it must still be connected on stage two.
 *
 * The "data tiruan" strip is not a placeholder to remove later without thought.
 * While the fixtures are in use, every number on every screen is invented, and
 * a screenshot of this app taken today would otherwise be indistinguishable
 * from a real measurement of a real person. It comes out when the API is
 * connected, and not before.
 */

import { Outlet, useParams } from 'react-router'
import { MODES, toModeId, type StageSegment } from './modes'
import { NavigateKeepingSearch } from './NavigateKeepingSearch'
import { useDevMode } from './useDevMode'
import { usesMockData } from '../api/client'
import { useDeviceConnection } from './useDeviceConnection'
import { useSessionState } from './useSessionState'
import type { StageContext } from './stageContext'
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

function ConnectionPill({ deviceName }: { deviceName: string | null }) {
  const connected = deviceName !== null
  return (
    <span
      className={
        'flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ' +
        (connected
          ? 'bg-level-low-bg text-level-low'
          : 'bg-unknown-bg text-unknown')
      }
    >
      <span
        aria-hidden="true"
        className={
          'h-2 w-2 rounded-full ' +
          (connected ? 'bg-level-low' : 'bg-unknown')
        }
      />
      {connected ? deviceName : 'Perangkat belum terhubung'}
    </span>
  )
}

export function AppLayout() {
  const params = useParams<{ mode: string; stage: string }>()
  const [devMode] = useDevMode()
  // With `?dev=1` the sensor is simulated, so screens can be worked on and
  // demonstrated without physically wearing a strap. Off by default, because a
  // silent fallback to invented beats would produce a confident report about
  // somebody who was never measured.
  const device = useDeviceConnection(devMode)
  const session = useSessionState(device)
  const modeId = toModeId(params.mode)

  // An unrecognised mode in the URL is a dead end, not an error worth a screen.
  if (modeId === null) return <NavigateKeepingSearch to="/v1/mulai" />

  const mode = MODES[modeId]
  const stage = (params.stage ?? 'mulai') as StageSegment
  const activeStep = mode.stepOfSegment[stage] ?? null
  const context: StageContext = { mode, device, session }

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <Logo />
        <div className="flex flex-wrap items-center gap-5">
          <DevModeToggle />
          <ModeSelect current={modeId} />
          <ConnectionPill deviceName={device.connected?.name ?? null} />
        </div>
      </header>

      {usesMockData() && (
        <p className="mb-4 rounded-lg bg-amber-soft px-4 py-2 text-sm text-level-moderate">
          <strong className="font-semibold">Data tiruan.</strong> Angka di layar
          ini belum berasal dari pengukuran sungguhan.
        </p>
      )}

      <p className="mb-5 text-sm text-ink-muted">{mode.tagline}</p>

      <div className="grid gap-6 lg:grid-cols-[17rem_1fr]">
        <StepRail
          mode={mode}
          activeStep={activeStep}
          deviceName={device.connected?.name ?? null}
        />
        {/* The mode and the connection travel down through the outlet so stage
            screens never re-parse the URL or open a second connection. */}
        <Outlet context={context} />
      </div>
    </div>
  )
}
