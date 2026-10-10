import { useEffect, useRef, useState } from 'react'
import { CircleCheck, Copy, MessageSquareText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { PatientDetail } from '@/lib/api'
import { firstName, initials, languageLabel } from '@/lib/patient'
import { formatPhone, smsHref } from '@/lib/phone'
import { formatDate } from '@/lib/schedule'
import type { IsoDate } from '@/features/med-reminders/types'
import { RemovePatientDialog } from './RemovePatientDialog'

export function PatientSidebar({ patient: p, today }: { patient: PatientDetail; today: IsoDate }) {
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
      </dl>

      <div className="mt-4 border-t border-border pt-2">
        <RemovePatientDialog patient={p} />
      </div>
    </aside>
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
