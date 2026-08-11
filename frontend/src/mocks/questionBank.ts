/**
 * questionBank.ts — the questions V3 asks.
 *
 * A fixture for now. In the real product this comes from KARIRLINK's question
 * bank, chosen for the role being practised; nothing in this app depends on
 * where the list originates, only on its shape.
 *
 * `isDifficult` is not a judgement about the person. It marks questions known
 * to provoke a stronger reaction in most people, which the backend uses as
 * context when reading someone's response to them.
 */

import type { QuestionType } from '../types/api'

export interface BankQuestion {
  text: string
  type: QuestionType
  isDifficult: boolean
  /** Shown while the question is on screen. Never a judgement of the answer. */
  tip: string
}

export const questionBank: BankQuestion[] = [
  {
    text: 'Ceritakan tentang dirimu',
    type: 'introduction',
    isDifficult: false,
    tip: 'Cukup dua menit. Mulai dari yang paling relevan dengan posisi ini.',
  },
  {
    text: 'Kenapa kami harus memilihmu?',
    type: 'behavioural',
    isDifficult: false,
    tip: 'Fokus ke dua atau tiga kelebihan, bukan seluruh riwayatmu.',
  },
  {
    text: 'Sebutkan kekuranganmu',
    type: 'behavioural',
    isDifficult: true,
    tip: 'Pilih satu yang sedang kamu perbaiki, lalu ceritakan langkahnya.',
  },
  {
    text: 'Ceritakan konflik di tim dan cara mengatasinya',
    type: 'situational',
    isDifficult: true,
    tip: 'Ceritakan situasinya, apa yang kamu lakukan, lalu hasilnya.',
  },
  {
    text: 'Berapa ekspektasi gajimu?',
    type: 'numerical',
    isDifficult: true,
    tip: 'Sebutkan rentang, bukan satu angka mati.',
  },
  {
    text: 'Ada pertanyaan untuk kami?',
    type: 'introduction',
    isDifficult: false,
    tip: 'Satu pertanyaan tentang cara kerja tim sehari-hari sudah cukup.',
  },
]
