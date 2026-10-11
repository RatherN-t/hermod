import type { IsoDate } from '@/features/med-reminders/types'

/** The clinic's timezone; the backend schedules doses in the same one. */
export const CLINIC_TIME_ZONE = 'Australia/Sydney'

const dateParts = new Intl.DateTimeFormat('en-CA', {
  timeZone: CLINIC_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** Calendar date in the clinic's timezone, e.g. "2027-01-08" for "2027-01-07T22:30:00Z". */
export function clinicDate(value: Date | string): IsoDate {
  const parts = dateParts.formatToParts(typeof value === 'string' ? new Date(value) : value)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')}`
}

/** Today's date in the clinic. */
export function clinicToday(): IsoDate {
  return clinicDate(new Date())
}

const wallClock = new Intl.DateTimeFormat('en-CA', {
  timeZone: CLINIC_TIME_ZONE,
  hourCycle: 'h23',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

/** The clinic's current time of day, e.g. "14:05". */
export function clinicTimeNow(): string {
  const p = Object.fromEntries(wallClock.formatToParts(new Date()).map((x) => [x.type, x.value]))
  return `${p.hour}:${p.minute}`
}

/** Clinic-local date and time ("2026-11-12", "09:30") → UTC ISO string for the API. */
export function clinicDateTimeToUtc(date: IsoDate, time: string): string {
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  const target = Date.UTC(y, m - 1, d, hh, mm)
  // Read what Sydney's clock shows at a guess, and shift by the difference (twice covers DST edges).
  let guess = target
  for (let i = 0; i < 2; i++) {
    const p = Object.fromEntries(wallClock.formatToParts(new Date(guess)).map((x) => [x.type, x.value]))
    const shown = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute)
    guess += target - shown
  }
  return new Date(guess).toISOString().replace('.000Z', 'Z')
}
