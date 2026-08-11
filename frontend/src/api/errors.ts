/**
 * errors.ts — the one failure type the UI has to understand.
 *
 * In its own module so both the real client and the dummy can throw it without
 * importing each other.
 */

export class ApiError extends Error {
  /**
   * Whether trying again could plausibly work.
   *
   * The two kinds of failure deserve different offers. A timeout or a server
   * waking up warrants a retry button. A recording the backend cannot parse
   * will fail identically however many times it is sent, and offering a retry
   * there just wastes someone's time before they discover they need a different
   * file.
   */
  readonly retryable: boolean

  constructor(message: string, retryable: boolean) {
    super(message)
    this.name = 'ApiError'
    this.retryable = retryable
  }
}

/** Anything can be thrown in JavaScript; this narrows it to something showable. */
export function toApiError(cause: unknown): ApiError {
  if (cause instanceof ApiError) return cause
  return new ApiError(
    'Terjadi kesalahan yang tidak terduga. Coba lagi.',
    true,
  )
}
