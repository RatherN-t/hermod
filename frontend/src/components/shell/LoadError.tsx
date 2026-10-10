import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** Card shown when a page's data couldn't be fetched. */
export function LoadError({ message, onRetry, className }: { message: string; onRetry: () => void; className?: string }) {
  return (
    <div role="alert" className={cn('flex flex-col items-start gap-3 rounded-xl border border-border bg-surface p-6', className)}>
      <p className="text-sm text-ink">{message}</p>
      <Button variant="secondary" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}
