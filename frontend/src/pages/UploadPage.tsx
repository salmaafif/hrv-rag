/**
 * UploadPage.tsx — V3, after the interview: hand over the recording.
 *
 * This stage exists because of when the heart data comes into being. The
 * recording is made DURING the interview, so in V3 there is nothing to upload
 * until the interview is over. Putting the upload on the start screen — where
 * it began life — asked for a file that could not yet exist.
 *
 * The stage is skipped entirely when a sensor was connected: the app already
 * has the data, and asking for it again would be asking twice for the same
 * thing.
 */

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { RecordingUpload } from '../components/RecordingUpload'
import { NavigateKeepingSearch } from '../app/NavigateKeepingSearch'
import { useNavigateKeepingSearch } from '../app/useNavigateKeepingSearch'
import type { StageContext } from '../app/stageContext'

export function UploadPage({ mode, session }: StageContext) {
  const navigate = useNavigateKeepingSearch()

  // Nothing was recorded here, so there is nothing to attach a recording to.
  if (session.questionTimeline === null) {
    return <NavigateKeepingSearch to={`/${mode.id}/mulai`} />
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <div className="space-y-6">
        <Card title="Unggah rekaman detak jantungmu">
          <p className="text-sm text-ink-muted">
            Sesi latihan selesai. Aplikasi sudah mencatat kapan tiap pertanyaan
            ditanyakan — sekarang tinggal rekaman detak jantung dari alatmu,
            supaya keduanya bisa disandingkan.
          </p>

          <p className="mt-4 rounded-xl bg-amber-soft p-4 text-sm text-level-moderate">
            Rekaman harus dimulai <strong>sebelum</strong> sesi latihan tadi,
            mencakup {session.baselineMinutes} menit periode tenang di awal.
            Tanpa bagian tenang itu, tidak ada pembanding untuk menilai sisanya.
          </p>

          <div className="mt-5">
            <RecordingUpload session={session} />
          </div>
        </Card>

        <Button
          variant="accent"
          full
          disabled={!session.isReady}
          onClick={() => navigate(`/${mode.id}/proses`)}
        >
          Analisis rekaman
        </Button>

        {!session.isReady && (
          <p className="text-center text-sm text-ink-muted">
            Pilih berkas rekamannya dulu, lalu beri tahu di mana alatnya
            dipakai.
          </p>
        )}
      </div>

      <Card title="Yang sudah tercatat">
        <ol className="space-y-2">
          {session.questionTimeline.map((entry) => (
            <li
              key={entry.number}
              className="rounded-lg bg-canvas px-3 py-2 text-sm"
            >
              <span className="font-semibold text-navy">{entry.number}.</span>{' '}
              <span className="text-ink-muted">{entry.text}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
