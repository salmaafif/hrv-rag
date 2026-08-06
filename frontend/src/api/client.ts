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

/**
 * Statuses worth another attempt even though they are not 5xx.
 *
 * 408 is the server saying it waited too long, and 429 is it asking us to slow
 * down. Both clear on their own. Lumping them in with 4xx told the person their
 * recording was unusable and removed the retry button, which is the opposite of
 * what either status means.
 */
const RETRYABLE_CLIENT_STATUSES = new Set([408, 429])

function messageForStatus(status: number): string {
  if (status === 404) {
    // Almost always a misconfigured base URL or endpoint path, not the recording.
    return 'Alamat layanan tidak ditemukan. Hubungi pengembang.'
  }
  if (status >= 500 || RETRYABLE_CLIENT_STATUSES.has(status)) {
    return 'Server sedang bermasalah. Coba lagi sebentar lagi.'
  }
  return 'Rekaman ini tidak bisa diproses. Periksa berkas atau sambungan perangkatmu.'
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  // Resolved BEFORE the try block on purpose. When it sat inside, the "server
  // address is not configured" error it throws was caught by the network handler
  // below and replaced with "check your internet connection" — sending the user
  // to look at their wifi over a missing .env value, behind a retry button that
  // could never succeed.
  const url = `${baseUrl()}${path}`

  let response: Response
  try {
    response = await fetch(url, {
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
    const retryable =
      response.status >= 500 || RETRYABLE_CLIENT_STATUSES.has(response.status)
    throw new ApiError(messageForStatus(response.status), retryable)
  }

  try {
    return (await response.json()) as T
  } catch {
    // A 200 carrying HTML rather than JSON — a proxy splash page, a captive
    // portal, a CDN error page. Left unguarded this escaped as a raw SyntaxError
    // quoting the HTML back at the user.
    throw new ApiError(
      'Jawaban dari server tidak bisa dibaca. Coba lagi sebentar lagi.',
      true,
    )
  }
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
