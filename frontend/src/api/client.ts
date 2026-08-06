/**
 * client.ts — the one place that knows how to reach the backend.
 *
 * Two implementations sit behind a single interface: a dummy that returns
 * fixtures, and a real one that calls FastAPI. Which one runs is decided by an
 * environment variable, not by an `if` inside a screen.
 *
 * Building it this way while the backend does not yet exist means the screens
 * get written against the shape they will actually face — a promise that takes
 * time, can fail, and can be retried. A screen written against an imported
 * fixture has no loading state and no error state, and both would have to be
 * retrofitted later, on every screen at once.
 *
 * To switch over: set `VITE_USE_MOCK_API=false` and `VITE_API_BASE_URL`.
 */

import type {
  AnalyzeRequest,
  SessionRequest,
  SessionResponse,
  TimelineResponse,
} from '../types/api'
import { ApiError } from './errors'
import {
  dummyAnalyzeSession,
  dummyAnalyzeTimeline,
  type AnalyzeOptions,
} from './dummy'

export { ApiError } from './errors'
export type { AnalyzeOptions } from './dummy'

/**
 * Defaults to the dummy.
 *
 * Deliberately opt-out rather than opt-in: a missing or mistyped .env file then
 * shows obviously fake data instead of silently pointing a demo at a backend
 * that is not running.
 */
function dummyEnabled(): boolean {
  return import.meta.env.VITE_USE_MOCK_API !== 'false'
}

function baseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured !== 'string' || configured === '') {
    throw new ApiError('Alamat server belum diatur. Hubungi pengembang.', false)
  }
  return configured.replace(/\/$/, '')
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    // No response at all. On a free host this is usually the server waking up,
    // so it is worth offering another attempt.
    throw new ApiError(
      'Tidak bisa menghubungi server. Periksa koneksi internetmu, lalu coba lagi.',
      true,
    )
  }

  if (!response.ok) {
    const retryable = response.status >= 500
    throw new ApiError(
      retryable
        ? 'Server sedang bermasalah. Coba lagi sebentar lagi.'
        : 'Rekaman ini tidak bisa diproses. Periksa berkas atau sambungan perangkatmu.',
      retryable,
    )
  }

  return (await response.json()) as T
}

export function analyzeTimeline(
  request: AnalyzeRequest,
  options: AnalyzeOptions = {},
): Promise<TimelineResponse> {
  if (dummyEnabled()) return dummyAnalyzeTimeline(request, options)
  return postJson<TimelineResponse>('/api/v1/analyze/timeline', request)
}

export function analyzeSession(
  request: SessionRequest,
  options: AnalyzeOptions = {},
): Promise<SessionResponse> {
  if (dummyEnabled()) return dummyAnalyzeSession(request, options)
  return postJson<SessionResponse>('/api/v1/analyze/session', request)
}
