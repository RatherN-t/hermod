import { PatientListPage } from '@/components/patients/PatientListPage'
import { PatientPage } from '@/components/shell/PatientPage'
import { TopNav } from '@/components/shell/TopNav'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useRoute } from '@/lib/router'

export default function App() {
  const route = useRoute()

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-dvh bg-page">
        <TopNav />
        {route.page === 'patient' ? <PatientPage id={route.id} /> : <PatientListPage page={route.listPage} />}
      </div>
    </TooltipProvider>
  )
}
