import type { AdherenceSummary } from '@/lib/adherence'

export function AdherenceCard({ summary }: { summary: AdherenceSummary }) {
  const { taken, due, prescribed } = summary
  const pct = due ? Math.round((taken / due) * 100) : 0
  const missed = due - taken

  return (
    <section aria-labelledby="adherence-heading" className="rounded-xl border border-border bg-surface p-4">
      <h2 id="adherence-heading" className="text-helper text-muted">
        Doses taken
      </h2>
      <p className="mt-1 flex items-baseline gap-2 text-ink tabular-nums">
        <span className="text-2xl font-medium">{taken}</span>
        <span className="text-sm text-muted">of {due} so far</span>
        <span className="ml-auto text-sm font-medium">{pct}%</span>
      </p>
      <div
        role="meter"
        aria-label="Doses taken so far"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${taken} of ${due} doses taken`}
        className="mt-3 h-2 overflow-hidden rounded-full bg-border"
      >
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-3 text-helper text-muted tabular-nums">
        {missed} missed · {prescribed} prescribed in total
      </p>
    </section>
  )
}
