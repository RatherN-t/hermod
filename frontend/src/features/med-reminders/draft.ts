import { defaultTimes } from '@/lib/schedule'
import type { ActiveReminder, DemoPatient, ReminderDraft } from './types'

export function emptyDraft(patient: DemoPatient): ReminderDraft {
  return {
    name: '',
    timesOfDay: defaultTimes(2),
    durationKind: 'appointment',
    durationDays: 7,
    untilDate: '',
    waPhone: patient.waPhone,
    phoneEdited: false,
    consent: false,
    language: 'en',
    customMessage: null,
    alertOnMissed: true,
  }
}

export function draftFromReminder(r: ActiveReminder, patient: DemoPatient): ReminderDraft {
  return {
    name: r.name,
    timesOfDay: [...r.timesOfDay],
    durationKind: r.durationKind,
    durationDays: r.durationDays,
    untilDate: r.untilDate,
    waPhone: r.waPhone,
    phoneEdited: r.waPhone !== patient.waPhone,
    // Consent was recorded when the reminder was first started.
    consent: true,
    language: r.language,
    customMessage: r.customMessage,
    alertOnMissed: r.alertOnMissed,
  }
}
