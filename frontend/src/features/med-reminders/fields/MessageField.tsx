import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { standardMessage } from '@/lib/schedule'
import { MESSAGE_MAX } from '../validation'
import { fieldDescribedBy } from './described-by'
import { FieldError } from './Field'

interface MessageFieldProps {
  firstName: string
  medication: string
  /** null = send the standard message */
  value: string | null
  error?: string | null
  onChange: (value: string | null) => void
  onBlur: () => void
}

export function MessageField({ firstName, medication, value, error, onChange, onBlur }: MessageFieldProps) {
  const id = 'reminder-message'
  const custom = value !== null
  const standard = standardMessage(firstName, medication)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex min-h-10 items-center gap-3">
        <Switch
          id={`${id}-toggle`}
          checked={custom}
          // Start from the standard text so the admin only edits what they need.
          onCheckedChange={(on) => onChange(on ? standard : null)}
          aria-describedby={`${id}-toggle-helper`}
        />
        <div>
          <Label htmlFor={`${id}-toggle`} className="font-normal">
            Write your own message
          </Label>
          <p id={`${id}-toggle-helper`} className="text-helper text-muted">
            {custom ? 'Edit the text below.' : `Off: ${firstName} gets the standard reminder.`}
          </p>
        </div>
      </div>

      {custom && (
        <div className="flex flex-col gap-2">
          <Label htmlFor={id} className="sr-only">
            WhatsApp message
          </Label>
          <Textarea
            id={id}
            rows={3}
            value={value}
            maxLength={MESSAGE_MAX}
            onChange={(e) => onChange(e.target.value)}
            onBlur={onBlur}
            aria-invalid={error ? true : undefined}
            aria-describedby={fieldDescribedBy(id, { helper: true, error })}
          />
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
            <p id={`${id}-helper`} className="text-helper text-muted">
              “Taken” and “Remind me in 30 min” buttons are added automatically. {value.length}/{MESSAGE_MAX}
            </p>
            {value !== standard && (
              <Button variant="link" className="-mr-2 px-2" onClick={() => onChange(standard)}>
                Reset to standard
              </Button>
            )}
          </div>
          {error && <FieldError id={`${id}-error`}>{error}</FieldError>}
        </div>
      )}
    </div>
  )
}
