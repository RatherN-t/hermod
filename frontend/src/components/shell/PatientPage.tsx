import { useEffect } from 'react'
import { ArrowLeft, BellOff } from 'lucide-react'
import { MedicationRemindersSection } from '@/features/med-reminders/MedicationRemindersSection'
import type { ReminderPatient } from '@/features/med-reminders/types'
import { summarizeAdherence } from '@/lib/adherence'
import { ApiError, api, type PatientDetail } from '@/lib/api'
import { clinicDate, clinicToday } from '@/lib/clinic-time'
import { firstName } from '@/lib/patient'
import { patientsHref } from '@/lib/router'
import { useApi } from '@/lib/useApi'
import { cn, focusRing } from '@/lib/utils'
import { AdherenceCard } from './AdherenceCard'
import { LoadError } from './LoadError'
import { PatientSidebar } from './PatientSidebar'

function reminderPatient(p: PatientDetail): ReminderPatient {
  const upcoming = p.nextAppointmentAt && new Date(p.nextAppointmentAt).getTime() > Date.now()
  return {
    id: p.id,
    firstName: firstName(p.name),
    nextAppointment: upcoming && p.nextAppointmentAt ? { date: clinicDate(p.nextAppointmentAt), clinician: p.doctorName } : null,
  }
}

export function PatientPage({ id }: { id: string }) {
  const numericId = /^\d+$/.test(id) ? Number(id) : null
  const {
    data: patient,
    error,
    reload,
  } = useApi(
    (signal) => (numericId === null ? Promise.reject(new ApiError(404, 'Not found')) : api.getPatient(numericId, signal)),
    numericId,
  )
  const notFound = !patient && error instanceof ApiError && error.status === 404
  const today = clinicToday()

  useEffect(() => {
    if (patient) document.title = `${patient.name} · Hermod`
    else if (notFound) document.title = 'Patient not found · Hermod'
  }, [patient, notFound])

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-4 md:px-6">
      <a
        href={patientsHref}
        className={cn(
          '-ml-2 inline-flex h-10 items-center gap-2 rounded-lg px-2 text-helper text-muted transition-colors duration-150 hover:text-ink',
          focusRing,
        )}
      >
        <ArrowLeft aria-hidden="true" className="size-4 stroke-[1.5]" />
        All patients
      </a>

      {patient ? (
        <div className="mt-2 grid gap-6 md:grid-cols-[15rem_minmax(0,1fr)]">
          <div className="flex flex-col gap-4 self-start">
            <PatientSidebar patient={patient} today={today} onChanged={reload} />
            <AdherenceCard
              summary={summarizeAdherence(patient.adherence)}
              prescribed={
                patient.reminders.some((r) => r.totalDoses === null)
                  ? null
                  : patient.reminders.reduce((sum, r) => sum + (r.totalDoses ?? 0), 0)
              }
            />
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            {patient.messagesStopped && (
              <p role="status" className="flex items-start gap-2 rounded-xl border border-border bg-subtle px-4 py-3 text-sm text-ink">
                <BellOff aria-hidden="true" className="mt-0.5 size-4 shrink-0 stroke-[1.5] text-muted" />
                <span>
                  Messages are stopped for {firstName(patient.name)}. Hermod won’t send check-ins or reply on Telegram, and upcoming doses
                  aren’t tracked. Resume messages from the patient card.
                </span>
              </p>
            )}
            <MedicationRemindersSection
              key={patient.id}
              patient={reminderPatient(patient)}
              today={today}
              reminders={patient.reminders}
              onChanged={reload}
            />
          </div>
        </div>
      ) : notFound ? (
        <div className="mt-2 rounded-xl border border-border bg-surface p-6">
          <h1 className="text-base font-medium text-ink">Patient not found</h1>
          <p className="mt-1 text-sm text-muted">No patient has the ID {id}. Go back to the list to pick another patient.</p>
        </div>
      ) : error ? (
        <LoadError className="mt-2" message={`Couldn’t load this patient. ${error.message}`} onRetry={() => void reload()} />
      ) : (
        <PatientSkeleton />
      )}
    </main>
  )
}

function PatientSkeleton() {
  const bar = 'block h-3 rounded bg-border'
  return (
    <div className="mt-2 grid gap-6 md:grid-cols-[15rem_minmax(0,1fr)]" aria-busy="true">
      <p className="sr-only">Loading patient…</p>
      <div aria-hidden="true" className="flex flex-col gap-4 self-start">
        <div className="rounded-xl border border-border bg-surface p-4">
          <span className="block size-20 rounded-lg bg-subtle" />
          <span className={cn(bar, 'mt-4 w-32')} />
          <div className="mt-4 flex flex-col gap-4 border-t border-border pt-4">
            {[20, 28, 16, 24].map((w) => (
              <span key={w} className={bar} style={{ width: `${w * 4}px` }} />
            ))}
          </div>
        </div>
        <div className="h-32 rounded-xl border border-border bg-surface" />
      </div>
      <div aria-hidden="true" className="flex flex-col gap-4">
        <div className="flex min-h-13 items-center border-b border-border pb-3">
          <span className={cn(bar, 'h-4 w-48')} />
        </div>
        <div className="h-16 rounded-xl border border-border bg-surface" />
      </div>
    </div>
  )
}
