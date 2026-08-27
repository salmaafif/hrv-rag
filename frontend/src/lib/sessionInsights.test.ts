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
import { headlines, pressureTimeline, responseDimensions } from './sessionInsights'
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

const axis = (result: SessionResponse, key: string) =>
  responseDimensions(result).find((dimension) => dimension.key === key)!

// ------------------------------------------------------------ the axes
describe('the response axes', () => {
  it('always returns the same three, in the same order', () => {
    /**
     * A radar is only comparable between two sessions if its axes stay put.
     * Sorting them by value — the tempting way to make every chart look
     * flattering — would turn two identical shapes into two different pictures.
     */
    // Nilainya sengaja tidak seragam (calm 0, recovery 90, resilience 0):
    // kalau ada yang menyortirnya, urutannya pasti berubah.
    const dimensions = responseDimensions(
      session([question(1, 'high', 90), question(2, 'high', 90)]),
    )
    expect(dimensions.map((d) => d.key)).toEqual(['calm', 'recovery', 'resilience'])
  })

  it('no longer carries the evenness axis', () => {
    /**
     * Removed on purpose, not lost. It measured the gap between the hardest and
     * easiest question — which the timeline next to the chart already shows, and
     * as a shape rather than a number. It also had to be explained to everybody
     * who saw it, including the person who commissioned it.
     */
    const dimensions = responseDimensions(session([question(1, 'high')]))
    expect(dimensions.map((d) => d.key)).not.toContain('evenness')
  })

  it('counts calmness as the share of questions that stayed low', () => {
    const result = session([
      question(1, 'low'),
      question(2, 'moderate'),
      question(3, 'high'),
      question(4, 'moderate'),
    ])
    // One in four, not two — half of four is what a lazy stand-in returns, and
    // it would have matched a fixture where two of the four ran calm.
    expect(axis(result, 'calm').value).toBe(25)
    expect(axis(result, 'calm').meaning).toContain('1 dari 4')
  })

  it('reports recovery it could not measure as unmeasured, never as zero', () => {
    /**
     * THE ONE THAT MATTERS MOST. Zero says the person never settled down;
     * null says the pause was too short to tell. Collapsing the second into
     * the first would draw a flat spoke on the chart and tell somebody
     * something about themselves that was never measured.
     */
    const result = session([question(1, 'high', null), question(2, 'high', null)])
    const recovery = axis(result, 'recovery')

    expect(recovery.value).toBeNull()
    expect(recovery.value).not.toBe(0)
    expect(recovery.unmeasured).toBeTruthy()
    expect(recovery.meaning).toContain('Belum terukur')
  })

  it('takes the median of the recoveries it does have', () => {
    const result = session([
      question(1, 'high', 20),
      question(2, 'high', null),
      question(3, 'high', 60),
    ])
    expect(axis(result, 'recovery').value).toBe(40)
  })

  it('translates the quadrant additively: each favourable half is worth 50', () => {
    /**
     * The two mixed quadrants deliberately SHARE the middle. "Big reaction but
     * fast recovery" and "small reaction but slow recovery" each got one half
     * right, and the rule never ranked one above the other — so neither does
     * the chart. The meaning sentence is what tells them apart.
     */
    const withQuadrant = (
      quadrant: SessionResponse['summary']['resilience'],
    ) => {
      const result = session([question(1, 'high'), question(2, 'low')])
      return { ...result, summary: { ...result.summary, resilience: quadrant } }
    }

    expect(axis(withQuadrant('high resilience'), 'resilience').value).toBe(100)
    expect(axis(withQuadrant('responsive but flexible'), 'resilience').value)
      .toBe(50)
    expect(axis(withQuadrant('held-in tension'), 'resilience').value).toBe(50)
    expect(axis(withQuadrant('low resilience'), 'resilience').value).toBe(0)

    // Read from the label, never recomputed: same questions, opposite verdicts,
    // different spokes. Deriving the value from the questions instead would
    // return the same answer twice and contradict the sentence beside it.
    expect(axis(withQuadrant('high resilience'), 'resilience').value)
      .not.toBe(axis(withQuadrant('low resilience'), 'resilience').value)
  })

  it('reports resilience as unmeasured when the backend could not conclude', () => {
    /**
     * `summary.resilience` is null when recovery was never measurable — one
     * axis of the quadrant's definition is missing. Falling back to a value
     * would draw a spoke for a conclusion nobody reached.
     */
    const result = session([question(1, 'high', null)])
    const noQuadrant = {
      ...result,
      summary: { ...result.summary, resilience: null },
    }

    const dimension = axis(noQuadrant, 'resilience')
    expect(dimension.value).toBeNull()
    expect(dimension.value).not.toBe(0)
    expect(dimension.unmeasured).toBeTruthy()
  })
})

// -------------------------------------------------------- the headlines
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
      ...responseDimensions(result).flatMap((d) => [
        d.label,
        d.meaning,
        d.unmeasured ?? '',
      ]),
      ...headlines(result).flatMap((h) => [h.label, h.value, h.hint]),
    ].join(' ')

    for (const forbidden of [
      'RMSSD', 'rmssd', 'SDNN', 'pNN50', 'LF/HF', 'HRV',
      'bpm', 'baseline', 'delta', '31.4', '12.7', '/4', 'skor',
    ]) {
      expect(shown).not.toContain(forbidden)
    }
  })

  it('phrases every axis as something that happened, not as a trait', () => {
    /**
     * Mandatory Rule #4 and decision K5: this system indicates pressure and
     * does not judge a person. A radar invites trait labels more than any other
     * chart, so the axis names are checked against the words the thesis rules
     * out.
     *
     * 'Resilience' is NOT on this list, by explicit request: it is the name of
     * one of the document's three promised outputs (reaktivitas, pemulihan,
     * ketahanan), and its meaning sentence describes a reaction and a recovery
     * — two events — rather than scoring the person.
     */
    const result = session([question(1, 'high'), question(2, 'low')])
    const labels = responseDimensions(result).map((d) => d.label).join(' ')

    for (const trait of [
      'Kepribadian', 'Regulasi', 'Kecemasan', 'Mental', 'Karakter', 'Emosi',
      'Personality', 'Anxiety', 'Regulation',
    ]) {
      expect(labels).not.toContain(trait)
    }
  })
})
