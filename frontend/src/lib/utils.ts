import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Teach tailwind-merge about our custom 13px helper size so it isn't treated as a colour.
const twMerge = extendTailwindMerge({
  extend: { classGroups: { 'font-size': [{ text: ['helper'] }] } },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Shared focus treatment for buttons and other non-text controls. */
export const focusRing =
  'outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface'

/** Shared field treatment: 40px tall, 8px radius, 1px border, green focus ring. */
export const fieldBase =
  'h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-ink transition-[border-color,box-shadow] duration-150 outline-none hover:border-border-strong focus-visible:border-accent focus-visible:ring-[3px] focus-visible:ring-accent/25 disabled:cursor-not-allowed disabled:bg-subtle disabled:text-muted aria-invalid:border-danger aria-invalid:focus-visible:ring-danger/20'
