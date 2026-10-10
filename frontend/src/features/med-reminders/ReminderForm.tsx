import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { defaultTimes, endDate, summarySentence } from '@/lib/schedule'
import { DurationCards } from './fields/DurationCards'
import { Field, FieldError } from './fields/Field'
import { fieldDescribedBy } from './fields/described-by'
import { MedicationCombobox } from './fields/MedicationCombobox'
import { TimesPerDay } from './fields/TimesPerDay'
import type { DemoPatient, IsoDate, ReminderDraft } from './types'
import { validateDraft, type FieldKey } from './validation'

interface ReminderFormProps {
  patient: DemoPatient
  today: IsoDate
  initial: ReminderDraft
  mode: 'new' | 'edit'
  /** Medications that already have a reminder and can't be picked again. */
  taken: string[]
  onSubmit: (draft: ReminderDraft, end: IsoDate) => void
  onCancel: () => void
}

export function ReminderForm({ patient, today, initial, mode, taken, onSubmit, onCancel }: ReminderFormProps) {
  const [draft, setDraft] = useState<ReminderDraft>(initial)
  const [touched, setTouched] = useState<Partial<Record<FieldKey, boolean>>>({})
  const [submitAttempted, setSubmitAttempted] = useState(false)

  const errors = validateDraft(draft, { today, nextAppointment: patient.nextAppointment.date })
  const isValid = Object.keys(errors).length === 0
  const shown = (key: FieldKey) => (touched[key] || submitAttempted ? (errors[key] ?? null) : null)
  const touch = (key: FieldKey) => setTouched((t) => (t[key] ? t : { ...t, [key]: true }))
  const update = (patch: Partial<ReminderDraft>) => setDraft((d) => ({ ...d, ...patch }))

  const end = endDate(
    { kind: draft.durationKind, days: draft.durationDays, untilDate: draft.untilDate, nextAppointment: patient.nextAppointment.date },
    today,
  )
  const sentence = summarySentence({ firstName: patient.firstName, times: draft.timesOfDay, today, end })

  const nameError = shown('name')
  const timesError = shown('times')
  const durationError = shown('duration')
  const consentError = shown('consent')

  return (
    <form
      noValidate
      aria-label={mode === 'edit' ? `Edit reminders for ${draft.name}` : 'New medication reminder'}
      className="rounded-xl border border-border bg-surface"
      onSubmit={(e) => {
        e.preventDefault()
        setSubmitAttempted(true)
        if (isValid && end) {
          onSubmit(draft, end)
          return
        }
        // Move keyboard and screen-reader users to the first field that needs attention.
        const form = e.currentTarget
        requestAnimationFrame(() => form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
      }}
    >
      <div className="flex flex-col gap-5 p-4 md:p-6">
        <h3 className="text-base font-medium text-ink">{mode === 'edit' ? `Edit ${initial.name}` : 'New reminder'}</h3>

        <Field id="reminder-medication" label="Medication" error={nameError}>
          <MedicationCombobox
            id="reminder-medication"
            value={draft.name}
            onChange={(name) => update({ name })}
            onClose={() => touch('name')}
            options={patient.currentMedications}
            taken={taken}
            invalid={!!nameError}
            describedBy={fieldDescribedBy('reminder-medication', { error: nameError })}
          />
        </Field>

        <Field id="reminder-times" group label="Times a day" error={timesError}>
          <TimesPerDay
            id="reminder-times"
            times={draft.timesOfDay}
            onCountChange={(n) => update({ timesOfDay: defaultTimes(n) })}
            onTimeChange={(i, t) => setDraft((d) => ({ ...d, timesOfDay: d.timesOfDay.map((old, j) => (j === i ? t : old)) }))}
            onBlur={() => {
              touch('times')
              // Keep chips in chronological order once an edit is finished.
              setDraft((d) => ({ ...d, timesOfDay: [...d.timesOfDay].sort() }))
            }}
            invalid={!!timesError}
            describedBy={fieldDescribedBy('reminder-times', { error: timesError })}
          />
        </Field>

        <Field id="reminder-duration" group label="For how long" error={durationError}>
          <DurationCards
            id="reminder-duration"
            today={today}
            kind={draft.durationKind}
            days={draft.durationDays}
            untilDate={draft.untilDate}
            nextAppointment={patient.nextAppointment}
            onKindChange={(durationKind) => update({ durationKind })}
            onDaysChange={(durationDays) => update({ durationDays })}
            onDateChange={(untilDate) => update({ untilDate })}
            onBlur={() => touch('duration')}
            invalid={!!durationError}
            describedBy={fieldDescribedBy('reminder-duration', { error: durationError })}
          />
        </Field>

        <div className="flex flex-col gap-2">
          <div className="flex min-h-10 items-center gap-3">
            <Checkbox
              id="reminder-consent"
              checked={draft.consent}
              onCheckedChange={(c) => {
                update({ consent: c === true })
                touch('consent')
              }}
              aria-required="true"
              aria-invalid={consentError ? true : undefined}
              aria-describedby={consentError ? 'reminder-consent-error' : undefined}
            />
            <Label htmlFor="reminder-consent" className="font-normal">
              {patient.firstName} agreed to WhatsApp reminders at <span className="tabular-nums">{draft.waPhone}</span>
            </Label>
          </div>
          {consentError && <FieldError id="reminder-consent-error">{consentError}</FieldError>}
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between md:px-6">
        <p aria-live="polite" className="text-helper text-muted" data-testid="reminder-summary">
          {sentence}
        </p>
        <div className="grid shrink-0 grid-cols-2 gap-2 sm:flex">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          {/* aria-disabled (not disabled) keeps it focusable; the submit handler blocks it and reveals inline errors. */}
          <Button type="submit" variant="primary" aria-disabled={!isValid || undefined}>
            {mode === 'edit' ? 'Save changes' : 'Start reminders'}
          </Button>
        </div>
      </div>
    </form>
  )
}
