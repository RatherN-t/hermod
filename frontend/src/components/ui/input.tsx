import * as React from 'react'
import { cn, fieldBase } from '@/lib/utils'

function Input({ className, type = 'text', ...props }: React.ComponentProps<'input'>) {
  return <input type={type} data-slot="input" className={cn(fieldBase, className)} {...props} />
}

function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(fieldBase, 'h-auto min-h-20 resize-y py-2 leading-6', className)}
      {...props}
    />
  )
}

export { Input, Textarea }
