import { useState } from 'react'
import { Clock } from 'lucide-react'
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { formatTime } from '@/lib/schedule'
import { cn, focusRing } from '@/lib/utils'
import type { TimeOfDay } from '../types'

const COUNTS = [1, 2, 3, 4] as const

interface TimesPerDayProps {
  id: string
  times: TimeOfDay[]
  onCountChange: (n: number) => void
  onTimeChange: (index: number, time: TimeOfDay) => void
  onBlur: () => void
  invalid?: boolean
  describedBy?: string
}

export function TimesPerDay({ id, times, onCountChange, onTimeChange, onBlur, invalid, describedBy }: TimesPerDayProps) {
  return (
    <div className="flex flex-col gap-2">
      <RadioGroupPrimitive.Root
        aria-labelledby={`${id}-label`}
        aria-describedby={describedBy}
        aria-required="true"
        value={times.length ? String(times.length) : ''}
        onValueChange={(v) => onCountChange(Number(v))}
        orientation="horizontal"
        className="flex w-full max-w-72"
      >
        {COUNTS.map((n, i) => (
          <RadioGroupPrimitive.Item
            key={n}
            value={String(n)}
            className={cn(
              'relative h-10 flex-1 border border-border bg-surface text-sm text-ink transition-colors duration-150 hover:bg-subtle focus-visible:z-20 data-[state=checked]:z-10 data-[state=checked]:border-accent data-[state=checked]:bg-accent-soft data-[state=checked]:font-medium data-[state=checked]:text-accent',
              i > 0 && '-ml-px',
              i === 0 && 'rounded-l-lg',
              i === COUNTS.length - 1 && 'rounded-r-lg',
              focusRing,
            )}
          >
            {n}×<span className="sr-only"> a day</span>
          </RadioGroupPrimitive.Item>
        ))}
      </RadioGroupPrimitive.Root>

      {times.length > 0 && (
        <ul aria-label="Dose times" className="flex flex-wrap gap-2" data-invalid={invalid || undefined}>
          {times.map((time, i) => (
            <li key={i}>
              <TimeChip index={i} time={time} onChange={(t) => onTimeChange(i, t)} onClose={onBlur} invalid={invalid} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TimeChip({
  index,
  time,
  onChange,
  onClose,
  invalid,
}: {
  index: number
  time: TimeOfDay
  onChange: (t: TimeOfDay) => void
  onClose: () => void
  invalid?: boolean
}) {
  const [open, setOpen] = useState(false)
  const inputId = `dose-time-${index}`
  const display = time ? formatTime(time) : 'Set time'

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) onClose()
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Dose ${index + 1} time, ${display}`}
          className={cn(
            'inline-flex h-10 items-center gap-2 rounded-lg border bg-surface px-3 text-sm text-ink tabular-nums transition-colors duration-150 hover:border-border-strong hover:bg-subtle',
            invalid ? 'border-danger' : 'border-border',
            focusRing,
          )}
        >
          <Clock aria-hidden="true" className="size-4 stroke-[1.5] text-muted" />
          {display}
        </button>
      </PopoverTrigger>
      <PopoverContent aria-label={`Change dose ${index + 1} time`} className="w-56 p-3">
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            // The popover is portalled, but React still bubbles submit to the outer reminder form.
            e.preventDefault()
            e.stopPropagation()
            setOpen(false)
            onClose()
          }}
        >
          <Label htmlFor={inputId}>Dose {index + 1} time</Label>
          <Input id={inputId} type="time" step={300} value={time} onChange={(e) => onChange(e.target.value)} />
          <Button type="submit" variant="secondary" className="w-full">
            Done
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  )
}
