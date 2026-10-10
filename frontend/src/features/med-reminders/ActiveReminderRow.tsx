import { Button } from '@/components/ui/button'
import type { Reminder } from '@/lib/api'
import { clinicDate } from '@/lib/clinic-time'
import { formatDate, scheduleLabel } from '@/lib/schedule'
import { cn } from '@/lib/utils'
import { FieldError } from './fields/Field'
import type { IsoDate } from './types'

interface ActiveReminderRowProps {
  reminder: Reminder
  today: IsoDate
  editing: boolean
  /** A pause/resume request for this row is in flight. */
  busy: boolean
  error: string | null
  onTogglePause: () => void
  onEdit: () => void
}

export function ActiveReminderRow({ reminder, today, editing, busy, error, onTogglePause, onEdit }: ActiveReminderRowProps) {
  const { status } = reminder
  const paused = status === 'paused'
  const ended = status === 'ended'
  const end = clinicDate(reminder.endDate)
  const ends = ended
    ? `Ended ${formatDate(end, today)}`
    : end === today
      ? 'ends today'
      : `until ${formatDate(end, today)}`
  const progress =
    status === 'scheduled'
      ? `Starts ${formatDate(clinicDate(reminder.startDate), today)}`
      : reminder.dosesSent === 0
        ? 'No doses sent yet'
        : `${reminder.dosesConfirmed} of ${reminder.dosesSent} doses taken`
  const errorId = `reminder-${reminder.id}-error`

  return (
    <li
      className={cn(
        'flex flex-col gap-3 rounded-xl border bg-surface px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4',
        editing ? 'border-accent' : 'border-border',
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink">
          {reminder.name}
          {paused && <span className="font-normal text-muted"> · Paused</span>}
        </p>
        <p className="text-helper text-muted">
          {scheduleLabel(reminder.timesOfDay)} · {ends}
          {reminder.customMessage !== null && ' · Custom message'}
        </p>
      </div>

      <p className="text-helper text-ink tabular-nums sm:text-right">{progress}</p>

      {!ended && (
        <div className="-ml-4 flex gap-1 sm:-mr-2 sm:ml-0">
          <Button
            variant="ghost"
            onClick={onTogglePause}
            disabled={busy}
            aria-label={`${paused ? 'Resume' : 'Pause'} ${reminder.name} reminders`}
            aria-describedby={error ? errorId : undefined}
          >
            {paused ? 'Resume' : 'Pause'}
          </Button>
          <Button variant="ghost" onClick={onEdit} disabled={editing} aria-label={`Edit ${reminder.name} reminders`}>
            Edit
          </Button>
        </div>
      )}

      {error && (
        <div role="alert" className="sm:basis-full">
          <FieldError id={errorId}>{error}</FieldError>
        </div>
      )}
    </li>
  )
}
