import { useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api, errorMessage, type Reminder } from '@/lib/api'
import { addDays } from '@/lib/schedule'
import { ActiveReminderRow } from './ActiveReminderRow'
import { courseBase, createBody, draftFromReminder, emptyDraft, updateBody } from './draft'
import { ReminderForm } from './ReminderForm'
import type { IsoDate, ReminderDraft, ReminderPatient } from './types'

interface Props {
  patient: ReminderPatient
  today: IsoDate
  reminders: Reminder[]
  /** Refetch the patient after a write so the reminders and dose numbers update. */
  onChanged: () => Promise<void>
}

type FormState = { mode: 'new'; key: number } | { mode: 'edit'; id: number; key: number } | null

export function MedicationRemindersSection({ patient, today, reminders, onChanged }: Props) {
  const [form, setForm] = useState<FormState>(null)
  const [saving, setSaving] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [pausing, setPausing] = useState<number | null>(null)
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const addButton = useRef<HTMLButtonElement>(null)

  const editing = form?.mode === 'edit' ? reminders.find((r) => r.id === form.id) : undefined
  const options = [...new Set(reminders.map((r) => r.name))]
  const taken = reminders.filter((r) => r.status !== 'ended' && r.id !== editing?.id).map((r) => r.name)
  const nextKey = (form?.key ?? 0) + 1

  function openForm(next: FormState) {
    setSubmitError(null)
    setForm(next)
  }

  function closeForm() {
    setForm(null)
    setSubmitError(null)
    // The form unmounts; send keyboard focus somewhere sensible instead of <body>.
    requestAnimationFrame(() => addButton.current?.focus())
  }

  async function handleSubmit(draft: ReminderDraft) {
    const name = draft.name.trim()
    setSaving(true)
    setSubmitError(null)
    try {
      if (editing) {
        const body = updateBody(draftFromReminder(editing), draft)
        if (Object.keys(body).length > 0) await api.updateReminder(editing.id, body)
        await onChanged()
        setAnnouncement(`Reminders for ${name} updated.`)
      } else {
        await api.createReminder(patient.id, createBody(draft, today))
        await onChanged()
        setAnnouncement(`Reminders for ${name} started.`)
      }
      closeForm()
    } catch (e) {
      setSubmitError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function togglePause(target: Reminder) {
    const status = target.status === 'paused' ? 'active' : 'paused'
    setPausing(target.id)
    setRowError(null)
    try {
      await api.updateReminder(target.id, { status })
      await onChanged()
      setAnnouncement(`Reminders for ${target.name} ${status === 'paused' ? 'paused' : 'resumed'}.`)
    } catch (e) {
      setRowError({ id: target.id, message: errorMessage(e) })
    } finally {
      setPausing(null)
    }
  }

  return (
    <section aria-labelledby="med-reminders-heading" className="flex min-w-0 flex-col gap-4">
      <header className="flex min-h-13 items-center justify-between gap-4 border-b border-border pb-3">
        <h2 id="med-reminders-heading" className="text-lg font-medium text-ink md:text-xl">
          Medication reminders
        </h2>
        {!form && (
          <Button ref={addButton} variant="secondary" onClick={() => openForm({ mode: 'new', key: nextKey })}>
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
              busy={pausing === r.id}
              error={rowError?.id === r.id ? rowError.message : null}
              onTogglePause={() => void togglePause(r)}
              onEdit={() => openForm({ mode: 'edit', id: r.id, key: nextKey })}
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
          base={courseBase(today, editing)}
          minEnd={editing ? today : addDays(today, 1)}
          mode={editing ? 'edit' : 'new'}
          initial={editing ? draftFromReminder(editing) : emptyDraft(patient)}
          options={options}
          taken={taken}
          saving={saving}
          submitError={submitError}
          onSubmit={(draft) => void handleSubmit(draft)}
          onCancel={closeForm}
        />
      )}

      <p role="status" className="sr-only">
        {announcement}
      </p>
    </section>
  )
}
