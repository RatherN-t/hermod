import { useEffect, useRef, useState } from 'react'
import { Bell, BellOff, CircleCheck, Copy, MessageSquareText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api, errorMessage, type PatientDetail } from '@/lib/api'
import { firstName, initials, languageLabel } from '@/lib/patient'
import { formatPhone, smsHref } from '@/lib/phone'
import { formatDate } from '@/lib/schedule'
import type { IsoDate } from '@/features/med-reminders/types'
import { RemovePatientDialog } from './RemovePatientDialog'

interface PatientSidebarProps {
  patient: PatientDetail
  today: IsoDate
  /** Called after a change saved here, so the page can reload the patient. */
  onChanged: () => void
}

export function PatientSidebar({ patient: p, today, onChanged }: PatientSidebarProps) {
  const rows: [string, string][] = [
    ['Date of birth', p.dateOfBirth ? formatDate(p.dateOfBirth, today, { forceYear: true }) : 'Not recorded'],
    ['Phone', formatPhone(p.phone)],
    ['Language', languageLabel(p.language)],
    ['Doctor', p.doctorName || 'Not assigned'],
  ]

  return (
    <aside aria-label="Patient" className="rounded-xl border border-border bg-surface p-4">
      {/* Initials stand in for a photo. */}
      <span aria-hidden="true" className="grid size-20 place-items-center rounded-lg bg-accent-soft text-2xl font-medium text-accent">
        {initials(p.name)}
      </span>
      <h1 className="mt-3 text-base font-medium text-ink">{p.name}</h1>
      {p.isSynthetic && <p className="text-helper text-muted">Demo patient</p>}

      <dl className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt className="text-helper text-muted">{k}</dt>
            <dd className="text-sm text-ink tabular-nums">{v}</dd>
          </div>
        ))}
        <div>
          <dt className="text-helper text-muted">Telegram</dt>
          <dd className="text-sm text-ink">
            <TelegramStatus patient={p} />
          </dd>
        </div>
        <div>
          <dt className="text-helper text-muted">Messages</dt>
          <dd className="text-sm text-ink">
            <MessagesControl patient={p} onChanged={onChanged} />
          </dd>
        </div>
      </dl>

      <div className="mt-4 border-t border-border pt-2">
        <RemovePatientDialog patient={p} />
      </div>
    </aside>
  )
}

/** Turn Hermod's Telegram messages off (no check-ins, no replies) or back on. */
function MessagesControl({ patient: p, onChanged }: { patient: PatientDetail; onChanged: () => void }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const stopped = p.messagesStopped

  async function toggle() {
    setSaving(true)
    setError(null)
    try {
      await api.updatePatient(p.id, { messagesStopped: !stopped })
      onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <span className="flex items-center gap-2">
        {stopped ? (
          <>
            <BellOff aria-hidden="true" className="size-4 stroke-[1.5] text-muted" />
            Stopped
          </>
        ) : (
          <>
            <Bell aria-hidden="true" className="size-4 stroke-[1.5] text-accent" />
            On
          </>
        )}
      </span>
      <span className="block text-helper text-muted">
        {stopped
          ? `Hermod won’t send ${firstName(p.name)} check-ins or replies.`
          : 'Check-ins and replies on Telegram.'}
      </span>
      <Button size="sm" variant="secondary" className="mt-2" aria-disabled={saving || undefined} onClick={() => !saving && void toggle()}>
        {saving ? (stopped ? 'Resuming…' : 'Stopping…') : stopped ? 'Resume messages' : 'Stop messages'}
      </Button>
      {error && (
        <p role="alert" className="mt-2 text-helper text-danger">
          {error}
        </p>
      )}
    </>
  )
}

function TelegramStatus({ patient: p }: { patient: PatientDetail }) {
  if (p.link.linked) {
    return (
      <span className="flex items-center gap-2">
        <CircleCheck aria-hidden="true" className="size-4 stroke-[1.5] text-accent" />
        Linked
      </span>
    )
  }
  const link = p.link.telegramLink
  if (!link) {
    return (
      <>
        <span className="block text-muted">Not linked yet</span>
        <span className="block text-helper text-muted">Start link unavailable: the server has no Telegram bot token.</span>
      </>
    )
  }
  const message = `Hi ${firstName(p.name)}, this is your clinic. Tap this link and press Start in Telegram to get your medication reminders: ${link}`
  return (
    <>
      <span className="block text-muted">Not linked yet. Send {firstName(p.name)} their link.</span>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button asChild size="sm" variant="secondary">
          <a href={smsHref(p.phone, message)}>
            <MessageSquareText aria-hidden="true" />
            Text link
          </a>
        </Button>
        <CopyButton text={link} />
      </div>
    </>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  return (
    <Button
      size="sm"
      variant="secondary"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
        } catch {
          return
        }
        setCopied(true)
        window.clearTimeout(timer.current)
        timer.current = window.setTimeout(() => setCopied(false), 2000)
      }}
    >
      <Copy aria-hidden="true" />
      <span aria-live="polite">{copied ? 'Copied' : 'Copy link'}</span>
    </Button>
  )
}
