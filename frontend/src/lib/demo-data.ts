import type { ActiveReminder, DemoPatient } from '@/features/med-reminders/types'

/**
 * Fictional demo data. Nothing here describes a real person.
 * "Today" is fixed so the copy and totals stay stable.
 */
export const TODAY: string = '2026-10-10'

export const demoPatient: DemoPatient & {
  initials: string
  age: number
  sex: string
  pronouns: string
  mrn: string
  dateOfBirth: string
  language: string
  primaryClinician: string
  insurance: string
} = {
  firstName: 'Eleanor',
  fullName: 'Eleanor Mitchell',
  initials: 'EM',
  age: 58,
  sex: 'Female',
  pronouns: 'she/her',
  mrn: 'EW-004821',
  dateOfBirth: 'Apr 18, 1968',
  waPhone: '(202) 555-0148',
  language: 'English',
  primaryClinician: 'Dr. Sarah Lee',
  insurance: 'Aster Health · PPO',
  currentMedications: ['Lisinopril 10 mg', 'Metformin 500 mg', 'Atorvastatin 20 mg'],
  nextAppointment: { date: '2027-01-08', clinician: 'Dr. Sarah Lee' },
}

export const seededReminders: ActiveReminder[] = [
  {
    id: 'rem-lisinopril',
    name: 'Lisinopril 10 mg',
    timesOfDay: ['08:00'],
    durationKind: 'appointment',
    durationDays: 7,
    untilDate: '',
    startDate: '2026-09-19',
    endDate: '2027-01-08',
    dosesSent: 21,
    dosesConfirmed: 18,
    totalDoses: 112,
    status: 'active',
    language: 'en',
    customMessage: null,
    alertOnMissed: true,
    waPhone: '(202) 555-0148',
  },
]
