/**
 * @vitest-environment jsdom
 *
 * QuestionSlider.test.tsx — one question shown at a time, navigation moves it.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { QuestionSlider } from './QuestionSlider'
import { mockSession } from '../mocks/session'

// This project runs vitest without `globals: true`, so React Testing
// Library's automatic per-test cleanup never registers itself. Without this,
// each `it` below leaves its render mounted and `getByLabelText` in a later
// test matches one button per accumulated render instead of one.
afterEach(cleanup)

describe('the per-question slider', () => {
  it('shows only the first question on mount', () => {
    render(<QuestionSlider questions={mockSession.questions} />)

    expect(screen.getByText('Ceritakan tentang dirimu')).toBeDefined()
    expect(screen.queryByText('Kenapa kami harus memilihmu?')).toBeNull()
  })

  it('moves to the next question and back', () => {
    render(<QuestionSlider questions={mockSession.questions} />)

    fireEvent.click(screen.getByLabelText('Pertanyaan berikutnya'))
    expect(screen.getByText('Kenapa kami harus memilihmu?')).toBeDefined()

    fireEvent.click(screen.getByLabelText('Pertanyaan sebelumnya'))
    expect(screen.getByText('Ceritakan tentang dirimu')).toBeDefined()
  })

  it('jumps straight to a question via its dot', () => {
    render(<QuestionSlider questions={mockSession.questions} />)

    fireEvent.click(screen.getByLabelText('Ke pertanyaan 5'))
    expect(screen.getByText('Berapa ekspektasi gajimu?')).toBeDefined()
  })

  it('disables prev at the first question and next at the last', () => {
    render(<QuestionSlider questions={mockSession.questions} />)

    expect(screen.getByLabelText('Pertanyaan sebelumnya')).toHaveProperty(
      'disabled',
      true,
    )

    fireEvent.click(screen.getByLabelText('Ke pertanyaan 6'))
    expect(screen.getByLabelText('Pertanyaan berikutnya')).toHaveProperty(
      'disabled',
      true,
    )
  })
})
