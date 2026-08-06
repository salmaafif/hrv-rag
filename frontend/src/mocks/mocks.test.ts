/**
 * mocks.test.ts — keeps the fixtures honest.
 *
 * Two jobs.
 *
 * First, guarantee that the awkward cases stay in the fixtures. A mock quietly
 * losing its null recovery or its disagreeing features would let a screen be
 * built, reviewed and demonstrated without anyone ever seeing the states that
 * are hardest to get right.
 *
 * Second, make sure the copy of the scoring rule kept in `rule.ts` never leaks
 * into application code. Mandatory rule #1 says the numbers are computed once,
 * by Python. A second classifier the UI could reach would let the screen
 * disagree with the backend it is supposed to be displaying.
 */

import { describe, expect, it } from 'vitest'
import {
  mockTimeline,
  mockTimelineUnstableBaseline,
} from './timeline'
import { mockSession, mockSessionNoRecovery } from './session'

describe('session fixture', () => {
  it('keeps a question whose recovery could not be measured', () => {
    const unmeasured = mockSession.questions.filter(
      (q) => q.recovery_pct === null,
    )
    expect(unmeasured).toHaveLength(1)
    expect(unmeasured[0]!.recovery_note).not.toBe('')
  })

  it('never uses zero to mean "not measured"', () => {
    // A fixture that wrote 0 instead of null would silently teach the UI the
    // wrong lesson, and every screen built against it would inherit the error.
    for (const q of mockSession.questions) {
      if (q.recovery_note !== '') expect(q.recovery_pct).toBeNull()
    }
  })

  it('keeps a question where the two markers disagree', () => {
    const disagreeing = mockSession.questions.filter((q) => q.features_disagree)
    expect(disagreeing).toHaveLength(1)
    // The pattern is specifically RMSSD rising while heart rate also rises.
    expect(disagreeing[0]!.delta_rmssd_pct).toBeGreaterThan(0)
    expect(disagreeing[0]!.delta_hr_pct).toBeGreaterThan(0)
  })

  it('covers all three levels', () => {
    const levels = new Set(mockSession.questions.map((q) => q.level))
    expect(levels).toEqual(new Set(['low', 'moderate', 'high']))
  })

  it('points at the question with the largest reaction', () => {
    const worst = mockSession.questions.reduce((a, b) =>
      b.delta_rmssd_pct < a.delta_rmssd_pct ? b : a,
    )
    expect(mockSession.summary.most_triggering_question).toBe(worst.number)
  })

  it('takes the median recovery from measurable questions only', () => {
    // Measurable values are 68, 41, 33, 12, 74 -> median 41. Had the null been
    // counted as zero the median would have dropped to 33, understating how
    // much this person actually settled.
    expect(mockSession.summary.median_recovery_pct).toBe(41)
  })
})

describe('session fixture without any measurable recovery', () => {
  it('reports no median recovery at all', () => {
    expect(mockSessionNoRecovery.summary.median_recovery_pct).toBeNull()
  })

  it('declines to place the session in a resilience quadrant', () => {
    // One of the two axes is missing, so the quadrant is undefined. Returning
    // a quadrant anyway would present a guess as a finding.
    expect(mockSessionNoRecovery.summary.resilience).toBeNull()
  })
})

describe('timeline fixture', () => {
  it('starts after the baseline period rather than at second zero', () => {
    expect(mockTimeline.timeline[0]!.start_sec).toBe(240)
  })

  it('advances every 30 seconds with 60-second windows', () => {
    // Adjacent points share half their data. The chart must not present them
    // as two independent readings that corroborate each other.
    const [first, second] = mockTimeline.timeline
    expect(second!.start_sec - first!.start_sec).toBe(30)
    expect(first!.end_sec - first!.start_sec).toBe(60)
  })

  it('counts every point exactly once in the summary', () => {
    const { count_low, count_moderate, count_high } = mockTimeline.summary
    expect(count_low + count_moderate + count_high).toBe(
      mockTimeline.timeline.length,
    )
  })

  it('keeps a window where the two markers disagree', () => {
    expect(mockTimeline.timeline.some((p) => p.features_disagree)).toBe(true)
  })
})

describe('timeline fixture with an unstable baseline', () => {
  it('carries a warning the screen has to surface', () => {
    expect(mockTimelineUnstableBaseline.baseline.is_stable).toBe(false)
    expect(mockTimelineUnstableBaseline.baseline.warning).not.toBeNull()
  })
})

describe('the mock scoring rule', () => {
  it('is not reachable from application code', () => {
    // Read every source file through Vite's glob import rather than Node's fs,
    // so the check needs no extra type packages and runs the same way the app
    // is bundled. The pattern is rooted at "/src" rather than written relative
    // to this file, so the keys are full project paths and the mocks directory
    // can be excluded by name instead of by how many "../" it happens to be
    // away.
    const sources = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>

    const offenders = Object.entries(sources)
      .filter(([path]) => !path.includes('/mocks/'))
      .filter(([, text]) => /from\s+['"][^'"]*\/rule['"]/.test(text))
      .map(([path]) => path)

    expect(offenders).toEqual([])
  })

  it('actually scans files, so the check above cannot pass vacuously', () => {
    const sources = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>
    expect(Object.keys(sources).length).toBeGreaterThan(3)
  })
})
