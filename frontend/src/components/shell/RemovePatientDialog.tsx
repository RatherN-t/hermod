import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { api, errorMessage, type PatientDetail } from '@/lib/api'
import { firstName } from '@/lib/patient'
import { patientsHref } from '@/lib/router'
import { plural } from '@/lib/schedule'

/** "Remove patient" button plus the confirmation it always asks for first. */
export function RemovePatientDialog({ patient: p }: { patient: PatientDetail }) {
  const [open, setOpen] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const first = firstName(p.name)
  const reminders = p.reminders.length

  async function remove() {
    setRemoving(true)
    setError(null)
    try {
      await api.deletePatient(p.id)
      window.location.hash = patientsHref
    } catch (e) {
      setRemoving(false)
      setError(errorMessage(e))
    }
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (removing) return
        setOpen(next)
        setError(null)
      }}
    >
      <AlertDialogTrigger asChild>
        <Button variant="ghost" className="-mx-2 w-[calc(100%+16px)] justify-start px-2 text-danger hover:bg-danger/5">
          <Trash2 aria-hidden="true" />
          Remove patient
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogTitle>Remove {p.name}?</AlertDialogTitle>
        <AlertDialogDescription>
          This permanently deletes {first}’s profile
          {reminders > 0 ? `, ${plural(reminders, 'reminder', 'reminders')} and their dose history` : ''}, Telegram messages and
          flags. {first} will stop getting reminders. This can’t be undone.
        </AlertDialogDescription>
        {error && (
          <p role="alert" className="mt-3 text-helper text-danger">
            Couldn’t remove {first}. {error}
          </p>
        )}
        <div className="mt-6 grid grid-cols-2 gap-2 sm:flex sm:justify-end">
          <AlertDialogCancel asChild>
            <Button variant="secondary">Cancel</Button>
          </AlertDialogCancel>
          {/* Not AlertDialogAction: that closes the dialog before the request finishes. */}
          <Button variant="danger" aria-disabled={removing || undefined} onClick={() => !removing && void remove()}>
            {removing ? 'Removing…' : 'Remove patient'}
          </Button>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  )
}
