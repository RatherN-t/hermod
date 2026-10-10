import { useState } from 'react'
import { ChevronRight, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getAdherence, type AdherenceSummary } from '@/lib/adherence'
import { listPatients } from '@/lib/demo-data'
import { patientHref } from '@/lib/router'
import { cn, fieldBase } from '@/lib/utils'

export function PatientListPage() {
  const [query, setQuery] = useState('')
  const patients = listPatients()
  const q = query.trim().toLowerCase()
  const shown = q ? patients.filter((p) => p.fullName.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)) : patients

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-6 md:px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-medium text-ink">Patients</h1>
          <p className="text-helper text-muted">{patients.length} patients · fictional demo data</p>
        </div>
        <label className="relative sm:w-72">
          <span className="sr-only">Search patients by name or ID</span>
          <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 stroke-[1.5] text-muted" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or ID"
            className={cn(fieldBase, 'pl-9')}
          />
        </label>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-border bg-surface">
        {shown.length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-subtle text-helper text-muted">
              <tr>
                <th scope="col" className="hidden px-4 py-3 font-normal sm:table-cell sm:w-36">
                  ID
                </th>
                <th scope="col" className="px-4 py-3 font-normal">
                  Name
                </th>
                <th scope="col" className="px-4 py-3 font-normal sm:w-64">
                  Doses taken
                </th>
                <th scope="col" className="w-12 px-4 py-3">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {shown.map((p) => (
                <tr
                  key={p.id}
                  // The name link is the real target; the rest of the row is a bigger mouse target for it.
                  onClick={(e) => {
                    if (!(e.target as HTMLElement).closest('a')) window.location.hash = patientHref(p.id)
                  }}
                  className="cursor-pointer transition-colors duration-150 hover:bg-subtle"
                >
                  <td className="hidden px-4 py-3 text-muted tabular-nums sm:table-cell">{p.id}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-xs font-medium text-accent">
                        {p.initials}
                      </span>
                      <div className="min-w-0">
                        <a
                          href={patientHref(p.id)}
                          className="rounded font-medium text-ink outline-none hover:underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                        >
                          {p.fullName}
                        </a>
                        <p className="text-helper text-muted tabular-nums sm:hidden">{p.id}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <DosesTaken summary={getAdherence(p)} />
                  </td>
                  <td className="px-4 py-3 text-muted">
                    <ChevronRight aria-hidden="true" className="ml-auto size-4 stroke-[1.5]" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex flex-col items-start gap-2 p-6">
            <p className="text-sm text-ink">No patients match “{query.trim()}”.</p>
            <Button variant="secondary" onClick={() => setQuery('')}>
              Clear search
            </Button>
          </div>
        )}
      </div>
    </main>
  )
}

function DosesTaken({ summary: { taken, due } }: { summary: AdherenceSummary }) {
  if (due === 0) return <span className="text-helper text-muted">No doses yet</span>
  const pct = Math.round((taken / due) * 100)
  return (
    <div className="flex items-center gap-3 tabular-nums">
      <span className="whitespace-nowrap text-ink sm:w-16">
        {taken} of {due}
      </span>
      <div aria-hidden="true" className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-border sm:block">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-helper text-muted">{pct}%</span>
    </div>
  )
}
