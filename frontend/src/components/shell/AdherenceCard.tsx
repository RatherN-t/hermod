import { adherencePercent, type AdherenceSummary } from '@/lib/adherence'

/** `prescribed` is every dose across the patient's courses (sum of the reminders' totalDoses), or null if one is open-ended. */
export function AdherenceCard({ summary, prescribed }: { summary: AdherenceSummary; prescribed: number | null }) {
  const { taken, due } = summary
  const pct = adherencePercent(summary)
  const missed = due - taken

  if (due === 0) {
    return (
      <section aria-labelledby="adherence-heading" className="rounded-xl border border-border bg-surface p-4">
        <h2 id="adherence-heading" className="text-helper text-muted">
          Doses taken
        </h2>
        <p className="mt-1 text-sm text-ink">No doses yet</p>
        <p className="mt-1 text-helper text-muted tabular-nums">
          {prescribed === null ? 'Ongoing course' : prescribed > 0 ? `${prescribed} prescribed in total` : 'Add a medication to start tracking.'}
        </p>
      </section>
    )
  }

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
        {missed} missed · {prescribed === null ? 'ongoing course' : `${prescribed} prescribed in total`}
      </p>
    </section>
  )
}
