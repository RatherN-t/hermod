import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Field } from '@/features/med-reminders/fields/Field'
import { fieldDescribedBy } from '@/features/med-reminders/fields/described-by'
import { ApiError, api, type PatientCreate } from '@/lib/api'
import { clinicDateTimeToUtc, clinicToday } from '@/lib/clinic-time'
import { isValidPhone, toApiPhone } from '@/lib/phone'
import { patientHref } from '@/lib/router'

interface Draft {
  name: string
  phone: string
  dateOfBirth: string
  language: 'en' | 'es'
  apptDate: string
  apptTime: string
  doctorName: string
}

type Errors = Partial<Record<'name' | 'phone' | 'dateOfBirth' | 'appt', string>>

function validate(d: Draft, today: string): Errors {
  const e: Errors = {}
  if (!d.name.trim()) e.name = 'Enter the patient’s full name.'
  if (!d.phone.trim()) e.phone = 'Enter a mobile number so you can text them their Telegram link.'
  else if (!isValidPhone(d.phone)) e.phone = 'Enter an Australian mobile like 0491 570 156, or start with + and the country code.'
  if (d.dateOfBirth && d.dateOfBirth > today) e.dateOfBirth = 'Date of birth can’t be in the future.'
  if (d.apptDate && d.apptDate < today) e.appt = 'Pick today or a later date.'
  return e
}

export function AddPatientForm({ defaultDoctor, onCancel }: { defaultDoctor: string; onCancel: () => void }) {
  const today = clinicToday()
  const [draft, setDraft] = useState<Draft>({
    name: '',
    phone: '',
    dateOfBirth: '',
    language: 'en',
    apptDate: '',
    apptTime: '09:00',
    doctorName: defaultDoctor,
  })
  const [touched, setTouched] = useState<Partial<Record<keyof Errors, boolean>>>({})
  const [attempted, setAttempted] = useState(false)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState<{ field?: 'phone'; message: string } | null>(null)

  const errors = validate(draft, today)
  const valid = Object.keys(errors).length === 0
  const shown = (k: keyof Errors) => (touched[k] || attempted ? errors[k] : undefined)
  const touch = (k: keyof Errors) => setTouched((t) => ({ ...t, [k]: true }))
  const update = (patch: Partial<Draft>) => {
    setDraft((d) => ({ ...d, ...patch }))
    setServerError(null)
  }

  const phoneError = shown('phone') ?? (serverError?.field === 'phone' ? serverError.message : undefined)

  async function submit(form: HTMLFormElement) {
    setAttempted(true)
    if (!valid) {
      requestAnimationFrame(() => form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
      return
    }
    const body: PatientCreate = {
      name: draft.name.trim(),
      phone: toApiPhone(draft.phone),
      language: draft.language,
      doctorName: draft.doctorName.trim(),
      ...(draft.dateOfBirth && { dateOfBirth: draft.dateOfBirth }),
      ...(draft.apptDate && { nextAppointmentAt: clinicDateTimeToUtc(draft.apptDate, draft.apptTime || '09:00') }),
    }
    setSaving(true)
    try {
      const created = await api.createPatient(body)
      // Their page shows the Telegram link to send them.
      window.location.hash = patientHref(created.id)
    } catch (e) {
      setSaving(false)
      if (e instanceof ApiError && e.status === 409) {
        setServerError({ field: 'phone', message: 'Another patient already has this number.' })
        requestAnimationFrame(() => form.querySelector<HTMLElement>('#patient-phone')?.focus())
      } else {
        setServerError({ message: e instanceof Error ? e.message : 'Couldn’t add the patient. Try again.' })
      }
    }
  }

  return (
    <form
      noValidate
      aria-label="Add patient"
      className="mt-4 rounded-xl border border-border bg-surface"
      onSubmit={(e) => {
        e.preventDefault()
        if (!saving) void submit(e.currentTarget)
      }}
    >
      <div className="flex flex-col gap-5 p-4 md:p-6">
        <h2 className="text-base font-medium text-ink">New patient</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="patient-name" label="Full name" required error={shown('name')}>
            <Input
              id="patient-name"
              autoComplete="off"
              value={draft.name}
              onChange={(e) => update({ name: e.target.value })}
              onBlur={() => touch('name')}
              aria-invalid={shown('name') ? true : undefined}
              aria-describedby={fieldDescribedBy('patient-name', { error: shown('name') })}
              autoFocus
            />
          </Field>
          <Field
            id="patient-phone"
            label="Mobile number"
            required
            helper="You’ll text their Telegram link to this number."
            error={phoneError}
          >
            <Input
              id="patient-phone"
              type="tel"
              inputMode="tel"
              autoComplete="off"
              placeholder="0491 570 156"
              value={draft.phone}
              onChange={(e) => update({ phone: e.target.value })}
              onBlur={() => touch('phone')}
              aria-invalid={phoneError ? true : undefined}
              aria-describedby={fieldDescribedBy('patient-phone', { helper: true, error: phoneError })}
              className="tabular-nums"
            />
          </Field>
          <Field id="patient-dob" label="Date of birth" error={shown('dateOfBirth')}>
            <Input
              id="patient-dob"
              type="date"
              max={today}
              value={draft.dateOfBirth}
              onChange={(e) => update({ dateOfBirth: e.target.value })}
              onBlur={() => touch('dateOfBirth')}
              aria-invalid={shown('dateOfBirth') ? true : undefined}
              aria-describedby={fieldDescribedBy('patient-dob', { error: shown('dateOfBirth') })}
            />
          </Field>
          <Field id="patient-language" label="Language">
            <Select value={draft.language} onValueChange={(v) => update({ language: v as Draft['language'] })}>
              <SelectTrigger id="patient-language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Spanish</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field id="patient-doctor" label="Doctor">
            <Input
              id="patient-doctor"
              autoComplete="off"
              value={draft.doctorName}
              onChange={(e) => update({ doctorName: e.target.value })}
            />
          </Field>
          <Field id="patient-appt" label="Next appointment" helper="Optional. Reminders can run until this visit." error={shown('appt')}>
            <div className="flex gap-2">
              <Input
                id="patient-appt"
                type="date"
                min={today}
                value={draft.apptDate}
                onChange={(e) => update({ apptDate: e.target.value })}
                onBlur={() => touch('appt')}
                aria-invalid={shown('appt') ? true : undefined}
                aria-describedby={fieldDescribedBy('patient-appt', { helper: true, error: shown('appt') })}
                className="min-w-0 flex-1"
              />
              <Input
                type="time"
                aria-label="Appointment time"
                value={draft.apptTime}
                disabled={!draft.apptDate}
                onChange={(e) => update({ apptTime: e.target.value })}
                className="w-32 shrink-0"
              />
            </div>
          </Field>
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between md:px-6">
        <p role="alert" className="text-helper text-danger">
          {serverError && !serverError.field ? serverError.message : ''}
        </p>
        <div className="grid shrink-0 grid-cols-2 gap-2 sm:flex">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" aria-disabled={!valid || saving || undefined}>
            {saving ? 'Adding…' : 'Add patient'}
          </Button>
        </div>
      </div>
    </form>
  )
}
