import { Button } from '@/components/ui/button'
import { formatDate, scheduleLabel } from '@/lib/schedule'
import { cn } from '@/lib/utils'
import type { ActiveReminder, IsoDate } from './types'

interface ActiveReminderRowProps {
  reminder: ActiveReminder
  today: IsoDate
  editing: boolean
  onTogglePause: () => void
  onEdit: () => void
}

export function ActiveReminderRow({ reminder, today, editing, onTogglePause, onEdit }: ActiveReminderRowProps) {
  const paused = reminder.status === 'paused'
  const ends = reminder.endDate === today ? 'ends today' : `until ${formatDate(reminder.endDate, today)}`
  const progress =
    reminder.dosesSent === 0
      ? `Starts ${formatDate(reminder.startDate, today)}`
      : `${reminder.dosesConfirmed} of ${reminder.dosesSent} doses taken`

  return (
    <li
      className={cn(
        'flex flex-col gap-3 rounded-xl border bg-surface px-4 py-3 sm:flex-row sm:items-center sm:gap-4',
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
        </p>
      </div>

      <p className="text-helper text-ink tabular-nums sm:text-right">{progress}</p>

      <div className="-ml-4 flex gap-1 sm:-mr-2 sm:ml-0">
        <Button variant="ghost" onClick={onTogglePause} aria-label={`${paused ? 'Resume' : 'Pause'} ${reminder.name} reminders`}>
          {paused ? 'Resume' : 'Pause'}
        </Button>
        <Button variant="ghost" onClick={onEdit} disabled={editing} aria-label={`Edit ${reminder.name} reminders`}>
          Edit
        </Button>
      </div>
    </li>
  )
}
