/**
 * httpClient.test.ts — the REAL backend path, which the dummy tests never touch.
 *
 * `client.test.ts` exercises the fixture backend. Everything below only runs when
 * `VITE_USE_MOCK_API=false`, which is the configuration the demo will actually be
 * shown in — and until now nothing covered it at all. Every failure locked in here
 * was found live in that untested branch.
 *
 * What matters in each case is not only that an error is raised, but WHICH error:
 * the message tells the person what to do, and `retryable` decides whether they
 * are even offered a way to try again.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { analyzeTimeline } from './client'
import { ApiError } from './errors'

const request = { baseline_minutes: 4, modality: 'ECG' as const }

function respondWith(init: { status?: number; body?: string }) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(init.body ?? '{}', { status: init.status ?? 200 }),
    ),
  )
}

async function captureError(): Promise<ApiError> {
  try {
    await analyzeTimeline(request)
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('expected analyzeTimeline to reject')
}

beforeEach(() => {
  vi.stubEnv('VITE_USE_MOCK_API', 'false')
  vi.stubEnv('VITE_API_BASE_URL', 'https://example.test')
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('missing configuration', () => {
  it('says the address is unset instead of blaming the network', async () => {
    // The diagnostic used to be thrown inside the try block that catches network
    // failures, so a forgotten .env value told the user to check their wifi and
    // offered a retry button that could never work.
    vi.stubEnv('VITE_API_BASE_URL', '')
    respondWith({})

    const error = await captureError()
    expect(error.message).toContain('Alamat server belum diatur')
    expect(error.retryable).toBe(false)
  })
})

describe('status classification', () => {
  it('treats 5xx as worth retrying', async () => {
    respondWith({ status: 503 })
    const error = await captureError()
    expect(error.retryable).toBe(true)
  })

  it.each([408, 429])('treats %i as worth retrying', async (status) => {
    // Timeout and rate-limit are transient by definition. Classed as ordinary
    // 4xx they told the person their recording was unusable and removed the
    // retry button — the one thing that would have worked.
    respondWith({ status })
    const error = await captureError()
    expect(error.retryable).toBe(true)
    expect(error.message).not.toContain('Rekaman ini tidak bisa diproses')
  })

  it('blames the recording only for genuine client errors', async () => {
    respondWith({ status: 422 })
    const error = await captureError()
    expect(error.retryable).toBe(false)
    expect(error.message).toContain('Rekaman ini tidak bisa diproses')
  })

  it('points a 404 at the configuration, not at the recording', async () => {
    // A 404 means the URL is wrong. Telling the person to check their file
    // sends them to fix something that was never broken.
    respondWith({ status: 404 })
    const error = await captureError()
    expect(error.message).toContain('Hubungi pengembang')
  })
})

describe('malformed responses', () => {
  it('reports a 200 carrying HTML as an ApiError, not a SyntaxError', async () => {
    // Proxy splash pages and CDN error pages arrive as 200 + HTML. Parsing was
    // outside every guard, so this escaped as a raw SyntaxError quoting the HTML
    // back at the user.
    respondWith({ status: 200, body: '<html>waking up</html>' })
    const error = await captureError()
    expect(error.retryable).toBe(true)
  })
})

describe('network failure', () => {
  it('is retryable and mentions the connection', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    const error = await captureError()
    expect(error.retryable).toBe(true)
    expect(error.message).toContain('koneksi')
  })
})
