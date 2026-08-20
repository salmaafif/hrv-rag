/**
 * uji-protokol-hrv.logic.js — the arithmetic behind the three-block device test.
 *
 * Split out of `uji-protokol-hrv.html` for one reason: this file decides whether a
 * sensor is returned to the shop or kept for the whole thesis, and a decision that
 * heavy should not rest on code that nothing can test. The page itself keeps only
 * the parts that need a browser — GATT connection, the DOM, the canvas.
 *
 * PLAIN ES MODULE, NO BUILD STEP. The page loads it with
 * `<script type="module" src="./uji-protokol-hrv.logic.js">`, so it still runs
 * under a bare `python -m http.server` with no bundler present. Vitest imports the
 * same file directly, so what is tested is exactly what runs.
 *
 * ---------------------------------------------------------------------------
 * THE RULE THIS FILE EXISTS TO OBEY
 *
 * Every threshold below mirrors `src/hrv_rag/config/settings.py`, and every
 * procedure mirrors the Python that produced the validated WESAD numbers. That is
 * not tidiness — it is the whole point. The go/no-go criteria for the device are
 * written in terms of "outlier %", "eligible segments" and "resting RMSSD". If
 * this file computes those three quantities by a different method than the
 * pipeline does, the test measures something the thesis never validated, and a
 * device could be returned (or kept) on the strength of a number that means
 * nothing.
 *
 * Where a constant appears here it names its Python source, so a change on one
 * side is findable from the other.
 * ---------------------------------------------------------------------------
 */

// === Quality thresholds — mirror of `QualityConfig` in settings.py ===========

/** Physiological interval bounds: 300 ms = 200 bpm, 2000 ms = 30 bpm. */
export const RR_MIN_MS = 300
export const RR_MAX_MS = 2000

/**
 * Largest change from the preceding interval still considered plausible
 * (the Malik criterion). `QualityConfig.max_rel_diff`.
 */
export const MAX_REL_DIFF = 0.2

/**
 * A window with more than this fraction of flagged beats is discarded.
 * `QualityConfig.max_outlier_ratio`.
 */
export const MAX_OUTLIER_RATIO = 0.1

// === Segmentation — mirror of `SegmentationConfig` in settings.py ===========

export const SEGMENT_LENGTH_SEC = 60
export const SEGMENT_HOP_SEC = 30

/**
 * Fewest beats a 60-second window may contain and still be analysed.
 *
 * 30 beats per minute is the lower physiological bound, so anything below it is
 * failed detection rather than a slow heart. `SegmentationConfig.min_beats`.
 *
 * The page previously used 20 here. Twenty beats in a minute is not a person; it
 * is a sensor that stopped reporting for half the window — which is precisely the
 * failure this test is meant to catch, so counting it as a usable window inverted
 * the tool's purpose.
 */
export const SEGMENT_MIN_BEATS = 30

// === BLE packet decoding ====================================================

const FLAG_HR_16_BIT = 0x01
const FLAG_ENERGY_PRESENT = 0x08
const FLAG_RR_PRESENT = 0x10

/** RR values travel in units of 1/1024 second, not milliseconds. */
const RR_UNITS_PER_SECOND = 1024

/**
 * Decode one Heart Rate Measurement notification (service 0x180D, char 0x2A37).
 *
 *   byte 0    flags — bit 0: 16-bit HR · bit 3: energy field · bit 4: RR present
 *   byte 1..  heart rate (1 or 2 bytes, little endian)
 *   then      energy expended (2 bytes, only when bit 3)
 *   then      RR intervals    (2 bytes each, only when bit 4)
 *
 * Every field sits at an offset that depends on the flags, so misreading one bit
 * shifts everything after it — and the intervals still emerge as plausible
 * three-digit numbers. Skipping the energy field is the classic slip: its two
 * bytes get read as the first interval and the whole series lands one pair out of
 * step, turning a resting heart into a racing one with nothing on screen to say so.
 *
 * The React app carries its own typed copy in `src/app/heartRateProtocol.ts`,
 * because that one is bundled and this one must load without a build step. A test
 * runs both against the same packets so the two cannot drift apart.
 */
export function parseHeartRateMeasurement(view) {
  const flags = view.getUint8(0)
  const is16Bit = (flags & FLAG_HR_16_BIT) !== 0
  const hasEnergy = (flags & FLAG_ENERGY_PRESENT) !== 0
  const hasRrIntervals = (flags & FLAG_RR_PRESENT) !== 0

  let offset = 1
  const bpm = is16Bit ? view.getUint16(offset, true) : view.getUint8(offset)
  offset += is16Bit ? 2 : 1

  if (hasEnergy) offset += 2

  const rrMs = []
  if (hasRrIntervals) {
    for (; offset + 1 < view.byteLength; offset += 2) {
      const units = view.getUint16(offset, true)
      rrMs.push((units / RR_UNITS_PER_SECOND) * 1000)
    }
  }

  return { bpm, hasRrIntervals, rrMs }
}

// === Ectopic correction — mirror of `correct_ectopic` in preprocessing/base.py ===

/**
 * Flag implausible beats and repair them by linear interpolation.
 *
 * Two criteria, both from CLAUDE.md:
 *   1. outside 300-2000 ms;
 *   2. differing by more than 20% from the immediately preceding interval.
 *
 * Criterion 2 is evaluated against the ORIGINAL values throughout, never against
 * a repaired one, so a single bad beat cannot start a cascade of rejections. A
 * real ectopic beat produces two deviant intervals — one short, then a
 * compensatory long one — and flagging both is the intended behaviour.
 *
 * REPAIR BY INTERPOLATION, NOT DELETION. The page used to drop flagged beats and
 * compute RMSSD from what was left. That silently fabricates data: removing beat
 * *i* makes beats *i-1* and *i+1* adjacent, and RMSSD is defined entirely on
 * adjacency, so it then measures a difference between two beats that never
 * followed one another. It also shortens the window without saying so, which is
 * why `base.py` chose interpolation and why this must match it.
 *
 * @param {number[]} rrMs
 * @returns {{corrected: number[], isOutlier: boolean[]}}
 */
export function correctEctopic(rrMs) {
  const n = rrMs.length
  const isOutlier = new Array(n).fill(false)
  if (n === 0) return { corrected: [], isOutlier }

  for (let i = 0; i < n; i++) {
    if (rrMs[i] < RR_MIN_MS || rrMs[i] > RR_MAX_MS) isOutlier[i] = true
  }
  for (let i = 1; i < n; i++) {
    if (Math.abs(rrMs[i] - rrMs[i - 1]) / rrMs[i - 1] > MAX_REL_DIFF) isOutlier[i] = true
  }

  const good = []
  for (let i = 0; i < n; i++) if (!isOutlier[i]) good.push(i)

  // Every beat flagged leaves nothing to interpolate from, so the values are
  // returned untouched — matching numpy's guard `0 < n_bad < n`. The window will
  // be rejected on its outlier ratio anyway.
  if (good.length === 0 || good.length === n) return { corrected: rrMs.slice(), isOutlier }

  const corrected = rrMs.slice()
  for (let i = 0; i < n; i++) {
    if (!isOutlier[i]) continue
    corrected[i] = interpolateAt(i, good, rrMs)
  }
  return { corrected, isOutlier }
}

/**
 * Value at index `i` interpolated from the nearest good indices either side.
 *
 * Outside the range of good indices numpy's `interp` clamps to the end value
 * rather than extrapolating, and this does the same — a run of bad beats at the
 * very start or end must not be replaced by an invented trend.
 */
function interpolateAt(i, good, rrMs) {
  if (i < good[0]) return rrMs[good[0]]
  if (i > good[good.length - 1]) return rrMs[good[good.length - 1]]
  let k = 0
  while (good[k + 1] < i) k++
  const lo = good[k]
  const hi = good[k + 1]
  const w = (i - lo) / (hi - lo)
  return rrMs[lo] + w * (rrMs[hi] - rrMs[lo])
}

// === Time-domain features — mirror of features/time_domain.py ===============

/** Mean interval (ms). */
export function meanRr(rrMs) {
  if (rrMs.length === 0) return null
  return rrMs.reduce((a, b) => a + b, 0) / rrMs.length
}

/**
 * Mean heart rate (bpm), derived from meanRR.
 *
 * 60000/mean(RR) is NOT mean(60000/RR) — division is non-linear — and the HRV
 * literature uses the former.
 */
export function meanHr(rrMs) {
  const m = meanRr(rrMs)
  return m === null ? null : 60000 / m
}

/** Root mean square of successive differences (ms). Needs at least two beats. */
export function rmssd(rrMs) {
  if (rrMs.length < 2) return null
  let sum = 0
  for (let i = 1; i < rrMs.length; i++) {
    const d = rrMs[i] - rrMs[i - 1]
    sum += d * d
  }
  return Math.sqrt(sum / (rrMs.length - 1))
}

/** Median of a numeric list, or null when empty. */
export function median(values) {
  if (values.length === 0) return null
  const s = [...values].sort((a, b) => a - b)
  const mid = s.length >> 1
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

// === Beat timing ============================================================

/**
 * Timestamp every beat carried by one BLE notification.
 *
 * Each interval is timestamped at the beat that ENDS it, matching
 * `rr_series_from_intervals` in the Python pipeline. One packet routinely carries
 * two or three beats, so the packet's arrival time belongs to the LAST of them and
 * the earlier ones are placed backwards by their own interval lengths. Stamping
 * them all with the arrival time — what the page did before — piled several beats
 * onto a single instant and left gaps between packets, distorting which beats fall
 * inside which 60-second window.
 *
 * Anchoring on arrival rather than accumulating intervals from session start is
 * the deliberate choice, and it matters most in exactly the case this tool exists
 * for. When a sensor drops beats, an accumulated clock shrinks the time axis by
 * the length of the dropout and the recording looks continuous; an arrival-anchored
 * clock leaves a real gap, so the affected windows fall below `SEGMENT_MIN_BEATS`
 * and are correctly reported as lost.
 *
 * `lastT` keeps the series monotonic: a delayed packet could otherwise extrapolate
 * backwards past a beat already recorded.
 *
 * @param {number[]} rrMs      intervals in this packet, oldest first
 * @param {number} arrivalSec  seconds since session start
 * @param {number|null} lastT  timestamp of the previously recorded beat
 * @returns {number[]} one timestamp per interval
 */
export function beatTimes(rrMs, arrivalSec, lastT) {
  const n = rrMs.length
  if (n === 0) return []

  const times = new Array(n)
  let t = arrivalSec
  for (let i = n - 1; i >= 0; i--) {
    times[i] = t
    t -= rrMs[i] / 1000
  }

  if (lastT === null || lastT === undefined) return times

  // Push forward, preserving spacing, only far enough to clear the last beat.
  const overlap = lastT - times[0]
  if (overlap > 0) {
    const shift = overlap + 1e-3
    for (let i = 0; i < n; i++) times[i] += shift
  }
  return times
}

// === Segmentation — mirror of `segment_rr_series` in features/segmentation.py ===

/**
 * Count the 60-second windows a phase produces and how many survive the gates.
 *
 * Windows are placed by TIME, not by beat count, so each really covers 60 seconds:
 * window *k* starts at `t0 + k * 30`. A tail shorter than 60 seconds is discarded
 * so every window has equal duration.
 *
 * Both rejection reasons are counted and both stay in the denominator. The page
 * used to skip short windows without counting them, so a block that lost five of
 * its eight windows to dropout reported "3 / 3" — a perfect score produced by
 * missing data.
 *
 * @param {number[]} tSec        beat timestamps, ascending
 * @param {boolean[]} isOutlier  flags aligned with `tSec`
 * @returns {{eligible: number, total: number, droppedShort: number,
 *            droppedNoisy: number, windows: {startSec: number, indices: number[],
 *            outlierRatio: number}[]}}
 */
export function segmentYield(tSec, isOutlier) {
  const empty = { eligible: 0, total: 0, droppedShort: 0, droppedNoisy: 0, windows: [] }
  if (tSec.length === 0) return empty

  const t0 = tSec[0]
  const duration = tSec[tSec.length - 1] - t0
  if (duration < SEGMENT_LENGTH_SEC) return empty

  const nWindows = Math.floor((duration - SEGMENT_LENGTH_SEC) / SEGMENT_HOP_SEC) + 1

  let eligible = 0
  let droppedShort = 0
  let droppedNoisy = 0
  const windows = []

  for (let k = 0; k < nWindows; k++) {
    const start = t0 + k * SEGMENT_HOP_SEC
    const end = start + SEGMENT_LENGTH_SEC

    const indices = []
    for (let i = 0; i < tSec.length; i++) {
      if (tSec[i] >= start && tSec[i] < end) indices.push(i)
    }

    if (indices.length < SEGMENT_MIN_BEATS) {
      droppedShort++
      continue
    }
    const ratio = indices.filter((i) => isOutlier[i]).length / indices.length
    if (ratio > MAX_OUTLIER_RATIO) {
      droppedNoisy++
      continue
    }
    eligible++
    windows.push({ startSec: start - t0, indices, outlierRatio: ratio })
  }

  return { eligible, total: nWindows, droppedShort, droppedNoisy, windows }
}

// === Per-block summary ======================================================

/**
 * Everything the results table shows for one block of the protocol.
 *
 * `rmssdSegments` is the list of per-window RMSSD values, and it is reported
 * rather than reduced to a single number on purpose. The locked criteria in the
 * acquisition document include "RMSSD jumping wildly between segments of the same
 * block" as a failure, and no threshold for "wildly" is defensible enough to
 * automate — so the values are put on screen and the judgement stays human.
 *
 * @param {number[]} rrMs  raw intervals for this block, in packet order
 * @param {number[]} tSec  matching beat timestamps
 */
/** Median of a numeric array. Local so this module stays dependency-free. */
function medianOf(values) {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = sorted.length >> 1
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2
}

/**
 * A gap counts as a dropout once it is this many typical beats long.
 *
 * Two and a half rather than two: a genuine sinus pause plus one late packet can
 * reach two, and calling that a dropout would flag ordinary recordings.
 */
export const DROPOUT_BEATS = 2.5

/**
 * Where the recording stopped receiving beats, and for how long.
 *
 * THE OUTLIER RULE CANNOT SEE THIS, and that is the whole reason the function
 * exists. T1.5 flags an interval that is out of range or more than 20% from its
 * predecessor. A dropout leaves neither trace: the beat arriving after a
 * fourteen-second silence is an ordinary ~700 ms interval sitting next to
 * another ordinary ~700 ms interval. Measured on the first HW9 protocol run,
 * only 8 of 30 gaps happened to be flagged — the other 22 passed as clean data.
 *
 * What is lost is sample count rather than accuracy: on that same run, dropping
 * every pair that straddles a gap moved RMSSD by at most 0.53 ms. The danger is
 * a block that quietly rests on three quarters of the beats it claims.
 *
 * @param {number[]} tSec beat timestamps, seconds, ascending
 * @param {number[]} rrMs matching intervals, used only for the typical length
 */
export function dropouts(tSec, rrMs) {
  if (tSec.length < 2) return { count: 0, seconds: 0, coveragePct: 100 }
  const typical = medianOf(rrMs) / 1000
  const limit = DROPOUT_BEATS * typical

  let count = 0
  let seconds = 0
  for (let i = 0; i < tSec.length - 1; i++) {
    const gap = tSec[i + 1] - tSec[i]
    if (gap > limit) {
      count++
      seconds += gap
    }
  }

  const elapsed = tSec[tSec.length - 1] - tSec[0]
  const covered = rrMs.reduce((a, b) => a + b, 0) / 1000
  return {
    count,
    seconds,
    // Share of wall-clock time actually spanned by intervals. Below ~90% the
    // block rests on fewer beats than its duration implies.
    coveragePct: elapsed > 0 ? Math.min(100, (covered / elapsed) * 100) : 100,
  }
}

export function phaseStats(rrMs, tSec) {
  if (rrMs.length === 0) return null

  const { corrected, isOutlier } = correctEctopic(rrMs)
  const seg = segmentYield(tSec, isOutlier)

  const rmssdSegments = seg.windows.map((w) => rmssd(w.indices.map((i) => corrected[i])))
  const drop = dropouts(tSec, rrMs)

  return {
    nBeats: rrMs.length,
    outlierPct: (isOutlier.filter(Boolean).length / rrMs.length) * 100,
    segEligible: seg.eligible,
    segTotal: seg.total,
    segDroppedShort: seg.droppedShort,
    segDroppedNoisy: seg.droppedNoisy,
    meanHr: meanHr(corrected),
    // Whole-block RMSSD, kept because it is defined even when no window survives.
    rmssd: rmssd(corrected),
    rmssdSegments,
    rmssdMedian: median(rmssdSegments.filter((v) => v !== null)),
    dropoutCount: drop.count,
    dropoutSeconds: drop.seconds,
    coveragePct: drop.coveragePct,
  }
}

// === Gate 1: is the RR field real? (HW8) ====================================

/**
 * Fewest beats before the synthetic-RR verdict is worth stating.
 *
 * Raised from 20 when signature 3 replaced the distinct-value count: a
 * correlation over a handful of grid rungs is noise, and a verdict this
 * expensive should not be delivered from noise.
 */
export const SYNTHETIC_MIN_SAMPLES = 60

/**
 * How far the gap-spacing correlation may climb before a device is condemned.
 *
 * Measured, not guessed. On simulated series and on a real HW9 recording the
 * two populations sit far apart: genuine intervals top out around +0.32,
 * `60000 / bpm` series start at +0.97. The threshold sits in the empty middle,
 * so neither side is anywhere near it.
 */
export const BPM_GRID_CORRELATION_LIMIT = 0.7

/**
 * How strongly the spacing between neighbouring RR values grows with RR².
 *
 * This is the signature that separates a coarse clock from a fabricated series,
 * and it works by arithmetic rather than by a tuned threshold. A device
 * reporting `60000 / bpm` can only emit the values integer bpm allows, and those
 * are not evenly spaced: neighbours sit `60000/b - 60000/(b+1)` apart, which
 * grows as RR². At 110 bpm the rungs are 5 ms apart; at 69 bpm, 12 ms. A device
 * with a coarse but honest beat clock quantises in TIME, so its rungs are
 * equally spaced everywhere and the correlation collapses to zero.
 *
 * Gaps far wider than the median are dropped before correlating: those are rungs
 * the recording never landed on, not evidence about spacing.
 *
 * @param {number[]|Set<number>} values every RR seen; duplicates are fine
 * @returns {number|null} Pearson r, or null when there is not enough spread
 */
export function bpmGridCorrelation(values) {
  const unique = [...new Set(values)].sort((a, b) => a - b)
  if (unique.length < 10) return null

  const allGaps = []
  for (let i = 0; i < unique.length - 1; i++) allGaps.push(unique[i + 1] - unique[i])
  const typical = medianOf(allGaps)

  const xs = []
  const ys = []
  for (let i = 0; i < unique.length - 1; i++) {
    const gap = unique[i + 1] - unique[i]
    if (gap > 2.5 * typical) continue
    xs.push(unique[i] * unique[i])
    ys.push(gap)
  }
  if (xs.length < 8) return null

  const meanX = xs.reduce((a, b) => a + b, 0) / xs.length
  const meanY = ys.reduce((a, b) => a + b, 0) / ys.length
  let num = 0
  let varX = 0
  let varY = 0
  for (let i = 0; i < xs.length; i++) {
    const dx = xs[i] - meanX
    const dy = ys[i] - meanY
    num += dx * dy
    varX += dx * dx
    varY += dy * dy
  }
  return varX && varY ? num / Math.sqrt(varX * varY) : null
}

/**
 * The device's timing resolution in milliseconds, or null when it cannot be seen.
 *
 * Reported, not judged. A coarse clock does not disqualify a sensor — the HW9's
 * 7.6 ms grid moves resting RMSSD by about a tenth of a millisecond — but it is
 * a property of the instrument, so it belongs in the export and in the write-up
 * rather than being discovered later by someone squinting at a tachogram.
 *
 * Estimated as the median spacing between neighbouring distinct values, which is
 * robust to whichever rungs a recording happened to skip.
 *
 * @param {number[]|Set<number>} values
 * @returns {number|null}
 */
export function timingResolutionMs(values) {
  const unique = [...new Set(values)].sort((a, b) => a - b)
  if (unique.length < 10) return null
  const gaps = []
  for (let i = 0; i < unique.length - 1; i++) gaps.push(unique[i + 1] - unique[i])
  return medianOf(gaps)
}

/**
 * Decide whether a device is sending real beat-to-beat intervals or `60000 / HR`.
 *
 * Some monitors set the RR bit and then fill it with the reported heart rate
 * inverted. Everything downstream keeps working, numbers keep appearing, RMSSD
 * becomes meaningless, and no error is ever raised — Rutenberg found exactly this
 * on a Decathlon monitor. It has to be caught here or not at all.
 *
 * Three signatures, any one of which condemns the device:
 *
 *   1. the intervals keep landing on `60000 / bpm` to within a millisecond or
 *      two — a real interval agrees with the averaged rate only by coincidence;
 *   2. the series is essentially flat — under eight distinct values across a
 *      whole block is a broken sensor whatever produced it;
 *   3. the spacing between neighbouring values grows with RR², which is what
 *      `60000 / bpm` does and what a time-quantised clock cannot do.
 *
 * WHY SIGNATURE 3 REPLACED A DISTINCT-VALUE COUNT. The rule used to be "fewer
 * than 8% of samples are distinct", which silently assumed the ~1 ms resolution
 * the BLE field implies. A real HW9 recording — 502 beats, RMSSD 32 ms, plainly
 * genuine — was condemned by it, because the device quantises at 7.6 ms and so
 * has only about forty values available to it in the first place. Counting
 * distinct values measures the device's CLOCK, and the clock was never the
 * question. Signature 3 measures the SHAPE of the spacing, which is the
 * question, and is indifferent to how coarse the clock is.
 *
 * Signature 1 alone is not enough either: a device that fabricates RR from bpm
 * but reports a smoothed bpm in the packet slips past it. Signature 3 catches
 * that case, because the fabricated values still land on the uneven bpm grid.
 *
 * @param {{matches: number, samples: number, values: number[]|Set<number>}} evidence
 * @returns {'menilai'|'sintetis'|'asli'}
 */
export function classifyRrSource({ matches, samples, values }) {
  if (samples < SYNTHETIC_MIN_SAMPLES) return 'menilai'
  if (matches / samples > 0.9) return 'sintetis'
  if (new Set(values).size < 8) return 'sintetis'
  const correlation = bpmGridCorrelation(values)
  if (correlation === null) return 'menilai'
  return correlation > BPM_GRID_CORRELATION_LIMIT ? 'sintetis' : 'asli'
}

/** True when this interval is indistinguishable from `60000 / bpm`. */
export function looksDerivedFromBpm(rrMs, bpm) {
  if (!bpm || bpm <= 0) return false
  return Math.abs(rrMs - 60000 / bpm) < 2
}

// === The locked go/no-go criteria ===========================================

/**
 * Plausible resting RMSSD for a healthy adult, in milliseconds.
 *
 * A sanity check on the magnitude, not a physiological claim: a resting figure
 * outside this band on a seated, silent subject points at the sensor, because
 * both failure modes land outside it — missed beats inflate it, an averaged or
 * synthetic series collapses it.
 */
export const RESTING_RMSSD_MIN_MS = 20
export const RESTING_RMSSD_MAX_MS = 60

/**
 * Apply the decision table locked before the test was run.
 *
 * Locking it first is the point: the criteria were fixed in the acquisition
 * document while the outcome was still unknown, so the verdict cannot be talked
 * into whichever answer is convenient once real numbers are on screen.
 *
 *   RR field absent or synthetic        -> return the device
 *   stressed outliers <= 10%, most windows eligible,
 *     and resting RMSSD in 20-60 ms     -> pass
 *   stressed outliers 10-20%            -> refit and repeat once
 *   stressed outliers > 20%, or no
 *     eligible window at all            -> fall back to the chest strap
 *
 * @param {object|null} rest    `phaseStats` for the resting block
 * @param {object|null} stress  `phaseStats` for the stressed block
 * @returns {{level: string, headline: string, detail: string}}
 */
export function judgeDeviceTest(rest, stress) {
  if (!stress || stress.segTotal === 0) {
    return {
      level: 'kurang-data',
      headline: 'Blok tertekan terlalu pendek untuk dinilai',
      detail: 'Butuh minimal 60 detik data berkelanjutan di dalam blok itu.',
    }
  }

  const out = stress.outlierPct.toFixed(1)
  const yieldText = `${stress.segEligible}/${stress.segTotal}`

  if (stress.segEligible === 0 || stress.outlierPct > 20) {
    return {
      level: 'gagal',
      headline: `✗ GAGAL — outlier ${out}%, segmen layak ${yieldText}`,
      detail:
        'Sensor runtuh pada kondisi bicara-tertekan. Ini mereplikasi temuan L11 ' +
        'pada perangkat modern — sah untuk dilaporkan, tetapi sensor ini tidak ' +
        'dapat dipakai untuk RMSSD. Beralih ke chest strap H808S.',
    }
  }

  if (stress.outlierPct > 10 || stress.segEligible < stress.segTotal * 0.6) {
    return {
      level: 'batas',
      headline: `⚠ BATAS — outlier ${out}%, segmen layak ${yieldText}`,
      detail:
        'Betulkan posisi dan kekencangan band, lalu ulangi sekali. Bila tetap di ' +
        'sini, perlakukan sebagai gagal.',
    }
  }

  // The third pass condition. A device can hold a low outlier rate and still be
  // wrong: a systematically biased interval series is smooth, so it sails through
  // a gate that only looks for jumps. The magnitude check is what catches that.
  const restingRmssd = rest ? (rest.rmssdMedian ?? rest.rmssd) : null
  if (restingRmssd === null) {
    return {
      level: 'batas',
      headline: `⚠ BELUM LENGKAP — outlier ${out}%, segmen layak ${yieldText}`,
      detail:
        'Blok tertekan lolos, tetapi blok istirahat belum menghasilkan RMSSD ' +
        'yang bisa diperiksa kewajarannya. Jalankan blok 1 sampai penuh.',
    }
  }
  if (restingRmssd < RESTING_RMSSD_MIN_MS || restingRmssd > RESTING_RMSSD_MAX_MS) {
    return {
      level: 'batas',
      headline: `⚠ ANGKA MERAGUKAN — RMSSD istirahat ${restingRmssd.toFixed(1)} ms`,
      detail:
        `Outlier blok tertekan bagus (${out}%), tetapi RMSSD istirahat di luar ` +
        `rentang wajar ${RESTING_RMSSD_MIN_MS}-${RESTING_RMSSD_MAX_MS} ms. Gerbang ` +
        'outlier hanya menangkap lonjakan; bias sistematis lolos begitu saja. ' +
        'Perlu pembanding chest strap sebelum perangkat ini dipercaya.',
    }
  }

  const hrRose = rest && rest.meanHr && stress.meanHr
    ? ((stress.meanHr - rest.meanHr) / rest.meanHr) * 100 > 3
    : false

  return {
    level: 'lulus',
    headline: `✓ LULUS — outlier ${out}%, segmen layak ${yieldText}, RMSSD istirahat ${restingRmssd.toFixed(1)} ms`,
    detail: hrRose
      ? 'Sensor bertahan dan HR naik seperti diharapkan. Catatan: outlier rendah ' +
        'belum membuktikan RMSSD akurat — untuk itu perlu pembanding chest strap ' +
        'di perangkat B.'
      : 'Sensor bertahan, TAPI HR tidak naik berarti — kemungkinan besar peserta ' +
        'belum benar-benar tertekan, bukan sensornya yang salah. Ulangi dengan ' +
        'stresor lebih menuntut sebelum menyimpulkan apa pun.',
  }
}
