import type * as React from 'react'
import { Minus, Plus } from 'lucide-react'
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'
import { RadioDot } from '@/components/ui/radio-group'
import { Input } from '@/components/ui/input'
import { addDays, formatDate } from '@/lib/schedule'
import { cn, focusRing } from '@/lib/utils'
import type { DurationKind, IsoDate } from '../types'
import { MAX_DAYS } from '../validation'

interface DurationCardsProps {
  id: string
  today: IsoDate
  kind: DurationKind
  days: number
  untilDate: IsoDate | ''
  nextAppointment: { date: IsoDate; clinician: string }
  onKindChange: (kind: DurationKind) => void
  onDaysChange: (days: number) => void
  onDateChange: (date: IsoDate | '') => void
  onBlur: () => void
  invalid?: boolean
  describedBy?: string
}

export function DurationCards(props: DurationCardsProps) {
  const { id, today, kind, days, untilDate, nextAppointment, onKindChange, onDaysChange, onDateChange, onBlur } = props
  const validDays = Number.isInteger(days) && days >= 1 && days <= MAX_DAYS

  return (
    <RadioGroupPrimitive.Root
      aria-labelledby={`${id}-label`}
      aria-describedby={props.describedBy}
      aria-required="true"
      value={kind}
      onValueChange={(v) => onKindChange(v as DurationKind)}
      className="flex flex-col gap-2"
    >
      <DurationCard
        value="appointment"
        checked={kind === 'appointment'}
        title="Until next appointment"
        detail={`${formatDate(nextAppointment.date, today, { weekday: true, forceYear: true })} with ${nextAppointment.clinician}`}
      />
      <DurationCard
        value="days"
        checked={kind === 'days'}
        title="Number of days"
        detail={validDays ? `Ends ${formatDate(addDays(today, days), today, { weekday: true })}` : `1 to ${MAX_DAYS} days`}
        invalid={props.invalid && kind === 'days'}
        control={
          <DayStepper
            value={days}
            onChange={(n) => {
              onKindChange('days')
              onDaysChange(n)
            }}
            onBlur={onBlur}
            invalid={props.invalid && kind === 'days'}
          />
        }
      />
      <DurationCard
        value="date"
        checked={kind === 'date'}
        title="Until a specific date"
        detail="Last day of reminders"
        invalid={props.invalid && kind === 'date'}
        control={
          <Input
            type="date"
            aria-label="Last day of reminders"
            min={addDays(today, 1)}
            value={untilDate}
            onChange={(e) => {
              onKindChange('date')
              onDateChange(e.target.value)
            }}
            onBlur={onBlur}
            aria-invalid={(props.invalid && kind === 'date') || undefined}
            className="w-40 tabular-nums"
          />
        }
      />
    </RadioGroupPrimitive.Root>
  )
}

function DurationCard({
  value,
  checked,
  title,
  detail,
  control,
  invalid,
}: {
  value: DurationKind
  checked: boolean
  title: string
  detail: string
  control?: React.ReactNode
  invalid?: boolean
}) {
  const titleId = `duration-${value}-title`
  const detailId = `duration-${value}-detail`
  return (
    <div
      className={cn(
        'relative flex min-h-14 flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border px-3 py-2 transition-colors duration-150',
        checked ? 'border-accent bg-accent-soft' : 'border-border bg-surface hover:border-border-strong',
        invalid && 'border-danger',
      )}
    >
      {/* The radio covers the whole card so clicking anywhere selects it; the inner control sits above it. */}
      <RadioGroupPrimitive.Item
        value={value}
        aria-labelledby={titleId}
        aria-describedby={detailId}
        className={cn('absolute inset-0 rounded-lg', focusRing)}
      />
      <div className="pointer-events-none flex min-w-48 flex-1 items-center gap-3">
        <RadioDot checked={checked} />
        <div className="min-w-0">
          <p id={titleId} className="text-sm font-medium text-ink">
            {title}
          </p>
          <p id={detailId} className="text-helper text-muted">
            {detail}
          </p>
        </div>
      </div>
      {control && <div className="relative z-10 ml-7">{control}</div>}
    </div>
  )
}

function DayStepper({
  value,
  onChange,
  onBlur,
  invalid,
}: {
  value: number
  onChange: (n: number) => void
  onBlur: () => void
  invalid?: boolean
}) {
  const safe = Number.isFinite(value) ? value : 0
  // Each segment carries its own 1px border (overlapping by 1px) so every tap target is the full 40px.
  const edge = invalid ? 'border-danger' : 'border-border'
  const btn = cn(
    'relative grid size-10 shrink-0 place-items-center border bg-surface text-ink transition-colors duration-150 hover:bg-subtle focus-visible:z-10 disabled:text-muted disabled:hover:bg-surface',
    edge,
    focusRing,
  )
  return (
    <div role="group" aria-label="Number of days" className="flex">
      <button
        type="button"
        aria-label="One day fewer"
        className={cn(btn, 'rounded-l-lg')}
        disabled={safe <= 1}
        onClick={() => onChange(Math.max(1, safe - 1))}
        onBlur={onBlur}
      >
        <Minus aria-hidden="true" className="size-4 stroke-[1.5]" />
      </button>
      <input
        type="text"
        inputMode="numeric"
        aria-label="Days"
        aria-invalid={invalid || undefined}
        value={Number.isFinite(value) && value > 0 ? String(value) : ''}
        onChange={(e) => {
          const digits = e.target.value.replace(/\D/g, '').slice(0, 2)
          onChange(digits ? Number(digits) : Number.NaN)
        }}
        onBlur={onBlur}
        className={cn(
          'relative -ml-px h-10 w-12 border bg-surface text-center text-sm text-ink tabular-nums outline-none focus-visible:z-10 focus-visible:border-accent focus-visible:ring-[3px] focus-visible:ring-accent/25',
          edge,
        )}
      />
      <button
        type="button"
        aria-label="One day more"
        className={cn(btn, '-ml-px rounded-r-lg')}
        disabled={safe >= MAX_DAYS}
        onClick={() => onChange(Math.min(MAX_DAYS, safe + 1))}
        onBlur={onBlur}
      >
        <Plus aria-hidden="true" className="size-4 stroke-[1.5]" />
      </button>
    </div>
  )
}
