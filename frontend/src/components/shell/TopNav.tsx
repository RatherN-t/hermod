import { Plus } from 'lucide-react'
import { patientsHref } from '@/lib/router'
import { cn, focusRing } from '@/lib/utils'

export function TopNav() {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex h-16 max-w-[1120px] items-center justify-between gap-4 px-4 md:px-6">
        <a href={patientsHref} className={cn('flex items-center gap-2 rounded-lg', focusRing)} aria-label="everwell home">
          <span aria-hidden="true" className="grid size-8 place-items-center rounded-lg bg-accent text-white">
            <Plus className="size-5 stroke-[2]" />
          </span>
          <span className="text-lg font-medium tracking-tight text-ink">everwell</span>
        </a>
      </div>
    </header>
  )
}
