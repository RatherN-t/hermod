import type { Reminder, ReminderCreate, ReminderUpdate } from '@/lib/api'
import { clinicDate } from '@/lib/clinic-time'
import { addDays, defaultTimes } from '@/lib/schedule'
import type { IsoDate, ReminderDraft, ReminderPatient } from './types'

export function emptyDraft(patient: ReminderPatient, today: IsoDate): ReminderDraft {
  return {
    name: '',
    // New reminders start tomorrow unless the clinic picks another day.
    startDate: addDays(today, 1),
    timesOfDay: defaultTimes(2),
    durationKind: patient.nextAppointment ? 'appointment' : 'days',
    durationDays: 7,
    untilDate: '',
    consent: false,
    customMessage: null,
    alertOnMissed: true,
  }
}

export function draftFromReminder(r: Reminder): ReminderDraft {
  return {
    name: r.name,
    startDate: clinicDate(r.startDate),
    timesOfDay: [...r.timesOfDay],
    durationKind: r.durationKind,
    durationDays: r.durationDays ?? 7,
    untilDate: r.durationKind === 'date' ? clinicDate(r.endDate) : '',
    // Consent was recorded when the reminder was first started.
    consent: true,
    customMessage: r.customMessage,
    alertOnMissed: r.alertOnMissed,
  }
}

const durationFields = (d: ReminderDraft) => ({
  durationKind: d.durationKind,
  ...(d.durationKind === 'days' ? { durationDays: d.durationDays } : {}),
  ...(d.durationKind === 'date' ? { untilDate: d.untilDate } : {}),
})

export function createBody(d: ReminderDraft): ReminderCreate {
  return {
    name: d.name.trim(),
    timesOfDay: [...d.timesOfDay].sort(),
    ...durationFields(d),
    startDate: d.startDate,
    customMessage: d.customMessage === null ? null : d.customMessage.trim(),
    alertOnMissed: d.alertOnMissed,
  }
}

/** Only the fields that changed, for `PATCH /api/reminders/{id}`. */
export function updateBody(before: ReminderDraft, d: ReminderDraft): ReminderUpdate {
  const body: ReminderUpdate = {}
  const times = [...d.timesOfDay].sort()
  if (times.join() !== [...before.timesOfDay].sort().join()) body.timesOfDay = times

  const durationChanged =
    d.durationKind !== before.durationKind ||
    (d.durationKind === 'days' && d.durationDays !== before.durationDays) ||
    (d.durationKind === 'date' && d.untilDate !== before.untilDate)
  if (durationChanged) Object.assign(body, durationFields(d))

  const message = d.customMessage === null ? null : d.customMessage.trim()
  if (message !== before.customMessage) body.customMessage = message ?? ''
  if (d.alertOnMissed !== before.alertOnMissed) body.alertOnMissed = d.alertOnMissed
  return body
}
