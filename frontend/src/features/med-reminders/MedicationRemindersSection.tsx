import { useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { addDays, reminderDays } from '@/lib/schedule'
import { ActiveReminderRow } from './ActiveReminderRow'
import { draftFromReminder, emptyDraft } from './draft'
import { ReminderForm } from './ReminderForm'
import type { ActiveReminder, DemoPatient, IsoDate, ReminderDraft, ReminderStatus } from './types'

interface Props {
  patient: DemoPatient
  today: IsoDate
  initialReminders: ActiveReminder[]
}

type FormState = { mode: 'new'; key: number } | { mode: 'edit'; id: string; key: number } | null

export function MedicationRemindersSection({ patient, today, initialReminders }: Props) {
  const [reminders, setReminders] = useState<ActiveReminder[]>(initialReminders)
  const [form, setForm] = useState<FormState>(null)
  const [announcement, setAnnouncement] = useState('')
  const addButton = useRef<HTMLButtonElement>(null)

  const editing = form?.mode === 'edit' ? reminders.find((r) => r.id === form.id) : undefined
  const taken = reminders.filter((r) => r.id !== editing?.id).map((r) => r.name)
  const nextKey = (form?.key ?? 0) + 1

  function closeForm() {
    setForm(null)
    // The form unmounts; send keyboard focus somewhere sensible instead of <body>.
    requestAnimationFrame(() => addButton.current?.focus())
  }

  function handleSubmit(draft: ReminderDraft, end: IsoDate) {
    const fields = {
      name: draft.name.trim(),
      timesOfDay: [...draft.timesOfDay].sort(),
      durationKind: draft.durationKind,
      durationDays: draft.durationDays,
      untilDate: draft.untilDate,
      endDate: end,
      totalDoses: draft.timesOfDay.length * reminderDays(today, end),
      language: draft.language,
      customMessage: draft.customMessage === null ? null : draft.customMessage.trim(),
      alertOnMissed: draft.alertOnMissed,
      waPhone: draft.waPhone,
    }
    if (editing) {
      setReminders((list) => list.map((r) => (r.id === editing.id ? { ...r, ...fields } : r)))
      setAnnouncement(`Reminders for ${fields.name} updated.`)
    } else {
      setReminders((list) => [
        ...list,
        { ...fields, id: `rem-${Date.now()}`, startDate: addDays(today, 1), dosesSent: 0, dosesConfirmed: 0, status: 'active' },
      ])
      setAnnouncement(`Reminders for ${fields.name} started.`)
    }
    closeForm()
  }

  function togglePause(id: string) {
    const target = reminders.find((r) => r.id === id)
    if (!target) return
    const status: ReminderStatus = target.status === 'paused' ? 'active' : 'paused'
    setReminders((list) => list.map((r) => (r.id === id ? { ...r, status } : r)))
    setAnnouncement(`Reminders for ${target.name} ${status === 'paused' ? 'paused' : 'resumed'}.`)
  }

  return (
    <section aria-labelledby="med-reminders-heading" className="flex min-w-0 flex-col gap-4">
      <header className="flex min-h-13 items-center justify-between gap-4 border-b border-border pb-3">
        <h2 id="med-reminders-heading" className="text-lg font-medium text-ink md:text-xl">
          Medication reminders
        </h2>
        {!form && (
          <Button ref={addButton} variant="secondary" onClick={() => setForm({ mode: 'new', key: nextKey })}>
            <Plus aria-hidden="true" />
            Add medication
          </Button>
        )}
      </header>

      {reminders.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {reminders.map((r) => (
            <ActiveReminderRow
              key={r.id}
              reminder={r}
              today={today}
              editing={editing?.id === r.id}
              onTogglePause={() => togglePause(r.id)}
              onEdit={() => setForm({ mode: 'edit', id: r.id, key: nextKey })}
            />
          ))}
        </ul>
      ) : (
        !form && <p className="text-sm text-muted">No reminders yet. Add a medication to start sending Telegram reminders.</p>
      )}

      {form && (
        <ReminderForm
          key={form.key}
          patient={patient}
          today={today}
          mode={editing ? 'edit' : 'new'}
          initial={editing ? draftFromReminder(editing, patient) : emptyDraft(patient)}
          taken={taken}
          onSubmit={handleSubmit}
          onCancel={closeForm}
        />
      )}

      <p role="status" className="sr-only">
        {announcement}
      </p>
    </section>
  )
}
