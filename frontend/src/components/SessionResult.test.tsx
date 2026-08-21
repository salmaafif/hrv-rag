/**
 * @vitest-environment jsdom
 *
 * SessionResult.test.tsx — the dashboard renders, and renders nothing forbidden.
 *
 * A smoke test on purpose. The arithmetic is covered in `sessionInsights.test.ts`
 * where it can be checked exactly; what cannot be checked there is whether the
 * chart actually mounts — a missing Chart.js registration throws at render time
 * and nothing before this point would have noticed.
 *
 * The K4 assertion is the one worth keeping forever: decision K4 says a user
 * never sees a feature name or a raw value, and this walks the rendered text
 * looking for one.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SessionResult } from './SessionResult'
import { mockSession } from '../mocks/session'

// Chart.js draws to a canvas jsdom does not implement. The timeline is replaced
// with a stand-in; the quadrant needs no mock, because it is plain markup rather
// than a chart — which is part of why it replaced the radar.
vi.mock('react-chartjs-2', () => ({
  Line: () => <div data-testid="line" />,
}))

// This project runs vitest without `globals: true`, so React Testing
// Library's automatic per-test cleanup never registers itself. Without this,
// each `it` below leaves its render mounted, and a later `getByText` matches
// one heading per accumulated render instead of one.
afterEach(cleanup)

describe('the result dashboard', () => {
  it('mounts the timeline and the panels around it', () => {
    render(<SessionResult result={mockSession} />)

    expect(screen.getByTestId('line')).toBeDefined()
    expect(screen.getByText('Naik-turun sepanjang sesi')).toBeDefined()
    expect(screen.getByText('Rincian per pertanyaan')).toBeDefined()
  })

  it('names Ketahanan on screen, and draws all four cells', () => {
    /**
     * The word used to appear nowhere at all. Ketahanan is one of the three
     * outputs the design document promises, and the screen showed its quadrant
     * under the heading "Besar reaksi dan kecepatan pulih" — the definition
     * instead of the name, so somebody reading the document could not find it
     * here.
     *
     * All four cells are drawn whatever the verdict, because a lone highlighted
     * box means nothing without the three it was chosen over.
     */
    render(<SessionResult result={mockSession} />)

    expect(screen.getByText('Ketahanan')).toBeDefined()
    for (const cell of [
      'Reaksi kecil, pulih cepat',
      'Reaksi besar, pulih cepat',
      'Reaksi kecil, pulih lambat',
      'Reaksi besar, pulih lambat',
    ]) {
      expect(screen.getByText(cell)).toBeDefined()
    }
  })

  it('reads the encouragement card before the session summary', () => {
    // Decision A13 (position half). Reappraisal is the one part of this
    // screen with experimental evidence it changes what happens next, so it
    // has to win the race for attention against everything else here.
    const { container } = render(<SessionResult result={mockSession} />)
    const text = container.textContent ?? ''

    const encouragementAt = text.indexOf(mockSession.narrative.penyemangat)
    const summaryAt = text.indexOf(mockSession.narrative.ringkasan_sesi)

    expect(encouragementAt).toBeGreaterThanOrEqual(0)
    expect(summaryAt).toBeGreaterThan(encouragementAt)
  })

  it('states the hardest question once, not twice', () => {
    /**
     * It was a headline figure at the top AND a row in a card below the
     * per-question list — one fact, twice, several screens apart.
     */
    const { container } = render(<SessionResult result={mockSession} />)
    const parts = (container.textContent ?? '').split('Paling bikin tegang')
    expect(parts).toHaveLength(2) // one split point = one occurrence
  })

  it('tells the reader a mismatch with how they felt is expected', () => {
    // Decision A14. Without this line, a body reading that disagrees with how
    // someone remembers feeling reads as the tool being wrong about them.
    render(<SessionResult result={mockSession} />)

    expect(
      screen.getByText(/tidak cocok dengan yang kamu rasakan/),
    ).toBeDefined()
  })

  it('states its scope, so tension is not read as a forecast of the interview', () => {
    // Decision A16. HRV covers one of five MASI dimensions of interview
    // anxiety, not "interview anxiety" as a whole.
    render(<SessionResult result={mockSession} />)

    expect(screen.getByText(/Tegang di sini tidak berarti/)).toBeDefined()
  })

  it('shows no feature name, raw value or score anywhere on screen', () => {
    const { container } = render(<SessionResult result={mockSession} />)
    const text = container.textContent ?? ''

    for (const forbidden of ['RMSSD', 'SDNN', 'pNN50', 'LF/HF', 'bpm', 'ms']) {
      expect(text).not.toContain(forbidden)
    }
  })
})
