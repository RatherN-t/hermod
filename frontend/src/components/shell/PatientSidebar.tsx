import type { DemoPatientRecord } from '@/lib/demo-data'

export function PatientSidebar({ patient: p }: { patient: DemoPatientRecord }) {
  const rows: [string, string][] = [
    ['Date of birth', p.dateOfBirth],
    ['Phone', p.waPhone],
    ['Language', p.language],
    ['Doctor', p.primaryClinician],
  ]

  return (
    <aside aria-label="Patient" className="rounded-xl border border-border bg-surface p-4">
      {/* Initials stand in for a photo: this is a fictional demo patient. */}
      <span aria-hidden="true" className="grid size-20 place-items-center rounded-lg bg-accent-soft text-2xl font-medium text-accent">
        {p.initials}
      </span>
      <h1 className="mt-3 text-base font-medium text-ink">{p.fullName}</h1>
      <p className="text-helper text-muted">Fictional demo patient</p>

      <dl className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt className="text-helper text-muted">{k}</dt>
            <dd className="text-sm text-ink tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}
