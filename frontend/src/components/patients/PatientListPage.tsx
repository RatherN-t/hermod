import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronRight, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LoadError } from '@/components/shell/LoadError'
import { AddPatientForm } from './AddPatientForm'
import { adherencePercent, summarizeAdherence, type AdherenceSummary } from '@/lib/adherence'
import { api, type PatientListItem } from '@/lib/api'
import { initials } from '@/lib/patient'
import { patientHref, patientsPageHref } from '@/lib/router'
import { plural } from '@/lib/schedule'
import { useApi } from '@/lib/useApi'
import { cn, fieldBase, focusRing } from '@/lib/utils'

function matches(p: PatientListItem, q: string): boolean {
  return p.name.toLowerCase().includes(q) || `#${p.id}` === q || String(p.id) === q
}

const PAGE_SIZE = 10

export function PatientListPage({ page }: { page: number }) {
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const { data, error, reload } = useApi((signal) => api.listPatients(signal))

  useEffect(() => {
    document.title = 'Patients · Hermod'
  }, [])

  const patients = data ? [...data].sort((a, b) => a.name.localeCompare(b.name)) : []
  const q = query.trim().toLowerCase()
  const shown = q ? patients.filter((p) => matches(p, q)) : patients
  const demo = patients.length > 0 && patients.every((p) => p.isSynthetic)
  const defaultDoctor = mostCommon(patients.map((p) => p.doctorName).filter(Boolean)) ?? ''
  const pageCount = Math.max(1, Math.ceil(shown.length / PAGE_SIZE))
  const current = Math.min(page, pageCount) // e.g. page 3 after removing patients
  const visible = shown.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  function search(value: string) {
    setQuery(value)
    // New results start from the first page (replace, so Back doesn't step through searches).
    if (page > 1) window.location.replace(patientsPageHref(1))
  }

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-6 md:px-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-medium text-ink">Patients</h1>
          <p className="min-h-[18px] text-helper text-muted">
            {data && `${plural(patients.length, 'patient', 'patients')}${demo ? ' · demo data' : ''}`}
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="relative sm:w-72">
            <span className="sr-only">Search patients by name or ID</span>
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 stroke-[1.5] text-muted"
            />
            <input
              type="search"
              value={query}
              onChange={(e) => search(e.target.value)}
              placeholder="Search by name or ID"
              className={cn(fieldBase, 'pl-9')}
            />
          </label>
          {!adding && (
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus aria-hidden="true" />
              Add patient
            </Button>
          )}
        </div>
      </div>

      {adding && <AddPatientForm defaultDoctor={defaultDoctor} onCancel={() => setAdding(false)} />}

      {!data && error ? (
        <LoadError className="mt-4" message={`Couldn’t load patients. ${error.message}`} onRetry={() => void reload()} />
      ) : (
        <div className="mt-4 overflow-hidden rounded-xl border border-border bg-surface">
          {!data || shown.length > 0 ? (
            <table className="w-full text-left text-sm" aria-busy={!data || undefined}>
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
                {data ? visible.map((p) => <PatientRow key={p.id} patient={p} />) : <SkeletonRows />}
              </tbody>
            </table>
          ) : (
            <div className="flex flex-col items-start gap-2 p-6">
              <p className="text-sm text-ink">No patients match “{query.trim()}”.</p>
              <Button variant="secondary" onClick={() => search('')}>
                Clear search
              </Button>
            </div>
          )}
        </div>
      )}

      {data && pageCount > 1 && (
        <Pagination
          current={current}
          pageCount={pageCount}
          total={shown.length}
          first={(current - 1) * PAGE_SIZE + 1}
          last={(current - 1) * PAGE_SIZE + visible.length}
        />
      )}
    </main>
  )
}

function PatientRow({ patient: p }: { patient: PatientListItem }) {
  return (
    <tr
      // The name link is the real target; the rest of the row is a bigger mouse target for it.
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest('a')) window.location.hash = patientHref(p.id)
      }}
      className="cursor-pointer transition-colors duration-150 hover:bg-subtle"
    >
      <td className="hidden px-4 py-3 text-muted tabular-nums sm:table-cell">#{p.id}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-xs font-medium text-accent"
          >
            {initials(p.name)}
          </span>
          <div className="min-w-0">
            <a
              href={patientHref(p.id)}
              className="rounded font-medium text-ink outline-none hover:underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            >
              {p.name}
            </a>
            {/* The ID column is hidden on phones, so the ID moves under the name there. */}
            <p className="text-helper text-muted tabular-nums">
              <span className="sm:hidden">#{p.id}</span>
              {p.messagesStopped && (
                <>
                  <span aria-hidden="true" className="sm:hidden">
                    {' · '}
                  </span>
                  Messages stopped
                </>
              )}
            </p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <DosesTaken summary={summarizeAdherence(p.adherence)} />
      </td>
      <td className="px-4 py-3 text-muted">
        <ChevronRight aria-hidden="true" className="ml-auto size-4 stroke-[1.5]" />
      </td>
    </tr>
  )
}

function SkeletonRows() {
  const bar = 'block h-3 rounded bg-border'
  return (
    <>
      {[40, 32, 44, 28, 36].map((w, i) => (
        <tr key={i} aria-hidden="true">
          <td className="hidden px-4 py-3 sm:table-cell">
            <span className={cn(bar, 'w-8')} />
          </td>
          <td className="px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="size-8 shrink-0 rounded-lg bg-subtle" />
              <span className={bar} style={{ width: `${w * 4}px` }} />
            </div>
          </td>
          <td className="px-4 py-3">
            <span className={cn(bar, 'w-24')} />
          </td>
          <td className="px-4 py-3" />
        </tr>
      ))}
      <tr className="sr-only">
        <td colSpan={4}>Loading patients…</td>
      </tr>
    </>
  )
}

function DosesTaken({ summary }: { summary: AdherenceSummary }) {
  const { taken, due } = summary
  if (due === 0) return <span className="text-helper text-muted">No doses yet</span>
  const pct = adherencePercent(summary)
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

function mostCommon(values: string[]): string | undefined {
  const counts = new Map<string, number>()
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1)
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
}

function Pagination({
  current,
  pageCount,
  total,
  first,
  last,
}: {
  current: number
  pageCount: number
  total: number
  first: number
  last: number
}) {
  const step = cn(
    'inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm font-medium text-ink transition-colors duration-150 hover:bg-subtle',
    focusRing,
  )
  const off = 'pointer-events-none opacity-50'
  return (
    <nav aria-label="Patient list pages" className="mt-4 flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
      <p className="text-helper text-muted tabular-nums">
        Showing {first}–{last} of {total}
      </p>
      <div className="flex items-center gap-2">
        <a
          href={patientsPageHref(current - 1)}
          aria-disabled={current === 1 || undefined}
          tabIndex={current === 1 ? -1 : undefined}
          className={cn(step, current === 1 && off)}
        >
          <ArrowLeft aria-hidden="true" className="size-4 stroke-[1.5]" />
          Previous
        </a>
        <ol className="flex items-center gap-1">
          {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
            <li key={n}>
              <a
                href={patientsPageHref(n)}
                aria-label={`Page ${n}`}
                aria-current={n === current ? 'page' : undefined}
                className={cn(
                  'grid size-10 place-items-center rounded-lg text-sm tabular-nums transition-colors duration-150',
                  n === current ? 'bg-accent font-medium text-white' : 'text-ink hover:bg-subtle',
                  focusRing,
                )}
              >
                {n}
              </a>
            </li>
          ))}
        </ol>
        <a
          href={patientsPageHref(current + 1)}
          aria-disabled={current === pageCount || undefined}
          tabIndex={current === pageCount ? -1 : undefined}
          className={cn(step, current === pageCount && off)}
        >
          Next
          <ArrowRight aria-hidden="true" className="size-4 stroke-[1.5]" />
        </a>
      </div>
    </nav>
  )
}
