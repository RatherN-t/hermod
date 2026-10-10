import * as React from 'react'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import { cn } from '@/lib/utils'

/** 36x20 visual track inside a 48x40 hit area (tap target). */
function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn('group -mx-1.5 -my-2.5 grid h-10 w-12 shrink-0 place-items-center rounded-lg outline-none', className)}
      {...props}
    >
      <span
        aria-hidden="true"
        className="flex h-5 w-9 items-center rounded-full bg-control transition-colors duration-150 group-focus-visible:ring-2 group-focus-visible:ring-accent group-focus-visible:ring-offset-2 group-data-[state=checked]:bg-accent"
      >
        <SwitchPrimitive.Thumb className="block size-4 translate-x-0.5 rounded-full bg-white transition-transform duration-150 data-[state=checked]:translate-x-[18px]" />
      </span>
    </SwitchPrimitive.Root>
  )
}

export { Switch }
