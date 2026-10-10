import { useState } from 'react'
import { Check, ChevronsUpDown, Plus } from 'lucide-react'
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn, fieldBase } from '@/lib/utils'

interface MedicationComboboxProps {
  id: string
  value: string
  onChange: (value: string) => void
  onClose: () => void
  options: string[]
  /** Medications that already have an active reminder (cannot be picked again). */
  taken: string[]
  invalid?: boolean
  disabled?: boolean
  describedBy?: string
}

export function MedicationCombobox({
  id,
  value,
  onChange,
  onClose,
  options,
  taken,
  invalid,
  disabled,
  describedBy,
}: MedicationComboboxProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const typed = query.trim()
  const exactMatch = options.some((o) => o.toLowerCase() === typed.toLowerCase())
  // Filter ourselves so the "Use …" row is always available for medications not on file.
  const matches = options.filter((o) => o.toLowerCase().includes(typed.toLowerCase()))

  function choose(next: string) {
    onChange(next)
    setOpen(false)
    setQuery('')
    onClose()
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setQuery('')
          onClose()
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          id={id}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          aria-required="true"
          disabled={disabled}
          className={cn(fieldBase, 'flex items-center justify-between gap-2 text-left')}
        >
          <span className={cn('truncate', !value && 'text-muted')}>{value || 'Choose or type a medication'}</span>
          <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 stroke-[1.5] text-muted" />
        </button>
      </PopoverTrigger>
      <PopoverContent aria-label="Choose a medication" className="w-[var(--radix-popover-trigger-width)] min-w-64 p-1">
        <Command loop shouldFilter={false}>
          <CommandInput
            aria-label="Search or type a medication"
            placeholder="Search or type, e.g. Amoxicillin 500 mg"
            value={query}
            onValueChange={setQuery}
          />
          <CommandList aria-label="Medications">
            {matches.length > 0 && (
              <CommandGroup heading="On file">
                {matches.map((option) => {
                  const hasReminder = taken.includes(option)
                  return (
                    <CommandItem key={option} value={option} disabled={hasReminder} onSelect={() => choose(option)}>
                      <Check
                        aria-hidden="true"
                        className={cn('text-accent', value === option ? 'opacity-100' : 'opacity-0')}
                      />
                      <span className="flex-1">{option}</span>
                      {hasReminder && <span className="text-xs text-muted">Reminder active</span>}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            )}
            {typed && !exactMatch && (
              <CommandGroup heading="Not on file">
                <CommandItem value={`use:${typed}`} onSelect={() => choose(typed)}>
                  <Plus aria-hidden="true" className="text-muted" />
                  <span>
                    Use “<span className="font-medium">{typed}</span>”
                  </span>
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
