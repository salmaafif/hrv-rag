/**
 * Button.tsx — the three button shapes used in the Figma frames.
 *
 * `primary` is the dark navy call to action, `accent` the blue one that starts
 * something, `outline` the quieter alternative offered beside them. Keeping the
 * set this small is the point: a screen that needs a fourth kind of button
 * usually needs fewer choices instead.
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'accent' | 'outline'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  full?: boolean
  children: ReactNode
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: 'bg-navy text-white hover:bg-navy/90',
  accent: 'bg-brand text-white hover:bg-brand/90',
  outline: 'border border-hairline bg-surface text-navy hover:bg-canvas',
}

export function Button({
  variant = 'primary',
  full = false,
  className = '',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={
        'rounded-xl px-5 py-3 text-sm font-semibold transition-colors ' +
        'disabled:cursor-not-allowed disabled:opacity-50 ' +
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ' +
        VARIANT_CLASS[variant] +
        (full ? ' w-full' : '') +
        (className ? ' ' + className : '')
      }
      {...rest}
    >
      {children}
    </button>
  )
}
