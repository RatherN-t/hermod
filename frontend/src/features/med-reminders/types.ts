/**
 * Front-end shapes for medication reminders. Field names follow the backend
 * (`hermod/db/models.py`): Medication.name, Medication.times_of_day,
 * Prescription.end_date, Patient.wa_phone, DoseEvent.status.
 */

/** ISO calendar date, e.g. "2026-10-17". */
export type IsoDate = string

/** 24-hour local time, e.g. "08:00". */
export type TimeOfDay = string

export type DurationKind = 'appointment' | 'days' | 'date'

export type MessageLanguage = 'en' | 'es'

export interface ReminderDraft {
  /** Medication.name */
  name: string
  /** Medication.times_of_day, split. Joined with "," when sent to the API. */
  timesOfDay: TimeOfDay[]
  durationKind: DurationKind
  durationDays: number
  /** Only used when durationKind === 'date' */
  untilDate: IsoDate | ''
  /** Patient.wa_phone, as displayed */
  waPhone: string
  phoneEdited: boolean
  consent: boolean
  language: MessageLanguage
  /** Patient-facing reminder text. null = the standard message. */
  customMessage: string | null
  alertOnMissed: boolean
}

export type ReminderStatus = 'active' | 'paused'

export interface ActiveReminder {
  id: string
  name: string
  timesOfDay: TimeOfDay[]
  durationKind: DurationKind
  durationDays: number
  untilDate: IsoDate | ''
  startDate: IsoDate
  /** Prescription.end_date */
  endDate: IsoDate
  /** Doses sent so far, and how many of those the patient marked "Taken" (DoseEvent.status) */
  dosesSent: number
  dosesConfirmed: number
  totalDoses: number
  status: ReminderStatus
  language: MessageLanguage
  customMessage: string | null
  alertOnMissed: boolean
  waPhone: string
}

export interface DemoPatient {
  firstName: string
  fullName: string
  waPhone: string
  currentMedications: string[]
  nextAppointment: { date: IsoDate; clinician: string }
}
