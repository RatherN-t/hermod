/**
 * Dose adherence for the patient list and patient card. Rows mirror `DoseEvent` in
 * hermod/db/models.py, so the dummy rows below can be swapped for the real table query later.
 */
import type { ActiveReminder } from '@/features/med-reminders/types'

export type DoseStatus = 'pending' | 'taken' | 'late' | 'missed' | 'extra' | 'unknown'

export interface DoseEventRow {
  medication_name: string
  status: DoseStatus
}

export interface AdherenceSummary {
  /** Doses marked taken (late still counts as taken). */
  taken: number
  /** Doses whose time has passed, so the patient could have taken them. */
  due: number
  /** Every dose in the prescription, including future ones. */
  prescribed: number
}

export function summarizeDoses(rows: DoseEventRow[]): AdherenceSummary {
  const past = rows.filter((r) => r.status !== 'pending')
  return {
    taken: past.filter((r) => r.status === 'taken' || r.status === 'late').length,
    due: past.filter((r) => r.status !== 'extra').length,
    prescribed: rows.filter((r) => r.status !== 'extra').length,
  }
}

/** Fictional dose history built from the seeded reminders, so every view shows the same numbers. */
function demoDoseEvents(reminders: ActiveReminder[]): DoseEventRow[] {
  return reminders.flatMap((r) =>
    Array.from({ length: r.totalDoses }, (_, i): DoseEventRow => ({
      medication_name: r.name,
      status: i >= r.dosesSent ? 'pending' : i < r.dosesConfirmed ? 'taken' : 'missed',
    })),
  )
}

// TODO: replace with a query for this patient's dose_event rows.
export function getAdherence(patient: { reminders: ActiveReminder[] }): AdherenceSummary {
  return summarizeDoses(demoDoseEvents(patient.reminders))
}
