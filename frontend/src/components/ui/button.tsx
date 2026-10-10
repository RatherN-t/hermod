import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn, focusRing } from '@/lib/utils'

const buttonVariants = cva(
  cn(
    'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:stroke-[1.5]',
    focusRing,
  ),
  {
    variants: {
      variant: {
        primary: 'bg-accent text-white hover:bg-accent-hover aria-disabled:hover:bg-accent',
        secondary: 'border border-border bg-surface text-ink hover:bg-subtle hover:border-border-strong',
        ghost: 'text-ink hover:bg-subtle',
        link: 'text-accent hover:underline underline-offset-4',
      },
      size: {
        default: 'h-10 px-4',
        sm: 'h-10 px-3 md:h-8',
        icon: 'size-10',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'default' },
  },
)

type ButtonProps = React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }

function Button({ className, variant, size, asChild = false, type = 'button', ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      data-slot="button"
      type={asChild ? undefined : type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { Button }
