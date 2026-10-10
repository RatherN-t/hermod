import { useEffect } from 'react'
import { PatientListPage } from '@/components/patients/PatientListPage'
import { PatientPage } from '@/components/shell/PatientPage'
import { TopNav } from '@/components/shell/TopNav'
import { TooltipProvider } from '@/components/ui/tooltip'
import { SIGNED_IN_DOCTOR, getPatient } from '@/lib/demo-data'
import { useRoute } from '@/lib/router'

export default function App() {
  const route = useRoute()
  const patientName = route.page === 'patient' ? getPatient(route.id)?.fullName : undefined

  useEffect(() => {
    document.title = route.page === 'patient' ? `${patientName ?? 'Patient not found'} · everwell` : 'Patients · everwell'
  }, [route.page, patientName])

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-dvh bg-page">
        <TopNav doctorName={SIGNED_IN_DOCTOR} />
        {route.page === 'patient' ? <PatientPage id={route.id} /> : <PatientListPage />}
      </div>
    </TooltipProvider>
  )
}
