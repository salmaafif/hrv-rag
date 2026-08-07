/**
 * device.test.ts — locks the device-to-modality mapping.
 *
 * This mapping is small but load-bearing. Mandatory rule #5 says the modality
 * reaches the prompt so the model can weigh its confidence; a chest strap
 * mislabelled as a watch would have its reading discounted for motion artefacts
 * it never had, and a watch mislabelled as a chest strap would be trusted more
 * than it deserves. Neither failure announces itself on screen.
 *
 * The recognition tests matter for a second reason: the honest answer for an
 * unknown device is null, meaning "ask". A regression that starts guessing
 * would be invisible until someone checked why a result's confidence looked
 * wrong.
 */

import { describe, expect, it } from 'vitest'
import { modalityFor, recogniseWearLocation } from './device'

describe('modalityFor', () => {
  it('maps a chest sensor to ECG and a wrist sensor to PPG', () => {
    expect(modalityFor('chest')).toBe('ECG')
    expect(modalityFor('wrist')).toBe('PPG')
  })
})

describe('recogniseWearLocation', () => {
  it('recognises common chest straps', () => {
    expect(recogniseWearLocation('Polar H10')).toBe('chest')
    expect(recogniseWearLocation('Coospo H808S')).toBe('chest')
    expect(recogniseWearLocation('Magene H64')).toBe('chest')
    expect(recogniseWearLocation('Wahoo TICKR')).toBe('chest')
  })

  it('recognises common wrist devices', () => {
    expect(recogniseWearLocation('Apple Watch')).toBe('wrist')
    expect(recogniseWearLocation('Mi Smart Band 8')).toBe('wrist')
    expect(recogniseWearLocation('Amazfit GTR')).toBe('wrist')
  })

  it('separates the two Garmin families, which share a brand name', () => {
    expect(recogniseWearLocation('Garmin HRM-Dual')).toBe('chest')
    expect(recogniseWearLocation('Garmin Venu 3')).toBe('wrist')
  })

  it('places optical armbands on the wrist even when the brand suggests a strap', () => {
    // Every one of these was reported as a chest strap, which is the dangerous
    // direction: it hands the model ECG-grade confidence for an optical signal.
    //
    // Polar's H series straps; OH1 and Verity Sense are optical armbands.
    expect(recogniseWearLocation('Polar OH1')).toBe('wrist')
    expect(recogniseWearLocation('Polar OH1+')).toBe('wrist')
    expect(recogniseWearLocation('Polar Verity Sense')).toBe('wrist')
    // Wahoo TICKR and TICKR X are straps; TICKR FIT is an optical armband.
    expect(recogniseWearLocation('Wahoo TICKR FIT')).toBe('wrist')
    expect(recogniseWearLocation('Wahoo TICKR X')).toBe('chest')
    // "Dual" was meant to catch HRM-Dual, but Garmin also sells a watch called
    // Instinct 2 Dual Power.
    expect(recogniseWearLocation('Garmin Instinct 2 Dual Power')).toBe('wrist')
    expect(recogniseWearLocation('Garmin Instinct Crossover Dual Power')).toBe(
      'wrist',
    )
  })

  it('separates the two Coospo families, which share a brand name', () => {
    // H series is a chest strap, HW series is an optical armband. The brand
    // pattern alone sent both down the ECG path.
    expect(recogniseWearLocation('Coospo H6')).toBe('chest')
    expect(recogniseWearLocation('Coospo H808S')).toBe('chest')
    expect(recogniseWearLocation('Coospo H9Z')).toBe('chest')
    expect(recogniseWearLocation('Coospo HW9')).toBe('wrist')
    expect(recogniseWearLocation('Coospo HW807')).toBe('wrist')
    expect(recogniseWearLocation('Coospo HW706')).toBe('wrist')
  })

  it('returns null for anything it does not actually recognise', () => {
    // Null means "ask the person". Guessing here would silently miscalibrate
    // how much the whole session's reading is trusted.
    expect(recogniseWearLocation('HRM-2938')).toBeNull()
    expect(recogniseWearLocation('BLE Device')).toBeNull()
    expect(recogniseWearLocation('')).toBeNull()
  })
})
