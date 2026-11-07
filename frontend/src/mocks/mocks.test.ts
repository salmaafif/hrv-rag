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
  mockSession,
  mockSessionHeartRateOnly,
  mockSessionNoRecovery,
  mockSessionUnstableBaseline,
} from './session'

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
    // A beat-interval fixture: every RMSSD delta is present.
    const rmssd = (q: (typeof mockSession.questions)[number]) =>
      q.delta_rmssd_pct ?? 0
    const worst = mockSession.questions.reduce((a, b) =>
      rmssd(b) < rmssd(a) ? b : a,
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

describe('session fixture from a watch that reports heart rate only', () => {
  /** Every number filed under a variability name, anywhere in the payload. */
  function variabilityNumbers(node: unknown, path = ''): string[] {
    if (Array.isArray(node)) {
      return node.flatMap((item, i) => variabilityNumbers(item, `${path}[${i}]`))
    }
    if (node === null || typeof node !== 'object') return []
    return Object.entries(node).flatMap(([key, value]) => {
      const named = key.split('_').some((part) =>
        ['rmssd', 'sdnn', 'pnn50', 'lf', 'hf'].includes(part))
      const here = named && typeof value === 'number' ? [`${path}.${key}`] : []
      return [...here, ...variabilityNumbers(value, `${path}.${key}`)]
    })
  }

  it('carries no variability number anywhere', () => {
    // A screen built against this fixture must never meet an RMSSD it could
    // quote. The same rule the backend test enforces on the real payload.
    expect(variabilityNumbers(mockSessionHeartRateOnly)).toEqual([])
    expect(JSON.stringify(mockSessionHeartRateOnly)).not.toContain('RMSSD')
    // The control: the interval fixture does carry them.
    expect(variabilityNumbers(mockSession)).not.toEqual([])
  })

  it('names its path and tier', () => {
    expect(mockSessionHeartRateOnly.source).toBe('bpm')
    expect(mockSessionHeartRateOnly.tier).toBe('T1-BPM')
    expect(mockSessionHeartRateOnly.summary.reactivity_basis).toBe('mean_hr')
  })

  it('reports recovery and resilience as unmeasured, never as zero', () => {
    for (const q of mockSessionHeartRateOnly.questions) {
      expect(q.recovery_pct).toBeNull()
      expect(q.recovery_note).not.toBe('')
    }
    expect(mockSessionHeartRateOnly.summary.median_recovery_pct).toBeNull()
    expect(mockSessionHeartRateOnly.summary.resilience).toBeNull()
  })

  it('names the question with the largest heart-rate rise', () => {
    const largest = mockSessionHeartRateOnly.questions.reduce((a, b) =>
      b.delta_hr_pct > a.delta_hr_pct ? b : a,
    )
    expect(mockSessionHeartRateOnly.summary.most_triggering_question)
      .toBe(largest.number)
  })
})

describe('session fixture with an unstable baseline', () => {
  it('carries a warning the screen has to surface', () => {
    expect(mockSessionUnstableBaseline.baseline.is_stable).toBe(false)
    expect(mockSessionUnstableBaseline.baseline.warning).not.toBeNull()
  })

  it('changes nothing but the baseline', () => {
    // Otherwise a screen reviewed against it would be judged on two
    // differences at once and nobody could tell which one drew the warning.
    expect(mockSessionUnstableBaseline.questions).toBe(mockSession.questions)
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
