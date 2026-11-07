/**
 * format.test.ts — locks the formatting rules that carry meaning.
 *
 * Most of these are ordinary label lookups. The ones that matter are the
 * recovery cases: they are the executable form of the rule in
 * `docs/frontend_plan.md` that a missing measurement must never be shown as a
 * measured zero. If someone later "simplifies" formatRecovery with `?? 0`,
 * these fail.
 */

import { describe, expect, it } from 'vitest'
import {
  NOT_MEASURED,
  formatClock,
  formatDuration,
  formatLevel,
  formatModality,
  formatQuestionType,
  formatRecovery,
  formatRecoveryNote,
  formatResilience,
  formatSignedPercent,
  hasMeasurement,
} from './format'

describe('formatRecoveryNote', () => {
  /**
   * The backend's reasons are English code strings. Shown raw they put an
   * English sentence on an Indonesian screen, which is what happened.
   */
  it('translates the reasons the backend actually sends', () => {
    expect(formatRecoveryNote(
      'this device reports heart rate only, and recovery is read from ' +
      'beat-to-beat variability, so it was not measured',
    )).toContain('hanya mengirim detak jantung')
    expect(formatRecoveryNote('no quiet gap followed this question'))
      .toContain('Tidak ada jeda')
    expect(formatRecoveryNote('gap produced no usable segment'))
      .toContain('Jeda setelah pertanyaan ini')
    // Written with the measured figures filled in, so matched by its opening.
    expect(formatRecoveryNote('reaction too small (4.2% < 10%)'))
      .toContain('terlalu kecil')
  })

  it('never lets an unknown reason through as it arrived', () => {
    const shown = formatRecoveryNote('some reason added next year')
    expect(shown).not.toContain('reason')
    expect(shown).toBe('Pemulihan tidak bisa dihitung untuk pertanyaan ini.')
  })

  it('keeps numbers and feature names off the screen', () => {
    const shown = formatRecoveryNote('reaction too small (4.2% < 10%)')
    for (const forbidden of ['4.2', '10%', 'RMSSD', 'variability']) {
      expect(shown).not.toContain(forbidden)
    }
  })

  it('still says something when the reason is empty', () => {
    expect(formatRecoveryNote('')).toContain('Tidak ada jeda')
  })
})

describe('formatRecovery', () => {
  it('says "tidak diukur" when recovery could not be measured', () => {
    expect(formatRecovery(null)).toBe(NOT_MEASURED)
  })

  it('shows a measured zero as 0%, not as "tidak diukur"', () => {
    // Zero means the reaction had not faded at all by the time the next
    // question began. That is a real, and fairly bad, result — it must not be
    // hidden behind the words used for "we could not tell".
    expect(formatRecovery(0)).toBe('0%')
  })

  it('never renders null and zero the same way', () => {
    // The single assertion this whole file exists for.
    expect(formatRecovery(null)).not.toBe(formatRecovery(0))
  })

  it('renders an ordinary percentage', () => {
    expect(formatRecovery(68)).toBe('68%')
  })

  it('rounds to whole percent', () => {
    expect(formatRecovery(12.4)).toBe('12%')
    expect(formatRecovery(12.6)).toBe('13%')
  })

  it('treats non-finite numbers as not measured rather than printing NaN', () => {
    expect(formatRecovery(Number.NaN)).toBe(NOT_MEASURED)
    expect(formatRecovery(Number.POSITIVE_INFINITY)).toBe(NOT_MEASURED)
  })
})

describe('hasMeasurement', () => {
  it('accepts zero, because zero is a measurement', () => {
    expect(hasMeasurement(0)).toBe(true)
  })

  it('rejects null and non-finite values', () => {
    expect(hasMeasurement(null)).toBe(false)
    expect(hasMeasurement(Number.NaN)).toBe(false)
  })
})

describe('formatLevel', () => {
  it('labels every level in Indonesian', () => {
    expect(formatLevel('low')).toBe('Rendah')
    expect(formatLevel('moderate')).toBe('Sedang')
    expect(formatLevel('high')).toBe('Tinggi')
  })
})

describe('formatResilience', () => {
  it('refuses to name a quadrant when there is none', () => {
    // Null here is the backend declining to answer because recovery could not
    // be measured. Inventing a quadrant would manufacture a conclusion.
    expect(formatResilience(null)).toBe('Belum dapat disimpulkan')
  })

  it('describes each quadrant by what happened, not by a verdict word', () => {
    expect(formatResilience('high resilience')).toBe('Reaksi kecil, pulih cepat')
    expect(formatResilience('held-in tension')).toBe('Reaksi kecil, pulih lambat')
    expect(formatResilience('responsive but flexible')).toBe(
      'Reaksi besar, pulih cepat',
    )
    expect(formatResilience('low resilience')).toBe('Reaksi besar, pulih lambat')
  })
})

describe('formatModality', () => {
  it('names the device, since ECG and PPG do not earn equal confidence', () => {
    expect(formatModality('ECG')).toBe('Chest strap (ECG)')
    expect(formatModality('PPG')).toBe('Smartwatch (PPG)')
  })
})

describe('formatQuestionType', () => {
  it('labels every question type', () => {
    expect(formatQuestionType('introduction')).toBe('Perkenalan')
    expect(formatQuestionType('behavioural')).toBe('Pengalaman')
    expect(formatQuestionType('technical')).toBe('Teknis')
    expect(formatQuestionType('numerical')).toBe('Hitungan')
    expect(formatQuestionType('situational')).toBe('Situasional')
  })
})

describe('formatClock', () => {
  it('pads to mm:ss', () => {
    expect(formatClock(92)).toBe('01:32')
    expect(formatClock(0)).toBe('00:00')
    expect(formatClock(600)).toBe('10:00')
  })

  it('clamps negatives instead of rendering "-1:-1"', () => {
    expect(formatClock(-5)).toBe('00:00')
  })
})

describe('formatDuration', () => {
  it('reports whole minutes', () => {
    expect(formatDuration(900)).toBe('15 menit')
  })
})

describe('formatSignedPercent', () => {
  it('always writes the direction', () => {
    expect(formatSignedPercent(85.9)).toBe('+85.9%')
    expect(formatSignedPercent(-79.8)).toBe('-79.8%')
  })

  it('leaves an unchanged value unsigned', () => {
    expect(formatSignedPercent(0)).toBe('0.0%')
  })

  it('falls back to "tidak diukur" rather than NaN', () => {
    expect(formatSignedPercent(null)).toBe(NOT_MEASURED)
  })
})
