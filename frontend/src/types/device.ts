/**
 * device.ts — heart sensors, described the way a person would describe them.
 *
 * The backend needs to know the modality, because ECG and PPG are not equally
 * reliable and mandatory rule #5 says that fact travels with the result. But
 * "ECG" and "PPG" are names for kinds of signal, and nobody buys a signal —
 * they buy a chest strap or a watch. Asking someone to classify their own
 * hardware by measurement principle invites a wrong answer, and a wrong
 * modality quietly miscalibrates how much confidence the reading is given.
 *
 * So the person is asked where they wear it. That is something they cannot get
 * wrong. The mapping to a modality happens here, once.
 */

import type { Modality } from './api'

/** Where the sensor sits on the body. The only question the user is asked. */
export type WearLocation = 'chest' | 'wrist'

/**
 * Chest sensors read the heart's electrical signal directly; wrist sensors
 * read blood volume through the skin with light. That is the whole of the
 * ECG/PPG distinction as far as this app is concerned.
 */
const MODALITY_OF: Record<WearLocation, Modality> = {
  chest: 'ECG',
  wrist: 'PPG',
}

export function modalityFor(location: WearLocation): Modality {
  return MODALITY_OF[location]
}

/** Indonesian labels, in device words rather than signal words. */
const WEAR_LABEL: Record<WearLocation, string> = {
  chest: 'Heart rate monitor (dipakai di dada)',
  wrist: 'Smartwatch atau gelang (di pergelangan tangan)',
}

export function wearLabel(location: WearLocation): string {
  return WEAR_LABEL[location]
}

export interface HeartDevice {
  id: string
  name: string
  /**
   * Null when the device is not one we recognise.
   *
   * Null is not a default to be filled in with a guess. It means the app has to
   * ask, because getting this wrong changes how much the result is trusted.
   */
  wornAt: WearLocation | null
}

/**
 * Recognise where a device is worn from its advertised Bluetooth name.
 *
 * Deliberately conservative: it matches families of devices that are
 * unambiguous, and returns null for everything else rather than guessing from
 * a partial resemblance. A standard Bluetooth heart rate service says nothing
 * about where the sensor sits — chest straps and watches both use it — so the
 * name is the only clue available, and it is not always enough.
 */
const CHEST_PATTERNS = [
  /\bpolar\s*(h\d|oh1|verity)/i,
  /\bcoospo\b/i,
  /\bmagene\b/i,
  /\bwahoo\b.*\btickr\b/i,
  /\bdecathlon\b.*\bdual\b/i,
  /\bgarmin\b.*\b(hrm|dual)\b/i,
]

const WRIST_PATTERNS = [
  /\bwatch\b/i,
  /\bband\b/i,
  /\bmi\s*smart\b/i,
  /\bfitbit\b/i,
  /\bamazfit\b/i,
  /\bgarmin\b.*\b(venu|vivo|forerunner|instinct)\b/i,
]

export function recogniseWearLocation(name: string): WearLocation | null {
  if (CHEST_PATTERNS.some((pattern) => pattern.test(name))) return 'chest'
  if (WRIST_PATTERNS.some((pattern) => pattern.test(name))) return 'wrist'
  return null
}
