import type { ActiveReminder, DemoPatient, DurationKind, IsoDate, TimeOfDay } from '@/features/med-reminders/types'
import { addDays, defaultTimes } from './schedule'

/**
 * Fictional demo data. Nothing here describes a real person, and every phone
 * number is in the 555 range. "Today" is fixed so the copy and totals stay stable.
 */
export const TODAY: IsoDate = '2026-10-10'

export interface DemoPatientRecord extends DemoPatient {
  /** MRN-style id shown in the list and used in the URL. */
  id: string
  initials: string
  dateOfBirth: string
  language: string
  primaryClinician: string
  reminders: ActiveReminder[]
}

interface ReminderSeed {
  name: string
  perDay: number
  /** Doses sent so far, and how many of those were confirmed. */
  sent: number
  confirmed: number
  /** Length of the whole course in days. */
  courseDays: number
  kind?: DurationKind
  customMessage?: string
}

function seedReminder(patientPhone: string, seed: ReminderSeed): ActiveReminder {
  const timesOfDay: TimeOfDay[] = defaultTimes(seed.perDay)
  const startDate = addDays(TODAY, -Math.ceil(seed.sent / seed.perDay))
  return {
    id: `rem-${seed.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
    name: seed.name,
    timesOfDay,
    durationKind: seed.kind ?? 'days',
    durationDays: seed.courseDays,
    untilDate: '',
    startDate,
    endDate: addDays(startDate, seed.courseDays - 1),
    dosesSent: seed.sent,
    dosesConfirmed: seed.confirmed,
    totalDoses: seed.courseDays * seed.perDay,
    status: 'active',
    language: 'en',
    customMessage: seed.customMessage ?? null,
    alertOnMissed: true,
    waPhone: patientPhone,
  }
}

function patient(
  p: Omit<DemoPatientRecord, 'firstName' | 'initials' | 'reminders'>,
  reminders: ReminderSeed[] = [],
): DemoPatientRecord {
  const [first, last] = p.fullName.split(' ')
  return {
    ...p,
    firstName: first,
    initials: `${first[0]}${last[0]}`,
    reminders: reminders.map((r) => seedReminder(p.waPhone, r)),
  }
}

const demoPatients: DemoPatientRecord[] = [
  patient(
    {
      id: 'EW-004821',
      fullName: 'Eleanor Mitchell',
      dateOfBirth: 'Apr 18, 1968',
      waPhone: '(202) 555-0148',
      language: 'English',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Lisinopril 10 mg', 'Metformin 500 mg', 'Atorvastatin 20 mg'],
      nextAppointment: { date: '2027-01-08', clinician: 'Dr. Sarah Lee' },
    },
    [{ name: 'Lisinopril 10 mg', perDay: 1, sent: 21, confirmed: 18, courseDays: 112, kind: 'appointment' }],
  ),
  patient(
    {
      id: 'EW-004822',
      fullName: 'James Okafor',
      dateOfBirth: 'Sep 2, 1959',
      waPhone: '(202) 555-0172',
      language: 'English',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Metformin 500 mg', 'Atorvastatin 20 mg'],
      nextAppointment: { date: '2026-12-14', clinician: 'Dr. Sarah Lee' },
    },
    [
      { name: 'Metformin 500 mg', perDay: 2, sent: 42, confirmed: 40, courseDays: 90 },
      { name: 'Atorvastatin 20 mg', perDay: 1, sent: 21, confirmed: 21, courseDays: 90 },
    ],
  ),
  patient(
    {
      id: 'EW-004823',
      fullName: 'Priya Shah',
      dateOfBirth: 'Jan 27, 1991',
      waPhone: '(202) 555-0119',
      language: 'English',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Amoxicillin 500 mg'],
      nextAppointment: { date: '2026-10-20', clinician: 'Dr. Sarah Lee' },
    },
    [{ name: 'Amoxicillin 500 mg', perDay: 3, sent: 14, confirmed: 9, courseDays: 7 }],
  ),
  patient(
    {
      id: 'EW-004824',
      fullName: 'Tomás Rivera',
      dateOfBirth: 'Jun 11, 1974',
      waPhone: '(202) 555-0163',
      language: 'Spanish',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Amlodipine 5 mg'],
      nextAppointment: { date: '2027-01-06', clinician: 'Dr. Sarah Lee' },
    },
    [{ name: 'Amlodipine 5 mg', perDay: 1, sent: 30, confirmed: 27, courseDays: 90 }],
  ),
  patient({
    id: 'EW-004825',
    fullName: 'Grace Chen',
    dateOfBirth: 'Nov 30, 1983',
    waPhone: '(202) 555-0137',
    language: 'English',
    primaryClinician: 'Dr. Sarah Lee',
    currentMedications: ['Cetirizine 10 mg'],
    nextAppointment: { date: '2026-11-18', clinician: 'Dr. Sarah Lee' },
  }),
  patient(
    {
      id: 'EW-004826',
      fullName: 'Samuel Adeyemi',
      dateOfBirth: 'Mar 5, 1950',
      waPhone: '(202) 555-0181',
      language: 'English',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Levothyroxine 50 mcg'],
      nextAppointment: { date: '2027-02-02', clinician: 'Dr. Sarah Lee' },
    },
    [{ name: 'Levothyroxine 50 mcg', perDay: 1, sent: 60, confirmed: 58, courseDays: 120 }],
  ),
  patient(
    {
      id: 'EW-004827',
      fullName: 'Hannah Kowalski',
      dateOfBirth: 'Aug 19, 1996',
      waPhone: '(202) 555-0124',
      language: 'English',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Sertraline 50 mg'],
      nextAppointment: { date: '2026-11-09', clinician: 'Dr. Sarah Lee' },
    },
    [{ name: 'Sertraline 50 mg', perDay: 1, sent: 10, confirmed: 6, courseDays: 60 }],
  ),
  patient(
    {
      id: 'EW-004828',
      fullName: 'Daniel Brooks',
      dateOfBirth: 'Dec 8, 1987',
      waPhone: '(202) 555-0156',
      language: 'English',
      primaryClinician: 'Dr. Sarah Lee',
      currentMedications: ['Prednisone 20 mg'],
      nextAppointment: { date: '2026-10-28', clinician: 'Dr. Sarah Lee' },
    },
    [{ name: 'Prednisone 20 mg', perDay: 1, sent: 3, confirmed: 3, courseDays: 5 }],
  ),
]

// TODO: replace with a query for the clinic's patients.
export function listPatients(): DemoPatientRecord[] {
  return demoPatients
}

// TODO: replace with a query for one patient by id.
export function getPatient(id: string): DemoPatientRecord | undefined {
  return demoPatients.find((p) => p.id === id)
}

/** Name of the signed-in clinician shown in the top bar. */
export const SIGNED_IN_DOCTOR = 'Dr. Sarah Lee'
