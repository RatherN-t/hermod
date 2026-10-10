import { endDate, formatTime } from '@/lib/schedule'
import type { IsoDate, ReminderDraft } from './types'

export type FieldKey = 'name' | 'times' | 'duration' | 'message' | 'phone' | 'consent'
export type FieldErrors = Partial<Record<FieldKey, string>>

export const MAX_DAYS = 90
export const MESSAGE_MAX = 500

export function validateDraft(draft: ReminderDraft, ctx: { today: IsoDate; nextAppointment: IsoDate }): FieldErrors {
  const errors: FieldErrors = {}

  if (!draft.name.trim()) errors.name = 'Choose a medication or type its name.'

  if (draft.timesOfDay.length === 0) {
    errors.times = 'Choose how many times a day.'
  } else {
    const missing = draft.timesOfDay.findIndex((t) => !/^\d{2}:\d{2}$/.test(t))
    if (missing !== -1) {
      errors.times = `Enter a time for dose ${missing + 1}.`
    } else {
      const dup = draft.timesOfDay.find((t, i) => draft.timesOfDay.indexOf(t) !== i)
      if (dup) errors.times = `Two doses are set for ${formatTime(dup)}. Change one of them.`
    }
  }

  if (draft.durationKind === 'days') {
    if (!Number.isInteger(draft.durationDays) || draft.durationDays < 1 || draft.durationDays > MAX_DAYS) {
      errors.duration = `Enter a number of days from 1 to ${MAX_DAYS}.`
    }
  } else if (draft.durationKind === 'date') {
    if (!draft.untilDate) errors.duration = 'Pick the last day of reminders.'
    else if (!endDate({ kind: 'date', days: 0, untilDate: draft.untilDate, nextAppointment: ctx.nextAppointment }, ctx.today))
      errors.duration = 'Pick a date after today.'
  }

  if (draft.phoneEdited && draft.waPhone.replace(/\D/g, '').length < 10) {
    errors.phone = 'Enter a full phone number, including area code.'
  }

  if (draft.customMessage !== null) {
    const length = draft.customMessage.trim().length
    if (length === 0) errors.message = 'Write a message, or turn this off to send the standard one.'
    else if (length > MESSAGE_MAX) errors.message = `Keep the message under ${MESSAGE_MAX} characters.`
  }

  if (!draft.consent) errors.consent = 'Confirm the patient agreed before you start reminders.'

  return errors
}
