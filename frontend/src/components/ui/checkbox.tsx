import * as React from 'react'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * 18px visual box inside a 40px hit area (tap target). The negative margin keeps
 * the visible box aligned to the content edge.
 */
function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn('group peer -m-[11px] grid size-10 shrink-0 place-items-center rounded-lg outline-none', className)}
      {...props}
    >
      <span
        aria-hidden="true"
        className="grid size-[18px] place-items-center rounded-[4px] border border-control bg-surface transition-colors duration-150 group-hover:border-muted group-focus-visible:ring-2 group-focus-visible:ring-accent group-focus-visible:ring-offset-2 group-aria-invalid:border-danger group-data-[state=checked]:border-accent group-data-[state=checked]:bg-accent"
      >
        <CheckboxPrimitive.Indicator className="text-white">
          <Check className="size-3.5 stroke-[2]" />
        </CheckboxPrimitive.Indicator>
      </span>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
