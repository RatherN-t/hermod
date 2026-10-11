import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { clinicTimeNow } from '@/lib/clinic-time'
import { addDays, daysBetween, defaultTimes, endDate, isValidIsoDate, standardMessage, summarySentence } from '@/lib/schedule'
import { DurationCards } from './fields/DurationCards'
import { Field, FieldError } from './fields/Field'
import { fieldDescribedBy } from './fields/described-by'
import { MedicationCombobox } from './fields/MedicationCombobox'
import { MessageField } from './fields/MessageField'
import { TimesPerDay } from './fields/TimesPerDay'
import type { IsoDate, ReminderDraft, ReminderPatient } from './types'
import { validateDraft, type FieldKey } from './validation'

interface ReminderFormProps {
  patient: ReminderPatient
  today: IsoDate
  initial: ReminderDraft
  mode: 'new' | 'edit'
  /** Medication names to suggest. */
  options: string[]
  /** Medications that already have a reminder and can't be picked again. */
  taken: string[]
  saving: boolean
  /** Error from the API for the last submit. */
  submitError: string | null
  onSubmit: (draft: ReminderDraft) => void
  onCancel: () => void
}

export function ReminderForm(props: ReminderFormProps) {
  const { patient, today, initial, mode, options, taken, saving, submitError, onSubmit, onCancel } = props
  const [draft, setDraft] = useState<ReminderDraft>(initial)
  const [touched, setTouched] = useState<Partial<Record<FieldKey, boolean>>>({})
  const [submitAttempted, setSubmitAttempted] = useState(false)

  // Day counts and the summary are measured from the day before the course's first day.
  // An edited course keeps its original start; a new one starts on the picked day.
  const isNew = mode === 'new'
  const firstDay = isValidIsoDate(draft.startDate) ? draft.startDate : addDays(today, 1)
  const base = addDays(firstDay, -1)
  const minEnd = isNew ? (daysBetween(today, firstDay) > 0 ? firstDay : today) : today
  // Doses earlier today than now are skipped when a course starts today.
  const now = clinicTimeNow()
  const skipped = isNew && firstDay === today ? draft.timesOfDay.filter((t) => t <= now).length : 0

  const nextAppointment = patient.nextAppointment?.date ?? null
  const errors = validateDraft(draft, { today, base, minEnd, nextAppointment, checkStart: isNew })
  const isValid = Object.keys(errors).length === 0
  const shown = (key: FieldKey) => (touched[key] || submitAttempted ? (errors[key] ?? null) : null)
  const touch = (key: FieldKey) => setTouched((t) => (t[key] ? t : { ...t, [key]: true }))
  const update = (patch: Partial<ReminderDraft>) => setDraft((d) => ({ ...d, ...patch }))

  const end = endDate(
    { kind: draft.durationKind, days: draft.durationDays, untilDate: draft.untilDate, nextAppointment: nextAppointment ?? '' },
    base,
  )
  const sentence = summarySentence({ firstName: patient.firstName, times: draft.timesOfDay, today, base, end, skipped, hideStart: !isNew })

  const nameError = shown('name')
  const startError = shown('start')
  const timesError = shown('times')
  const durationError = shown('duration')
  const consentError = shown('consent')

  return (
    <form
      noValidate
      aria-label={mode === 'edit' ? `Edit reminders for ${draft.name}` : 'New medication reminder'}
      aria-busy={saving || undefined}
      className="rounded-xl border border-border bg-surface"
      onSubmit={(e) => {
        e.preventDefault()
        if (saving) return
        setSubmitAttempted(true)
        if (isValid && end) {
          onSubmit(draft)
          return
        }
        // Move keyboard and screen-reader users to the first field that needs attention.
        const form = e.currentTarget
        requestAnimationFrame(() => form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
      }}
    >
      <div className="flex flex-col gap-5 p-4 md:p-6">
        <h3 className="text-base font-medium text-ink">{mode === 'edit' ? `Edit ${initial.name}` : 'New reminder'}</h3>

        <Field
          id="reminder-medication"
          label="Medication"
          error={nameError}
          helper={mode === 'edit' ? 'To switch medication, add a new reminder.' : undefined}
        >
          <MedicationCombobox
            id="reminder-medication"
            value={draft.name}
            onChange={(name) =>
              setDraft((d) => ({
                ...d,
                name,
                // An untouched template follows the medication; edited text is left alone.
                customMessage:
                  d.customMessage === standardMessage(patient.firstName, d.name)
                    ? standardMessage(patient.firstName, name)
                    : d.customMessage,
              }))
            }
            onClose={() => touch('name')}
            options={options}
            taken={taken}
            disabled={mode === 'edit'}
            invalid={!!nameError}
            describedBy={fieldDescribedBy('reminder-medication', { helper: mode === 'edit', error: nameError })}
          />
        </Field>

        {isNew && (
          <Field
            id="reminder-start"
            label="Start date"
            error={startError}
            helper={skipped > 0 ? 'Doses earlier than now are skipped today.' : 'Today or any later date.'}
          >
            <Input
              id="reminder-start"
              type="date"
              min={today}
              value={draft.startDate}
              onChange={(e) => update({ startDate: e.target.value })}
              onBlur={() => touch('start')}
              aria-required="true"
              aria-invalid={startError ? true : undefined}
              aria-describedby={fieldDescribedBy('reminder-start', { helper: !startError, error: startError })}
              className="w-44 tabular-nums"
            />
          </Field>
        )}

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
            base={base}
            minEnd={minEnd}
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

        <MessageField
          firstName={patient.firstName}
          medication={draft.name}
          value={draft.customMessage}
          error={shown('message')}
          onChange={(customMessage) => update({ customMessage })}
          onBlur={() => touch('message')}
        />

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
              {patient.firstName} agreed to get medication reminders on Telegram
            </Label>
          </div>
          {consentError && <FieldError id="reminder-consent-error">{consentError}</FieldError>}
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between md:px-6">
        <div className="flex flex-col gap-2">
          <p aria-live="polite" className="text-helper text-muted" data-testid="reminder-summary">
            {sentence}
          </p>
          {submitError && (
            <div role="alert">
              <FieldError id="reminder-submit-error">{submitError}</FieldError>
            </div>
          )}
        </div>
        <div className="grid shrink-0 grid-cols-2 gap-2 sm:flex">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          {/* aria-disabled (not disabled) keeps it focusable; the submit handler blocks it and reveals inline errors. */}
          <Button type="submit" variant="primary" aria-disabled={!isValid || saving || undefined}>
            {saving ? (mode === 'edit' ? 'Saving…' : 'Starting…') : mode === 'edit' ? 'Save changes' : 'Start reminders'}
          </Button>
        </div>
      </div>
    </form>
  )
}
