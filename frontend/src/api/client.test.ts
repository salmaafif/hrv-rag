/**
 * client.test.ts — the dummy backend behaves like a backend.
 *
 * Not testing the fixtures — `mocks.test.ts` does that. What is checked here is
 * that the seam the screens are written against actually has the properties
 * they depend on: each endpoint returns its own shape, failures arrive as
 * `ApiError` rather than as an undefined result, and the deliberate awkward
 * cases can be reached on demand.
 *
 * If this seam were skipped and the screens imported fixtures directly, none of
 * these behaviours would exist to test, and none of them would exist to handle.
 */

import { describe, expect, it } from 'vitest'
import { analyzeSession, analyzeTimeline } from './client'
import { ApiError } from './errors'
import { mockQuestionTimeline } from '../mocks/questionTimeline'

const FAST = { latencyMs: 0 }

const baseRequest = {
  baseline_minutes: 4,
  modality: 'ECG' as const,
}

describe('analyzeTimeline', () => {
  it('returns a per-minute timeline', async () => {
    const result = await analyzeTimeline(baseRequest, FAST)
    expect(result.timeline.length).toBeGreaterThan(0)
    expect(result.summary.count_low).toBeGreaterThanOrEqual(0)
  })

  it('can return the unsteady-baseline case on demand', async () => {
    // This is the warning the result screen must surface. Being able to reach
    // it deliberately is the difference between designing that state and
    // discovering it.
    const result = await analyzeTimeline(baseRequest, {
      ...FAST,
      simulateUnstableBaseline: true,
    })
    expect(result.baseline.is_stable).toBe(false)
    expect(result.baseline.warning).not.toBeNull()
  })

  it('returns a stable baseline by default', async () => {
    const result = await analyzeTimeline(baseRequest, FAST)
    expect(result.baseline.is_stable).toBe(true)
  })
})

describe('analyzeSession', () => {
  it('returns per-question results', async () => {
    const result = await analyzeSession(
      { ...baseRequest, questions: mockQuestionTimeline },
      FAST,
    )
    expect(result.questions.length).toBe(mockQuestionTimeline.length)
  })
})

describe('failures', () => {
  it('rejects with an ApiError carrying a message the user can read', async () => {
    await expect(
      analyzeTimeline(baseRequest, { ...FAST, simulateError: true }),
    ).rejects.toBeInstanceOf(ApiError)
  })

  it('marks a server failure as worth retrying', async () => {
    // The retry offer is not cosmetic: on a free host most failures are the
    // server waking up, and a second attempt genuinely works.
    try {
      await analyzeTimeline(baseRequest, { ...FAST, simulateError: true })
      expect.unreachable('should have thrown')
    } catch (cause) {
      expect(cause).toBeInstanceOf(ApiError)
      expect((cause as ApiError).retryable).toBe(true)
      expect((cause as ApiError).message).not.toBe('')
    }
  })
})
