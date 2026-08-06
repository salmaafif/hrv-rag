/**
 * SessionPage.tsx — stage 2 of V3: the interview itself, running here.
 *
 * Only V3 reaches this screen. In V2 the person supplies the question timeline
 * afterwards; in V1 there is no timeline at all. Because it is V3-only, it
 * needs no mode prop — there is nothing for it to branch on.
 *
 * Note what the right-hand column will and will not show. Heart rate in beats
 * per minute stays, because it is the only evidence that the sensor is still
 * reading. The "mulai tegang" badge from the Figma frame does not: telling
 * someone mid-answer that they are getting tense changes how tense they are,
 * which would leave the measurement partly caused by the screen displaying it.
 */

import { Card } from '../components/Card'

export function SessionPage() {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
      <Card>
        <p className="rounded-lg border border-dashed border-hairline p-10 text-center text-sm text-ink-muted">
          Pertanyaan wawancara, penghitung waktu, dan tombol lanjut ditambahkan
          di tahap berikutnya.
        </p>
      </Card>

      <div className="space-y-6">
        <Card title="Self view">
          <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
            Pratinjau kamera menyusul.
          </p>
        </Card>
        <Card title="Detak jantung">
          <p className="rounded-lg border border-dashed border-hairline p-6 text-center text-sm text-ink-muted">
            Angka bpm langsung, tanpa penilaian tekanan. Menyusul bersama
            sambungan Bluetooth.
          </p>
        </Card>
      </div>
    </div>
  )
}
