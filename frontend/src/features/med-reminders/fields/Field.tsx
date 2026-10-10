import type * as React from 'react'
import { CircleAlert } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface FieldProps {
  /** Base id. The label points at `${id}`; helper and error use `${id}-helper` / `${id}-error`. */
  id: string
  label: string
  required?: boolean
  /** Use for radio groups and other non-labelable controls: renders a span with `${id}-label` instead of <label>. */
  group?: boolean
  helper?: React.ReactNode
  error?: string | null
  labelAside?: React.ReactNode
  className?: string
  children: React.ReactNode
}

export function Field({ id, label, required, group, helper, error, labelAside, className, children }: FieldProps) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div className="flex items-baseline justify-between gap-2">
        {group ? (
          <span id={`${id}-label`} className="text-sm font-medium text-ink">
            {label}
            {required && (
              <span aria-hidden="true" className="ml-0.5 text-danger">
                *
              </span>
            )}
          </span>
        ) : (
          <Label htmlFor={id} required={required}>
            {label}
          </Label>
        )}
        {labelAside}
      </div>
      {children}
      {helper && !error && (
        <p id={`${id}-helper`} className="text-helper text-muted">
          {helper}
        </p>
      )}
      {error && <FieldError id={`${id}-error`}>{error}</FieldError>}
    </div>
  )
}

export function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <p id={id} className="flex items-start gap-2 text-helper text-danger">
      <CircleAlert aria-hidden="true" className="mt-px size-4 shrink-0 stroke-[1.5]" />
      <span>{children}</span>
    </p>
  )
}
