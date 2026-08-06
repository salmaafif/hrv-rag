/**
 * ErrorScreen.tsx — what is shown when a screen crashes.
 *
 * Exists because the alternative is a blank white page. A crash during a
 * defence demonstration is bad; a crash that looks identical to a page that
 * simply has not loaded is worse, because there is no way to tell whether to
 * wait, reload, or start over.
 *
 * The technical detail is deliberately included rather than hidden behind a
 * polite apology: the person most likely to read this screen is the developer,
 * and a message they can paste is worth more than a reassuring sentence.
 */

import { useRouteError } from 'react-router'

function describe(error: unknown): string {
  if (error instanceof Error) return `${error.name}: ${error.message}`
  if (typeof error === 'string') return error
  return 'Kesalahan tidak dikenali.'
}

export function ErrorScreen() {
  const error = useRouteError()

  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-2xl border border-hairline bg-surface p-8">
        <h1 className="text-xl font-semibold text-navy">
          Halaman ini gagal ditampilkan
        </h1>
        <p className="mt-2 text-sm text-ink-muted">
          Ini kesalahan di aplikasinya, bukan pada rekaman atau perangkatmu.
          Muat ulang halaman; kalau masih muncul, salin pesan di bawah.
        </p>

        <pre className="mt-5 overflow-x-auto rounded-lg bg-canvas p-4 text-xs text-ink">
          {describe(error)}
        </pre>

        <div className="mt-6 flex gap-3">
          <button
            onClick={() => window.location.reload()}
            className="rounded-xl bg-navy px-5 py-3 text-sm font-semibold text-white"
          >
            Muat ulang
          </button>
          <a
            href="/v1/mulai"
            className="rounded-xl border border-hairline px-5 py-3 text-sm font-semibold text-navy"
          >
            Kembali ke awal
          </a>
        </div>
      </div>
    </div>
  )
}
