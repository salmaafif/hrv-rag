/**
 * stages.ts — the screens of an interview session, in order.
 *
 * The demo used to run three versions side by side: V1 scored a recording per
 * minute, V2 took a question timeline typed in afterwards, and V3 ran the
 * interview itself. Only the interview remains. It is the one the product is,
 * and the only one that knows when each question was really asked — because it
 * asked them.
 */

export type StageSegment = 'mulai' | 'sesi' | 'unggah' | 'proses' | 'hasil'

export const STAGES: readonly StageSegment[] = [
  'mulai',
  'sesi',
  'unggah',
  'proses',
  'hasil',
]

/**
 * The three steps shown in the left rail.
 *
 * Analysis is deliberately NOT a step of its own. It is a wait, not something
 * the person does, and giving it equal weight in a three-item list would make
 * the session look like a four-step chore.
 */
export const SESSION_STEPS = [
  'Hubungkan perangkat',
  'Sesi latihan',
  'Lihat hasil',
] as const

/** Which step each screen highlights. */
export const STEP_OF_STAGE: Readonly<Record<StageSegment, number>> = {
  mulai: 0,
  sesi: 1,
  unggah: 1,
  proses: 1,
  hasil: 2,
}

export function isStage(value: string | undefined): value is StageSegment {
  return STAGES.includes(value as StageSegment)
}
