import * as React from 'react'
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'
import { cn } from '@/lib/utils'

const RadioGroup = RadioGroupPrimitive.Root

function RadioGroupItem({ className, ...props }: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return <RadioGroupPrimitive.Item data-slot="radio-group-item" className={cn(className)} {...props} />
}

/** The small circle used inside radio cards. Purely visual. */
function RadioDot({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'grid size-4 shrink-0 place-items-center rounded-full border bg-surface transition-colors duration-150',
        checked ? 'border-accent' : 'border-control',
      )}
    >
      {checked && <span className="size-2 rounded-full bg-accent" />}
    </span>
  )
}

export { RadioGroup, RadioGroupItem, RadioDot }
