/**
 * sessionInsights.test.ts — the figures the dashboard draws.
 *
 * Every number on the result screen now passes through this module, so a
 * mistake here is a wrong statement made confidently to somebody about their
 * own interview. Two classes of failure are worth more than the others and are
 * tested hardest: a "not measured" quietly becoming a zero, and a technical
 * figure escaping into text a user reads.
 */

import { describe, expect, it } from 'vitest'
import {
  headlines,
  pressureTimeline,
  resilienceCell,
  sessionTrend,
} from './sessionInsights'
import type { QuestionResult, SessionResponse, StressLevel } from '../types/api'

function question(
  number: number,
  level: StressLevel,
  recovery: number | null = 40,
): QuestionResult {
  return {
    number,
    text: `Pertanyaan ${number}`,
    type: 'behavioural',
    level,
    score: 2,
    delta_rmssd_pct: -31.4,
    delta_hr_pct: 12.7,
    recovery_pct: recovery,
    recovery_note: '',
    evidence: ['RMSSD 31% below baseline (1 pt)'],
    features_disagree: false,
    penjelasan: 'Tubuhmu menunjukkan respons.',
    saran: 'Tarik napas dulu sebelum menjawab.',
  }
}

function session(questions: QuestionResult[]): SessionResponse {
  return {
    session_id: 'test',
    modality: 'ECG',
    tier: 'T2',
    baseline: {
      rmssd_ms: 32,
      mean_hr_bpm: 73,
      n_segments: 11,
      is_stable: true,
      evidence: 'full',
      warning: null,
    },
    questions,
    summary: {
      most_triggering_question: questions[0]?.number ?? null,
      resilience: 'low resilience',
      median_reactivity_pct: -24.3,
      median_recovery_pct: 40,
    },
    narrative: { ringkasan_sesi: 'Ringkasan.', penyemangat: 'Semangat.' },
    meta: {
      kb_version: 'kb_v2.0', model: 'gemini-2.5-flash', trustworthy: true,
      prompt_version: 'HRV_session_narrative', rule_version: 'K16-2026-08-03',
    },
  }
}

// ------------------------------------------------------------ ketahanan
describe('the resilience quadrant', () => {
  const withQuadrant = (quadrant: SessionResponse['summary']['resilience']) => {
    const result = session([question(1, 'high'), question(2, 'low')])
    return { ...result, summary: { ...result.summary, resilience: quadrant } }
  }

  it('maps every quadrant the backend can return', () => {
    // No default branch and no fallback cell: an unmapped quadrant must be a
    // type error at build time, not a silently wrong square at render time.
    expect(resilienceCell('high resilience')).toEqual({
      reaction: 'kecil', recovery: 'cepat',
    })
    expect(resilienceCell('held-in tension')).toEqual({
      reaction: 'kecil', recovery: 'lambat',
    })
    expect(resilienceCell('responsive but flexible')).toEqual({
      reaction: 'besar', recovery: 'cepat',
    })
    expect(resilienceCell('low resilience')).toEqual({
      reaction: 'besar', recovery: 'lambat',
    })
  })

  it('returns nothing when the backend could not conclude', () => {
    /**
     * THE ONE THAT MATTERS MOST here. `resilience` is null when recovery could
     * not be measured at all — one of the two axes is missing, so there is no
     * cell. Falling back to a square would light one up and tell somebody where
     * they landed on a measurement nobody took.
     */
    expect(resilienceCell(null)).toBeNull()
    expect(resilienceCell(withQuadrant(null).summary.resilience)).toBeNull()
  })

  it('reads the cell from the label, never recomputed from the questions', () => {
    // Same questions, opposite verdicts. If this module derived the cell from
    // the levels and recoveries it would return the same answer twice, and the
    // picture would contradict the sentence beside it.
    const a = { ...withQuadrant('high resilience') }
    const b = { ...withQuadrant('low resilience') }
    expect(a.questions).toEqual(b.questions)
    expect(resilienceCell(a.summary.resilience))
      .not.toEqual(resilienceCell(b.summary.resilience))
  })
})

// ------------------------------------------------------------- arah sesi
describe('the session trend', () => {
  it('says the pressure held steady', () => {
    const steady = session([
      question(1, 'moderate'), question(2, 'moderate'),
      question(3, 'moderate'), question(4, 'moderate'),
    ])
    expect(sessionTrend(steady)).toContain('Segitu-gitu saja')
  })

  it('says it eased towards the end', () => {
    const fading = session([
      question(1, 'high'), question(2, 'high'),
      question(3, 'low'), question(4, 'low'),
    ])
    expect(sessionTrend(fading)).toContain('makin santai')
  })

  it('says it piled up towards the end', () => {
    const piling = session([
      question(1, 'low'), question(2, 'low'),
      question(3, 'high'), question(4, 'high'),
    ])
    expect(sessionTrend(piling)).toContain('menumpuk')
  })

  it('refuses to compare halves of a single question', () => {
    expect(sessionTrend(session([question(1, 'high')]))).toBeNull()
  })

  it('is a sentence, never a number', () => {
    /**
     * The reason this stopped being a chart axis. On a 0-100 scale its midpoint
     * meant "no change" while every other axis midpoint meant "half", so a
     * steady session drew the same dent as a bad one. In words there is nothing
     * left to misread.
     */
    const steady = session([question(1, 'moderate'), question(2, 'moderate')])
    expect(sessionTrend(steady)).not.toMatch(/\d/)
  })
})

describe('the headline figures', () => {
  it('names the question that triggered the most', () => {
    const result = session([question(1, 'high'), question(2, 'low')])
    expect(headlines(result)[0]!.value).toBe('Pertanyaan 1')
  })

  it('says so plainly when recovery was never measurable', () => {
    const result = session([question(1, 'high', null)])
    const settled = headlines(result)[2]!
    expect(settled.value).toBe('Belum terukur')
    expect(settled.value).not.toContain('0')
  })
})

// ------------------------------------------------------------ timeline
describe('the pressure timeline', () => {
  it('follows the labels the rule assigned, not the raw percentages', () => {
    /**
     * The line has to agree with the badges beside it. Plotting
     * `delta_rmssd_pct` instead would draw a curve that contradicts the labels
     * — and would put a technical figure on a user's screen (K4).
     */
    const result = session([
      question(1, 'low'),
      question(2, 'moderate'),
      question(3, 'high'),
    ])
    expect(pressureTimeline(result).map((point) => point.pressure))
      .toEqual([0, 50, 100])
  })

  it('keeps the questions in the order they were asked', () => {
    const result = session([question(1, 'high'), question(2, 'low')])
    expect(pressureTimeline(result).map((p) => p.number)).toEqual([1, 2])
  })
})

// ------------------------------------------------------ decision K4
describe('nothing technical reaches the text a user reads', () => {
  it('never mentions a feature name, a raw value or a score', () => {
    /**
     * The API withholds the technical layer by default, but the fields ARE
     * present in a V2/V3 response and a helper here could easily quote one into
     * a sentence. K4 cannot be enforced by the backend; this is where it holds.
     */
    const result = session([
      question(1, 'high', 40),
      question(2, 'low', null),
      question(3, 'moderate', 80),
    ])

    const shown = [
      ...headlines(result).flatMap((h) => [h.label, h.value, h.hint]),
      sessionTrend(result) ?? '',
    ].join(' ')

    for (const forbidden of [
      'RMSSD', 'rmssd', 'SDNN', 'pNN50', 'LF/HF', 'HRV',
      'bpm', 'baseline', 'delta', '31.4', '12.7', '/4', 'skor',
    ]) {
      expect(shown).not.toContain(forbidden)
    }
  })

  it('phrases the outcome as something that happened, not as a trait', () => {
    /**
     * Mandatory Rule #4 and decision K5: this system indicates pressure and
     * does not judge a person. The quadrant is the riskiest place for that to
     * slip, because sorting somebody into one of four boxes is what a
     * personality instrument does — so the words in those boxes are checked
     * against the vocabulary the thesis rules out. They describe a reaction and
     * a recovery, both of which are events, and neither of which is a person.
     */
    const result = session([question(1, 'high'), question(2, 'low')])
    const shown = [
      resilienceCell('high resilience')!.reaction,
      resilienceCell('high resilience')!.recovery,
      resilienceCell('low resilience')!.reaction,
      resilienceCell('low resilience')!.recovery,
      sessionTrend(result) ?? '',
      ...headlines(result).map((h) => h.label),
    ].join(' ')

    for (const trait of [
      'Kepribadian', 'Regulasi', 'Kecemasan', 'Mental', 'Karakter', 'Emosi',
      'Personality', 'Anxiety', 'Regulation', 'Resilience', 'Ketahanan',
    ]) {
      expect(shown).not.toContain(trait)
    }
  })
})
