/**
 * Card.tsx — the white panel every screen is built from.
 *
 * Exists so the corner radius, border and shadow from the Figma frames are
 * decided once. Nothing here is behaviour; if it ever needs a prop that is not
 * about appearance, that is a sign the thing being built is not a card.
 */

import type { ReactNode } from 'react'

interface CardProps {
  /** Optional heading rendered in the card's own style. */
  title?: string
  /** Small uppercase label above the title, as used in the left rail. */
  eyebrow?: string
  children: ReactNode
  className?: string
}

export function Card({ title, eyebrow, children, className = '' }: CardProps) {
  return (
    <section
      className={
        'rounded-2xl border border-hairline bg-surface p-6 ' +
        'shadow-[0_1px_2px_rgba(22,35,77,0.04)] ' +
        className
      }
    >
      {eyebrow && (
        <p className="mb-3 text-xs font-semibold tracking-wider text-ink-muted uppercase">
          {eyebrow}
        </p>
      )}
      {title && (
        <h2 className="mb-4 text-xl font-semibold tracking-tight text-navy">
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}
