/**
 * heartRateProtocol.ts — decoding the standard BLE Heart Rate Measurement packet.
 *
 * Kept separate from the connection hook because this is the part that can be
 * WRONG WITHOUT LOOKING WRONG. Every field after the flags byte sits at an offset
 * that depends on the flags, so misreading one bit shifts everything after it —
 * and the intervals still come out as plausible three-digit numbers. A resting
 * heart would simply be reported as a racing one, with nothing on screen to
 * suggest a problem.
 *
 * Splitting it out means it can be tested against packets whose correct answer is
 * known from the Bluetooth SIG specification, without any hardware present.
 *
 * The layout (Heart Rate Service 0x180D, characteristic 0x2A37):
 *
 *   byte 0        flags
 *                   bit 0  heart rate is 16-bit rather than 8-bit
 *                   bit 3  an "energy expended" field is present
 *                   bit 4  RR-interval values are present   <- what HRV needs
 *   byte 1..       heart rate      (1 or 2 bytes, little endian)
 *   then           energy expended (2 bytes, only if bit 3)
 *   then           RR intervals    (2 bytes each, only if bit 4)
 *
 * RR values are transmitted in units of 1/1024 second, NOT milliseconds.
 */

export interface HeartRateSample {
  /** Beats per minute, as reported by the device. */
  bpm: number
  /**
   * True when the device included beat-to-beat intervals.
   *
   * This is the single fact that decides whether HRV can be computed at all.
   * A device that only sends `bpm` cannot support RMSSD, because RMSSD is
   * defined as the variation BETWEEN successive beats — averaging it away at
   * source destroys the quantity rather than coarsening it.
   */
  hasRrIntervals: boolean
  /** Beat-to-beat intervals in milliseconds, oldest first. */
  rrMs: number[]
}

const FLAG_HR_16_BIT = 0x01
const FLAG_ENERGY_PRESENT = 0x08
const FLAG_RR_PRESENT = 0x10

/** One RR unit is 1/1024 of a second. */
const RR_UNITS_PER_SECOND = 1024

export function parseHeartRateMeasurement(view: DataView): HeartRateSample {
  const flags = view.getUint8(0)
  const is16Bit = (flags & FLAG_HR_16_BIT) !== 0
  const hasEnergy = (flags & FLAG_ENERGY_PRESENT) !== 0
  const hasRrIntervals = (flags & FLAG_RR_PRESENT) !== 0

  let offset = 1
  const bpm = is16Bit ? view.getUint16(offset, true) : view.getUint8(offset)
  offset += is16Bit ? 2 : 1

  // Skip the energy field if present. Forgetting this is the classic mistake:
  // its two bytes would be read as the first RR interval, and every interval
  // after it lands one pair out of step.
  if (hasEnergy) offset += 2

  const rrMs: number[] = []
  if (hasRrIntervals) {
    // A single notification may carry several intervals — a device sending
    // once a second will include every beat that happened in between.
    for (; offset + 1 < view.byteLength; offset += 2) {
      const units = view.getUint16(offset, true)
      rrMs.push((units / RR_UNITS_PER_SECOND) * 1000)
    }
  }

  return { bpm, hasRrIntervals, rrMs }
}
