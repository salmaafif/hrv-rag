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

/**
 * Indonesian labels, in device words rather than signal words.
 *
 * The wrist option deliberately says "armband", not "smartwatch". A consumer
 * smartwatch (Apple Watch, Galaxy Watch, Fitbit, Garmin's own watches) keeps
 * its heart-rate reading inside its own app and does not expose the standard
 * Bluetooth Heart Rate Service Web Bluetooth pairs against — so offering
 * "smartwatch" as a choice here promised a connection this app cannot make.
 * Only chest straps and dedicated optical armbands (Polar OH1, Coospo HW-series)
 * broadcast that standard service.
 */
const WEAR_LABEL: Record<WearLocation, string> = {
  chest: 'Chest strap (dipakai di dada)',
  wrist: 'Armband (di pergelangan tangan)',
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
/**
 * Optical sensors that are easy to mistake for chest straps.
 *
 * Checked FIRST, because each of these carries a brand or model word that the
 * chest list also matches, and the chest list used to win:
 *
 * - Polar OH1, OH1+ and Verity Sense are optical armbands, not straps. They were
 *   listed as chest outright.
 * - Wahoo TICKR FIT is an optical armband; only TICKR and TICKR X go on the chest.
 * - Garmin Instinct 2 Dual Power is a watch. The chest pattern looked for "dual"
 *   anywhere after "garmin", intending HRM-Dual, and swallowed it.
 *
 * Each mistake reported PPG hardware as ECG. That is not cosmetic: modality is
 * carried into the prompt precisely so the model can hold an optical reading to a
 * lower confidence (Mandatory Rule #5), and nothing downstream can tell it was
 * lied to. It would raise its confidence on exactly the signal that deserves less.
 */
const OPTICAL_OVERRIDES = [
  /\bpolar\s*(oh1|verity)/i,
  /\bwahoo\b.*\btickr\s*fit\b/i,
  /\bgarmin\b.*\binstinct\b/i,
  // Coospo sells both: the H series (H6, H808S, H9Z) are chest straps, the HW
  // series (HW9, HW807, HW706) are optical armbands. Matching the brand alone
  // sent every one of them down the ECG path.
  /\bcoospo\b.*\bhw\d/i,
  // The advertised Bluetooth name for these often omits "Coospo" entirely —
  // an HW9 paired in practice as plain "HW9 25819", brand nowhere in sight.
  // "HW" followed by a digit is distinctive enough on its own to trust.
  /\bhw\d/i,
]

const CHEST_PATTERNS = [
  /\bpolar\s*h\d/i,
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
  if (OPTICAL_OVERRIDES.some((pattern) => pattern.test(name))) return 'wrist'
  if (CHEST_PATTERNS.some((pattern) => pattern.test(name))) return 'chest'
  if (WRIST_PATTERNS.some((pattern) => pattern.test(name))) return 'wrist'
  return null
}
