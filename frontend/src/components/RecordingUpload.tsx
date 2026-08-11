/**
 * RecordingUpload.tsx — pick a recording file and say where it was worn.
 *
 * Shared because the same two questions get asked at two different moments:
 * on the start screen for V1 and V2, whose recording already existed before
 * anyone opened the app, and after the interview for V3, whose recording could
 * not exist any earlier than that.
 *
 * The wear location is asked every time a new file is chosen, never carried
 * over. A different recording may well have come from a different device, and
 * the modality decides how much confidence the whole reading is given.
 */

import { Button } from './Button'
import { wearLabel, type WearLocation } from '../types/device'
import type { SessionState } from '../app/useSessionState'

const WEAR_CHOICES: WearLocation[] = ['chest', 'wrist']

interface RecordingUploadProps {
  session: SessionState
  /** Text on the file picker before anything is chosen. */
  label?: string
}

export function RecordingUpload({
  session,
  label = 'Unggah berkas rekaman (CSV)',
}: RecordingUploadProps) {
  return (
    <div>
      <label className="block cursor-pointer rounded-xl border border-hairline bg-surface px-5 py-3 text-center text-sm font-semibold text-navy hover:bg-canvas">
        {session.fileName ?? label}
        <input
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(event) => session.setFile(event.target.files?.[0] ?? null)}
        />
      </label>

      {session.fileName !== null && session.fileWornAt === null && (
        <div className="mt-4 rounded-xl bg-level-moderate-bg p-4">
          <p className="mb-3 text-sm font-semibold text-level-moderate">
            Rekaman ini diambil dengan alat yang dipakai di mana?
          </p>
          <div className="space-y-2">
            {WEAR_CHOICES.map((location) => (
              <Button
                key={location}
                variant="outline"
                full
                onClick={() => session.setFileWornAt(location)}
              >
                {wearLabel(location)}
              </Button>
            ))}
          </div>
        </div>
      )}

      {session.fileName !== null && session.fileWornAt !== null && (
        <p className="mt-3 rounded-lg bg-canvas px-4 py-3 text-sm text-ink-muted">
          {wearLabel(session.fileWornAt)}
        </p>
      )}
    </div>
  )
}
