/**
 * session.ts — fixture for V2 and V3, `POST /api/v1/analyze/session`.
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
  const reactivity = median(results.map((q) => q.delta_rmssd_pct))
  // Only questions whose recovery could actually be measured take part.
  const recovery = median(
    results
      .map((q) => q.recovery_pct)
      .filter((v): v is number => v !== null),
  )
  const worst = results.reduce((a, b) =>
    b.delta_rmssd_pct < a.delta_rmssd_pct ? b : a,
  )
  return {
    most_triggering_question: worst.number,
    resilience: quadrant(reactivity, recovery),
    median_reactivity_pct: reactivity,
    median_recovery_pct: recovery,
  }
}

export const mockSession: SessionResponse = {
  session_id: 'demo-session-001',
  modality: 'ECG',
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
