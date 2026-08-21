/**
 * @vitest-environment jsdom
 *
 * CandidateCheckIn.test.tsx — the check-in question captures a selection
 * locally, and nothing more.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { CandidateCheckIn } from './CandidateCheckIn'

afterEach(cleanup)

describe('the candidate check-in question', () => {
  it('asks whether the reading matched how the candidate felt', () => {
    render(<CandidateCheckIn />)

    expect(
      screen.getByText('Ini cocok tidak dengan yang kamu rasakan tadi?'),
    ).toBeDefined()
  })

  it('shows no acknowledgement before an answer is picked', () => {
    render(<CandidateCheckIn />)

    expect(screen.queryByText('Makasih sudah kasih tahu.')).toBeNull()
  })

  it('marks the picked option and acknowledges it, without changing the others', () => {
    render(<CandidateCheckIn />)

    fireEvent.click(screen.getByText('Sebagian cocok'))

    expect(
      screen.getByText('Sebagian cocok').getAttribute('aria-pressed'),
    ).toBe('true')
    expect(screen.getByText('Cocok').getAttribute('aria-pressed')).toBe(
      'false',
    )
    expect(screen.getByText('Makasih sudah kasih tahu.')).toBeDefined()
  })
})
