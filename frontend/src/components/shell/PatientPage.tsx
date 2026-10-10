import { TooltipProvider } from '@/components/ui/tooltip'
import { MedicationRemindersSection } from '@/features/med-reminders/MedicationRemindersSection'
import { TODAY, demoPatient } from '@/lib/demo-data'
import { PatientSidebar } from './PatientSidebar'
import { TopNav } from './TopNav'

export function PatientPage() {
  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-dvh bg-page">
        <TopNav doctorName={demoPatient.primaryClinician} />
        <main className="mx-auto grid max-w-[1120px] gap-6 px-4 py-6 md:grid-cols-[15rem_minmax(0,1fr)] md:px-6">
          <PatientSidebar />
          <MedicationRemindersSection patient={demoPatient} today={TODAY} />
        </main>
      </div>
    </TooltipProvider>
  )
}
