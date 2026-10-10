import { ArrowLeft } from 'lucide-react'
import { MedicationRemindersSection } from '@/features/med-reminders/MedicationRemindersSection'
import { getAdherence } from '@/lib/adherence'
import { TODAY, getPatient } from '@/lib/demo-data'
import { patientsHref } from '@/lib/router'
import { cn, focusRing } from '@/lib/utils'
import { AdherenceCard } from './AdherenceCard'
import { PatientSidebar } from './PatientSidebar'

export function PatientPage({ id }: { id: string }) {
  const patient = getPatient(id)

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-4 md:px-6">
      <a
        href={patientsHref}
        className={cn('-ml-2 inline-flex h-10 items-center gap-2 rounded-lg px-2 text-helper text-muted transition-colors duration-150 hover:text-ink', focusRing)}
      >
        <ArrowLeft aria-hidden="true" className="size-4 stroke-[1.5]" />
        All patients
      </a>

      {patient ? (
        <div className="mt-2 grid gap-6 md:grid-cols-[15rem_minmax(0,1fr)]">
          <div className="flex flex-col gap-4 self-start">
            <PatientSidebar patient={patient} />
            <AdherenceCard summary={getAdherence(patient)} />
          </div>
          <MedicationRemindersSection key={patient.id} patient={patient} today={TODAY} initialReminders={patient.reminders} />
        </div>
      ) : (
        <div className="mt-2 rounded-xl border border-border bg-surface p-6">
          <h1 className="text-base font-medium text-ink">Patient not found</h1>
          <p className="mt-1 text-sm text-muted">No patient has the ID {id}. Go back to the list to pick another patient.</p>
        </div>
      )}
    </main>
  )
}
