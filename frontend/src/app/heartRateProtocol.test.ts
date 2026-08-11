/**
 * heartRateProtocol.test.ts — packets whose correct answer comes from the spec.
 *
 * No hardware needed, and none would help: a real strap sends one flag
 * combination, while the failures here live in the combinations it does NOT
 * send. Offsets shift with the flags, so a decoder can work perfectly against
 * one device and silently corrupt every reading from the next.
 *
 * Corrupt in the worst possible way, too — misread intervals stay in the 500 to
 * 1500 range, so nothing downstream can tell that a calm person is being
 * reported as an agitated one.
 */

import { describe, expect, it } from 'vitest'
import { parseHeartRateMeasurement } from './heartRateProtocol'

/** Build a packet from raw bytes. */
const packet = (...bytes: number[]) =>
  new DataView(new Uint8Array(bytes).buffer)

/** Encode milliseconds the way the spec does: units of 1/1024 second. */
const rr = (ms: number) => {
  const units = Math.round((ms / 1000) * 1024)
  return [units & 0xff, units >> 8]
}

describe('parseHeartRateMeasurement', () => {
  it('reads an 8-bit heart rate with no extra fields', () => {
    const sample = parseHeartRateMeasurement(packet(0x00, 72))
    expect(sample.bpm).toBe(72)
    expect(sample.hasRrIntervals).toBe(false)
    expect(sample.rrMs).toEqual([])
  })

  it('reports the absence of RR intervals rather than returning zero', () => {
    // The distinction the whole module exists for. A device sending only bpm
    // cannot support RMSSD at all, and that has to surface as "not available"
    // rather than as an empty measurement someone might average.
    expect(parseHeartRateMeasurement(packet(0x00, 60)).hasRrIntervals).toBe(false)
    expect(parseHeartRateMeasurement(packet(0x10, 60, ...rr(1000))).hasRrIntervals)
      .toBe(true)
  })

  it('converts RR units of 1/1024 s into milliseconds', () => {
    const sample = parseHeartRateMeasurement(packet(0x10, 70, ...rr(850)))
    expect(sample.rrMs[0]).toBeCloseTo(850, 0)
  })

  it('reads several intervals from one notification', () => {
    // A device notifying once a second reports every beat since the last one.
    const sample = parseHeartRateMeasurement(
      packet(0x10, 70, ...rr(900), ...rr(880), ...rr(910)),
    )
    expect(sample.rrMs.map(Math.round)).toEqual([900, 880, 910])
  })

  it('shifts correctly when the heart rate is 16-bit', () => {
    // Reading the value as 8-bit would leave one stray byte, and every interval
    // afterwards would be assembled from the wrong pair of bytes.
    const sample = parseHeartRateMeasurement(
      packet(0x11, 0x48, 0x00, ...rr(1000)),
    )
    expect(sample.bpm).toBe(72)
    expect(sample.rrMs.map(Math.round)).toEqual([1000])
  })

  it('skips the energy-expended field before reading intervals', () => {
    // Flags 0x19 = 16-bit heart rate + energy + RR. Failing to skip the two
    // energy bytes turns them into a fabricated first interval.
    const sample = parseHeartRateMeasurement(
      packet(0x19, 0x50, 0x00, 0xff, 0x00, ...rr(600)),
    )
    expect(sample.bpm).toBe(80)
    expect(sample.rrMs.map(Math.round)).toEqual([600])
  })

  it('skips energy even with an 8-bit heart rate', () => {
    const sample = parseHeartRateMeasurement(
      packet(0x18, 65, 0x2c, 0x01, ...rr(920)),
    )
    expect(sample.bpm).toBe(65)
    expect(sample.rrMs.map(Math.round)).toEqual([920])
  })

  it('ignores a trailing odd byte instead of reading past the buffer', () => {
    // Intervals are two bytes each. A stray byte must be dropped, not turned
    // into a reading built from whatever memory follows.
    const sample = parseHeartRateMeasurement(packet(0x10, 70, ...rr(800), 0x0a))
    expect(sample.rrMs.map(Math.round)).toEqual([800])
  })
})
