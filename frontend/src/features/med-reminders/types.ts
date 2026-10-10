/**
 * Front-end shapes for medication reminders. The draft maps onto
 * `POST /api/patients/{id}/reminders` (see docs/API.md); saved reminders use the API's
 * `Reminder` type from `@/lib/api`.
 */

/** ISO calendar date, e.g. "2026-10-17". */
export type IsoDate = string

/** 24-hour local time, e.g. "08:00". */
export type TimeOfDay = string

export type DurationKind = 'appointment' | 'days' | 'date'

export interface ReminderDraft {
  name: string
  timesOfDay: TimeOfDay[]
  durationKind: DurationKind
  durationDays: number
  /** Only used when durationKind === 'date' */
  untilDate: IsoDate | ''
  /** Kept client-side; never sent to the API. */
  consent: boolean
  /** Patient-facing reminder text. null = the standard message. */
  customMessage: string | null
  alertOnMissed: boolean
}

/** What the reminder form needs to know about the patient. */
export interface ReminderPatient {
  id: number
  firstName: string
  /** Clinic-local date of the next booked appointment, or null when none is booked. */
  nextAppointment: { date: IsoDate; clinician: string } | null
}
