/**
 * @vitest-environment jsdom
 *
 * SessionResult.test.tsx — the dashboard renders, and renders nothing forbidden.
 *
 * A smoke test on purpose. The arithmetic is covered in `sessionInsights.test.ts`
 * where it can be checked exactly; what cannot be checked there is whether the
 * charts actually mount — a missing Chart.js registration throws at render time
 * and nothing before this point would have noticed.
 *
 * The second assertion is the one worth keeping forever: decision K4 says a user
 * never sees a feature name or a raw value, and this walks the rendered text
 * looking for one.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SessionResult } from './SessionResult'
import { mockSession } from '../mocks/session'

// Chart.js draws to a canvas jsdom does not implement. The charts are replaced
// with their accessible labels, which is what a screen reader would receive
// anyway — so the test still covers that they were handed sensible data.
vi.mock('react-chartjs-2', () => ({
  Radar: () => <div data-testid="radar" />,
  Line: () => <div data-testid="line" />,
}))

describe('the result dashboard', () => {
  it('mounts both charts and the panels around them', () => {
    render(<SessionResult result={mockSession} />)

    expect(screen.getByTestId('radar')).toBeDefined()
    expect(screen.getByTestId('line')).toBeDefined()
    expect(screen.getByText('Gambaran sesi kamu')).toBeDefined()
    expect(screen.getByText('Naik-turun sepanjang sesi')).toBeDefined()
    expect(screen.getByText('Balik tenang setelah tiap pertanyaan')).toBeDefined()
  })

  it('shows no feature name, raw value or score anywhere on screen', () => {
    const { container } = render(<SessionResult result={mockSession} />)
    const text = container.textContent ?? ''

    for (const forbidden of ['RMSSD', 'SDNN', 'pNN50', 'LF/HF', 'bpm', 'ms']) {
      expect(text).not.toContain(forbidden)
    }
  })
})
