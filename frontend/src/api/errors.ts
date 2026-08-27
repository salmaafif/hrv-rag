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

  /**
   * The server's own explanation, verbatim, when it gave one.
   *
   * The backend writes its 422 reasons to be actionable — "only 3 intervals
   * found", "no question had a usable window" — and for a whole afternoon of
   * failed test sessions this string was thrown away in favour of one canned
   * sentence, leaving every failure looking identical. The canned sentence
   * stays as the headline; this travels with it so the screen can show WHY.
   */
  readonly serverDetail: string | null

  constructor(message: string, retryable: boolean,
              serverDetail: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.retryable = retryable
    this.serverDetail = serverDetail
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
