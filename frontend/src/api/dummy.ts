/**
 * dummy.ts — a stand-in backend.
 *
 * Returns the fixtures, but only after behaving like a network call: it takes
 * time, it can fail, and it hands back a promise. That is the whole reason it
 * exists rather than importing the fixtures straight into a screen — a screen
 * written against an instant, infallible value is a screen with no loading
 * state and no error state, and both would have to be added later under
 * pressure.
 *
 * The delay is a compressed stand-in. `docs/frontend_plan.md` section 6 warns
 * that a free host cold-starting scipy, numpy and neurokit2 can take 30 to 60
 * seconds; waiting that long on every click during development would be
 * unusable, so the wait here is short but real.
 */

import type {
  AnalyzeRequest,
  SessionRequest,
  SessionResponse,
  TimelineResponse,
} from '../types/api'
import { mockTimeline, mockTimelineUnstableBaseline } from '../mocks/timeline'
import { mockSession } from '../mocks/session'
import { ApiError } from './errors'

/** Long enough to see a loading state, short enough to work with. */
export const DUMMY_LATENCY_MS = 1600

export interface AnalyzeOptions {
  /**
   * Force a failure. Dummy only.
   *
   * Exists so the error screen can be reached deliberately instead of being
   * written blind and first seen the day something actually breaks.
   */
  simulateError?: boolean
  /**
   * Return the fixture whose resting period was too unsteady to trust.
   *
   * Same reasoning: the unstable-baseline warning is the single most important
   * thing this UI can say, and it must be possible to look at it on demand.
   */
  simulateUnstableBaseline?: boolean
  /**
   * Override the artificial delay, in milliseconds.
   *
   * Only tests pass this. They are asserting what comes back, not how long the
   * screen spends waiting, and making them sit through the real delay would add
   * seconds to every run for no extra confidence.
   */
  latencyMs?: number
}

// Plain `setTimeout`, not `window.setTimeout`: this module has to run under the
// test runner too, where there is no window.
function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function respond<T>(payload: T, options: AnalyzeOptions): Promise<T> {
  await wait(options.latencyMs ?? DUMMY_LATENCY_MS)
  if (options.simulateError) {
    throw new ApiError('Server sedang bermasalah. Coba lagi sebentar lagi.', true)
  }
  return payload
}

export function dummyAnalyzeTimeline(
  _request: AnalyzeRequest,
  options: AnalyzeOptions = {},
): Promise<TimelineResponse> {
  return respond(
    options.simulateUnstableBaseline ? mockTimelineUnstableBaseline : mockTimeline,
    options,
  )
}

export function dummyAnalyzeSession(
  _request: SessionRequest,
  options: AnalyzeOptions = {},
): Promise<SessionResponse> {
  return respond(mockSession, options)
}
