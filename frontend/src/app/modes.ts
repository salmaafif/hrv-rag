/**
 * modes.ts — the three versions of the demo, described as data.
 *
 * V1, V2 and V3 run the SAME analysis pipeline. What differs is only where the
 * question timeline comes from and what unit the result is reported in:
 *
 *   V1  no question timeline at all      -> one result per minute
 *   V2  the user types the timeline      -> one result per question
 *   V3  the app knows it, having asked   -> one result per question
 *
 * V2 and V3 therefore hit the same endpoint and render the same result screen.
 * Keeping that fact in one table, rather than scattered across components,
 * means a screen cannot accidentally start treating them as two different
 * analyses.
 */

export type ModeId = 'v1' | 'v2' | 'v3'

export const MODE_IDS: readonly ModeId[] = ['v1', 'v2', 'v3']

/** Path segments that can appear under `/:mode/`. */
export type StageSegment = 'mulai' | 'sesi' | 'proses' | 'hasil'

export interface ModeDefinition {
  id: ModeId
  /** Shown in the mode picker. */
  label: string
  /** One line explaining what this mode is for. */
  tagline: string
  /** Which endpoint this mode calls. */
  endpoint: '/api/v1/analyze/timeline' | '/api/v1/analyze/session'
  /** True only for V3, where the interview itself runs inside the app. */
  runsInterview: boolean
  /**
   * The three stages shown in the left rail.
   *
   * Analysis is deliberately NOT a stage of its own. It is a wait, not
   * something the person does, and giving it equal weight in a three-item list
   * would make the session look like a four-step chore.
   */
  steps: readonly string[]
  /** Which stage index each route segment highlights. */
  stepOfSegment: Readonly<Record<StageSegment, number | null>>
}

const TIMELINE_STEPS = ['Siapkan data', 'Rekaman', 'Lihat hasil'] as const
const SESSION_STEPS = ['Hubungkan perangkat', 'Sesi latihan', 'Lihat hasil'] as const

export const MODES: Readonly<Record<ModeId, ModeDefinition>> = {
  v1: {
    id: 'v1',
    label: 'V1 — Deteksi',
    tagline: 'Menilai tekanan per menit sepanjang rekaman, tanpa daftar pertanyaan.',
    endpoint: '/api/v1/analyze/timeline',
    runsInterview: false,
    steps: TIMELINE_STEPS,
    stepOfSegment: { mulai: 0, sesi: null, proses: 1, hasil: 2 },
  },
  v2: {
    id: 'v2',
    label: 'V2 — Analisis Sesi',
    tagline: 'Menilai tekanan per pertanyaan, dari linimasa yang kamu isi sendiri.',
    endpoint: '/api/v1/analyze/session',
    runsInterview: false,
    steps: ['Siapkan data', 'Isi pertanyaan', 'Lihat hasil'],
    stepOfSegment: { mulai: 0, sesi: null, proses: 1, hasil: 2 },
  },
  v3: {
    id: 'v3',
    label: 'V3 — Simulasi Penuh',
    tagline: 'Wawancara berjalan di sini, linimasa pertanyaannya terisi otomatis.',
    endpoint: '/api/v1/analyze/session',
    runsInterview: true,
    steps: SESSION_STEPS,
    stepOfSegment: { mulai: 0, sesi: 1, proses: 1, hasil: 2 },
  },
}

/** Narrows an unknown path segment to a mode, or null when it is not one. */
export function toModeId(value: string | undefined): ModeId | null {
  return MODE_IDS.includes(value as ModeId) ? (value as ModeId) : null
}
