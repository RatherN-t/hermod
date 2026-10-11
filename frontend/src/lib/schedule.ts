import type { DurationKind, IsoDate, TimeOfDay } from '@/features/med-reminders/types'

const DAY_MS = 86_400_000

/** Evenly spaced default dose times for a given number of doses a day. */
export function defaultTimes(n: number): TimeOfDay[] {
  switch (n) {
    case 1:
      return ['08:00']
    case 2:
      return ['08:00', '20:00']
    case 3:
      return ['08:00', '14:00', '20:00']
    case 4:
      return ['08:00', '12:00', '16:00', '20:00']
    default:
      return []
  }
}

function toUtc(date: IsoDate): number {
  const [y, m, d] = date.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

function fromUtc(ms: number): IsoDate {
  return new Date(ms).toISOString().slice(0, 10)
}

export function isValidIsoDate(value: string): value is IsoDate {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const ms = toUtc(value)
  return !Number.isNaN(ms) && fromUtc(ms) === value
}

export function addDays(date: IsoDate, days: number): IsoDate {
  return fromUtc(toUtc(date) + days * DAY_MS)
}

/** Whole days from `a` to `b` (positive when b is later). */
export function daysBetween(a: IsoDate, b: IsoDate): number {
  return Math.round((toUtc(b) - toUtc(a)) / DAY_MS)
}

export interface DurationInput {
  kind: DurationKind
  days: number
  untilDate: IsoDate | ''
  nextAppointment: IsoDate
}

/**
 * Reminders start the day after setup and run through the end date (inclusive).
 * Returns null when the chosen duration has no valid end date yet.
 */
export function endDate(duration: DurationInput, today: IsoDate): IsoDate | null {
  switch (duration.kind) {
    case 'appointment':
      return duration.nextAppointment
    case 'days':
      return Number.isInteger(duration.days) && duration.days >= 1 ? addDays(today, duration.days) : null
    case 'date':
      return duration.untilDate && isValidIsoDate(duration.untilDate) && daysBetween(today, duration.untilDate) >= 1
        ? duration.untilDate
        : null
  }
}

/** Number of reminder days between setup (`today`) and `end`, inclusive of `end`. */
export function reminderDays(today: IsoDate, end: IsoDate): number {
  return Math.max(0, daysBetween(today, end))
}

export function totalDoses(times: TimeOfDay[], today: IsoDate, end: IsoDate): number {
  return times.length * reminderDays(today, end)
}

/** "08:00" -> "8:00", "14:30" -> "14:30" */
export function formatTime(time: TimeOfDay): string {
  const [h, m] = time.split(':')
  if (h === undefined || m === undefined) return time
  return `${Number(h)}:${m}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** "Oct 17", or "Jan 8, 2027" when the year differs from `today`. */
export function formatDate(date: IsoDate, today: IsoDate, opts: { weekday?: boolean; forceYear?: boolean } = {}): string {
  const d = new Date(toUtc(date))
  const sameYear = date.slice(0, 4) === today.slice(0, 4)
  const base = `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`
  const withYear = sameYear && !opts.forceYear ? base : `${base}, ${d.getUTCFullYear()}`
  return opts.weekday ? `${WEEKDAYS[d.getUTCDay()]}, ${withYear}` : withYear
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/** "Eleanor will get 3 reminders a day for 7 days (21 total), ending Oct 17." */
export function summarySentence(args: {
  firstName: string
  times: TimeOfDay[]
  today: IsoDate
  end: IsoDate | null
}): string {
  const { firstName, times, today, end } = args
  if (times.length === 0) return `Choose how many times a day ${firstName} should be reminded.`
  if (!end) return `Choose an end date to see ${firstName}’s full schedule.`
  const days = reminderDays(today, end)
  const total = times.length * days
  return `${firstName} will get ${plural(times.length, 'reminder', 'reminders')} a day for ${plural(days, 'day', 'days')} (${total} total), ending ${formatDate(end, today)}.`
}

/** Default Telegram reminder text. The "Taken" and "Remind me in 30 min" buttons are added by the sender. */
export function standardMessage(firstName: string, medication: string): string {
  const med = medication.trim() || 'your medication'
  return `Hi ${firstName}, it’s time to take ${med}. Tap “Taken” once you’ve had it. – Hermod`
}

export function scheduleLabel(times: TimeOfDay[]): string {
  return `${times.length}× daily · ${times.map(formatTime).join(', ')}`
}

