/**
 * heartStream.ts — turns the beat stream into a drawable line, and nothing more.
 *
 * WHAT THIS DELIBERATELY IS NOT: an interpretation. The session screen once had
 * a "mulai tegang" badge and it was removed on purpose — telling somebody
 * mid-answer that they are getting tense changes how tense they are, and the
 * measurement then partly describes the screen instead of the interview. A live
 * trace is allowed back in only under that same rule: it shows the HEART RATE,
 * in one neutral colour, with no thresholds, no zones, no colour changes, and
 * no words about stress. Its job is reassurance that the sensor is alive and a
 * sense that something real is being recorded — not feedback on how the
 * recording is going.
 *
 * Pure functions, so the arithmetic is testable without a browser.
 */

/** How many of the most recent beats the trace shows. */
export const STREAM_WINDOW_BEATS = 60

/** Physiological display bounds; beats outside are artefacts, clamped. */
const MIN_BPM = 40
const MAX_BPM = 160

export interface StreamPoint {
  x: number
  y: number
}

/**
 * The last beats as polyline points in a 0..width / 0..height box.
 *
 * The y scale is FIXED to the physiological range rather than auto-fitted to
 * the visible window. Auto-fit would amplify tiny fluctuations into dramatic
 * swings whenever the window is calm — the calmer the person, the more anxious
 * the line would look, which is exactly the feedback loop this component is
 * forbidden from creating.
 */
export function streamPoints(
  rrIntervals: number[],
  width: number,
  height: number,
): StreamPoint[] {
  const recent = rrIntervals.slice(-STREAM_WINDOW_BEATS)
  if (recent.length < 2) return []

  return recent.map((rr, index) => {
    const bpm = Math.max(MIN_BPM, Math.min(MAX_BPM, 60000 / rr))
    return {
      x: (index / (STREAM_WINDOW_BEATS - 1)) * width,
      y: height - ((bpm - MIN_BPM) / (MAX_BPM - MIN_BPM)) * height,
    }
  })
}

/** The points as an SVG polyline `points` attribute. */
export function streamPath(rrIntervals: number[], width: number,
                           height: number): string {
  return streamPoints(rrIntervals, width, height)
    .map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(' ')
}
