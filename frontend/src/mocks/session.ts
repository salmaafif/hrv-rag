/**
 * session.ts — fixture for `POST /api/v1/analyze/session`.
 *
 * The six questions are the ones drawn in the KARIRLINK Figma frames, so the
 * mock and the design describe the same session.
 *
 * Three awkward cases are deliberately present, because they are the ones a
 * screen built only against happy-path data will get wrong:
 *
 *   - question 3 has `recovery_pct: null` — the gap before the next question
 *     was too short to measure recovery. It is NOT zero.
 *   - question 4 has `features_disagree: true` — RMSSD rose while heart rate
 *     also rose, so the reading is less certain than the others.
 *   - the session lands in the "low resilience" quadrant, which is what the
 *     backend rule returns for a large median reaction paired with a slow
 *     median recovery. Reaction and recovery are both derived below rather
 *     than asserted, so the quadrant follows from the data.
 */

import type {
  QuestionResult,
  SessionResponse,
  SessionSummary,
} from '../types/api'
import { mockVerdict } from './rule'

/** What is written by hand; everything else is derived from it. */
interface QuestionSeed {
  number: number
  text: string
  type: QuestionResult['type']
  deltaRmssdPct: number
  deltaHrPct: number
  /** Null when no gap was long enough to measure recovery. */
  recoveryPct: number | null
  recoveryNote: string
  penjelasan: string
  saran: string
}

const SEEDS: QuestionSeed[] = [
  {
    number: 1,
    text: 'Ceritakan tentang dirimu',
    type: 'introduction',
    deltaRmssdPct: -18,
    deltaHrPct: 2,
    recoveryPct: 68,
    recoveryNote: '',
    penjelasan:
      'Kamu tetap tenang saat menjawab pertanyaan pembuka ini, dan cepat ' +
      'kembali santai setelahnya.',
    saran:
      'Pertahankan ritme bicara seperti ini di pertanyaan berikutnya.',
  },
  {
    number: 2,
    text: 'Kenapa kami harus memilihmu?',
    type: 'behavioural',
    deltaRmssdPct: -26,
    deltaHrPct: 7,
    recoveryPct: 41,
    recoveryNote: '',
    penjelasan:
      'Tekananmu naik sedang saat menjawab, dan baru mereda sebagian sebelum ' +
      'pertanyaan berikutnya mulai.',
    saran:
      'Siapkan dua atau tiga kelebihan yang paling ingin kamu sampaikan, jadi ' +
      'kamu tidak perlu menyusunnya mendadak.',
  },
  {
    number: 3,
    text: 'Sebutkan kekuranganmu',
    type: 'behavioural',
    deltaRmssdPct: -41,
    deltaHrPct: 24,
    recoveryPct: null,
    recoveryNote: 'jeda sebelum pertanyaan berikutnya kurang dari 30 detik',
    penjelasan:
      'Ini pertanyaan dengan tekanan paling besar sepanjang sesi. Jeda ' +
      'sesudahnya terlalu pendek, jadi belum kelihatan seberapa cepat kamu ' +
      'kembali tenang.',
    saran:
      'Siapkan satu contoh kekurangan yang sedang kamu perbaiki, lengkap ' +
      'dengan langkah yang sudah kamu ambil, lalu latih menceritakannya.',
  },
  {
    number: 4,
    text: 'Ceritakan konflik di tim dan cara mengatasinya',
    type: 'situational',
    deltaRmssdPct: 14,
    deltaHrPct: 11,
    recoveryPct: 33,
    recoveryNote: '',
    penjelasan:
      'Pembacaan di pertanyaan ini kurang jelas. Sebagian tanda menunjukkan ' +
      'kamu tenang, sebagian lain sebaliknya — berbicara panjang memang bisa ' +
      'memunculkan pola seperti ini.',
    saran:
      'Coba jawab dengan kalimat yang lebih pendek, dan beri jeda napas di ' +
      'antara poin.',
  },
  {
    number: 5,
    text: 'Berapa ekspektasi gajimu?',
    type: 'numerical',
    deltaRmssdPct: -36,
    deltaHrPct: 19,
    recoveryPct: 12,
    recoveryNote: '',
    penjelasan:
      'Tekananmu naik tinggi di pertanyaan ini, dan hanya sedikit mereda ' +
      'sesudahnya.',
    saran:
      'Tentukan rentang angkanya sebelum wawancara, lalu ucapkan sekali ' +
      'dengan lantang untuk latihan. Jadi kamu tidak perlu memutuskan ' +
      'mendadak saat ditanya.',
  },
  {
    number: 6,
    text: 'Ada pertanyaan untuk kami?',
    type: 'introduction',
    deltaRmssdPct: -14,
    deltaHrPct: 1,
    recoveryPct: 74,
    recoveryNote: '',
    penjelasan:
      'Kamu menutup sesi dengan tenang, sama seperti saat memulainya.',
    saran:
      'Siapkan satu pertanyaan tentang cara kerja tim sehari-hari, jadi bagian ' +
      'penutup ini terasa semudah tadi.',
  },
]

const questions: QuestionResult[] = SEEDS.map((seed) => {
  const verdict = mockVerdict(seed.deltaRmssdPct, seed.deltaHrPct)
  return {
    number: seed.number,
    text: seed.text,
    type: seed.type,
    level: verdict.level,
    score: verdict.score,
    delta_rmssd_pct: seed.deltaRmssdPct,
    delta_hr_pct: seed.deltaHrPct,
    recovery_pct: seed.recoveryPct,
    recovery_note: seed.recoveryNote,
    evidence: verdict.evidence,
    features_disagree: verdict.features_disagree,
    penjelasan: seed.penjelasan,
    saran: seed.saran,
  }
})

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 1
    ? sorted[mid]!
    : (sorted[mid - 1]! + sorted[mid]!) / 2
}

/**
 * Mirrors `resilience_quadrant()` in `features/dynamics.py`, including its
 * refusal to answer: without a measurable recovery one of the two axes is
 * missing, and guessing it would make the conclusion look better supported
 * than it is.
 *
 * Thresholds from `config/settings.py`: |reaction| >= 20% counts as large,
 * recovery >= 50% counts as fast.
 */
function quadrant(
  reactivityPct: number | null,
  recoveryPct: number | null,
): SessionSummary['resilience'] {
  if (reactivityPct === null || recoveryPct === null) return null
  const strong = Math.abs(reactivityPct) >= 20
  const fast = recoveryPct >= 50
  if (strong && fast) return 'responsive but flexible'
  if (strong) return 'low resilience'
  if (fast) return 'high resilience'
  return 'held-in tension'
}

function summarise(results: QuestionResult[]): SessionSummary {
  // This fixture is a beat-interval session, so every RMSSD delta is present.
  const rmssd = (q: QuestionResult) => q.delta_rmssd_pct ?? 0
  const reactivity = median(results.map(rmssd))
  // Only questions whose recovery could actually be measured take part.
  const recovery = median(
    results
      .map((q) => q.recovery_pct)
      .filter((v): v is number => v !== null),
  )
  const worst = results.reduce((a, b) => (rmssd(b) < rmssd(a) ? b : a))
  return {
    most_triggering_question: worst.number,
    resilience: quadrant(reactivity, recovery),
    median_reactivity_pct: reactivity,
    median_recovery_pct: recovery,
    reactivity_basis: 'rmssd',
  }
}

export const mockSession: SessionResponse = {
  session_id: 'demo-session-001',
  modality: 'ECG',
  tier: 'T2',
  source: 'beat_intervals',
  baseline: {
    rmssd_ms: 32,
    mean_hr_bpm: 73,
    n_segments: 7,
    is_stable: true,
    evidence: 'limited',
    warning: null,
  },
  questions,
  summary: summarise(questions),
  narrative: {
    ringkasan_sesi:
      'Secara umum kamu cukup tenang. Tapi ada dua pertanyaan yang membuat ' +
      'tekananmu naik jauh lebih tinggi daripada yang lain, dan keduanya ' +
      'sama-sama meminta kamu menilai diri sendiri.',
    penyemangat:
      'Kamu menyelesaikan seluruh sesi tanpa berhenti, dan menutupnya ' +
      'setenang saat memulai. Itu bukan hal kecil.',
  },
  meta: {
    kb_version: 'kb_v2.0',
    model: 'gemini-2.5-flash',
    trustworthy: true,
    prompt_version: 'HRV_session_narrative',
    rule_version: 'K16-2026-08-03',
  },
}

/**
 * A session where no question had a long enough gap after it.
 *
 * Every `recovery_pct` is null, so `median_recovery_pct` is null and the
 * resilience quadrant cannot be determined at all. Kept because the summary
 * card has to degrade gracefully here: "belum dapat disimpulkan" is the honest
 * answer, and it must not fall back to a quadrant or to zero.
 */
export const mockSessionNoRecovery: SessionResponse = (() => {
  const stripped = questions.map((q) => ({
    ...q,
    recovery_pct: null,
    recovery_note: 'jeda sebelum pertanyaan berikutnya kurang dari 30 detik',
  }))
  return {
    ...mockSession,
    session_id: 'demo-session-002',
    questions: stripped,
    summary: summarise(stripped),
  }
})()

/**
 * A session from a watch that reports heart rate only (`source: 'bpm'`).
 *
 * The same six questions and heart-rate changes, with everything the backend
 * does not measure on that path ABSENT rather than zero: no RMSSD anywhere, no
 * recovery, no resilience quadrant, and a summary ranked by heart rate. The
 * dummy serves it whenever a request carries heart-rate reports and no
 * intervals, so `?dev=1&sensor=bpm` shows the screen that path really gets.
 */
export const mockSessionHeartRateOnly: SessionResponse = (() => {
  // Written per level rather than copied from the seeds: those sentences talk
  // about settling afterwards, which this path never measures.
  const PENJELASAN: Record<QuestionResult['level'], string> = {
    low: 'Detak jantungmu tetap dekat dengan saat kamu tenang di awal.',
    moderate: 'Detak jantungmu naik sedang saat menjawab pertanyaan ini.',
    high: 'Detak jantungmu naik cukup tinggi saat menjawab pertanyaan ini.',
  }

  const measured: QuestionResult[] = SEEDS.map((seed) => {
    const verdict = mockVerdict(null, seed.deltaHrPct)
    return {
      number: seed.number,
      text: seed.text,
      type: seed.type,
      level: verdict.level,
      score: verdict.score,
      delta_rmssd_pct: null,
      delta_hr_pct: seed.deltaHrPct,
      recovery_pct: null,
      recovery_note:
        'perangkat ini hanya mengirim detak jantung, jadi pemulihan tidak diukur',
      evidence: verdict.evidence,
      features_disagree: verdict.features_disagree,
      penjelasan: PENJELASAN[verdict.level],
      saran: seed.saran,
    }
  })

  const largest = measured.reduce((a, b) =>
    Math.abs(b.delta_hr_pct) > Math.abs(a.delta_hr_pct) ? b : a,
  )

  return {
    ...mockSession,
    session_id: 'demo-session-004',
    tier: 'T1-BPM',
    source: 'bpm',
    baseline: { ...mockSession.baseline, rmssd_ms: null },
    signal_fitness: {
      rmssd_trusted: false,
      reasons: [
        'device reports heart rate (bpm) only, not beat-to-beat intervals, ' +
          'so variability was not measured',
      ],
      quantization_step_ms: null,
      missed_beat_ratio: null,
      task_outlier_ratio: null,
    },
    questions: measured,
    summary: {
      most_triggering_question: largest.number,
      resilience: null,
      median_reactivity_pct: median(measured.map((q) => q.delta_hr_pct)),
      median_recovery_pct: null,
      reactivity_basis: 'mean_hr',
    },
    narrative: {
      ringkasan_sesi:
        'Secara umum detak jantungmu cukup terjaga. Ada dua pertanyaan yang ' +
        'membuatnya naik jauh lebih tinggi daripada yang lain.',
      penyemangat: mockSession.narrative.penyemangat,
    },
    meta: {
      ...mockSession.meta,
      prompt_version: 'HRV_session_narrative_heart_rate_only',
    },
  }
})()

/**
 * A session whose resting period came back too unsteady to trust.
 *
 * The unstable-baseline warning is the single most important thing the result
 * screen can say — every number is a comparison against that period — so it
 * must be possible to look at it on demand (`?baseline=goyah`). The warning is
 * the backend's own wording from `BaselineVerdict.note_for_user`.
 */
export const mockSessionUnstableBaseline: SessionResponse = {
  ...mockSession,
  session_id: 'demo-session-003',
  baseline: {
    ...mockSession.baseline,
    is_stable: false,
    warning:
      'periode tenang di awal belum benar-benar tenang, jadi angka di bawah ' +
      'ini kurang pasti dari biasanya',
  },
}
