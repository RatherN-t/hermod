/**
 * Typed client for the Hermod API (see docs/API.md). Only the shapes the dashboard uses are
 * typed here; `/docs` on the API has the full schemas.
 */
import type { DurationKind, IsoDate, TimeOfDay } from '@/features/med-reminders/types'

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
const API_KEY = import.meta.env.VITE_API_KEY

/** ISO 8601 datetime in UTC, e.g. "2026-10-10T21:00:00Z". */
export type IsoDateTime = string

export interface Adherence {
  taken: number
  late: number
  missed: number
  unknown: number
  extra: number
  /** Past-due doses still waiting for a reply (under 6 hours old). Not future doses. */
  pending: number
  adherencePct: number | null
}

export interface TelegramLink {
  linked: boolean
  linkCode: string
  /** null when the backend has no bot token. */
  telegramLink: string | null
}

export type ReminderStatus = 'active' | 'paused' | 'scheduled' | 'ended'

export interface Reminder {
  id: number
  patientId: number
  name: string
  dose: string
  instructions: string
  timesOfDay: TimeOfDay[]
  durationKind: DurationKind
  /** Only set for durationKind "days". */
  durationDays: number | null
  startDate: IsoDateTime
  endDate: IsoDateTime
  status: ReminderStatus
  customMessage: string | null
  alertOnMissed: boolean
  dosesSent: number
  dosesConfirmed: number
  totalDoses: number
  nextDoseAt: IsoDateTime | null
}

export interface PatientListItem {
  id: number
  name: string
  phone: string
  doctorName: string
  language: string
  isSynthetic: boolean
  telegramLinked: boolean
  nextAppointmentAt: IsoDateTime | null
  activeReminders: number
  adherence: Adherence
}

export interface PatientDetail extends PatientListItem {
  dateOfBirth: IsoDate | null
  notes: string
  link: TelegramLink
  reminders: Reminder[]
}

export interface ReminderCreate {
  name: string
  timesOfDay: TimeOfDay[]
  durationKind: DurationKind
  durationDays?: number
  untilDate?: IsoDate
  startDate?: IsoDate
  customMessage: string | null
  alertOnMissed: boolean
}

export interface PatientCreate {
  name: string
  /** Digits only, international form without "+", e.g. "61491570156". */
  phone: string
  doctorName?: string
  dateOfBirth?: IsoDate
  language?: 'en' | 'es'
  nextAppointmentAt?: IsoDateTime
}

export interface ReminderUpdate {
  status?: 'active' | 'paused'
  timesOfDay?: TimeOfDay[]
  durationKind?: DurationKind
  durationDays?: number
  untilDate?: IsoDate
  /** "" = back to the standard message. */
  customMessage?: string
  alertOnMissed?: boolean
}

export class ApiError extends Error {
  /** HTTP status, or 0 when the server couldn't be reached. */
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type ValidationItem = { loc?: (string | number)[]; msg?: string }

function detailMessage(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationItem[]).map((d) => {
      const msg = (d.msg ?? '').replace(/^Value error, /, '')
      const field = d.loc?.filter((l) => l !== 'body').at(-1)
      return field !== undefined ? `${field}: ${msg}` : msg
    })
    return parts.filter(Boolean).join(' ') || null
  }
  return null
}

async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  const h = new Headers(headers)
  if (json !== undefined) h.set('Content-Type', 'application/json')
  if (API_KEY) h.set('X-API-Key', API_KEY)

  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...rest, headers: h, body: json !== undefined ? JSON.stringify(json) : rest.body })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'Can’t reach the server. Check your connection and try again.')
  }

  if (!res.ok) {
    let message: string | null = null
    try {
      message = detailMessage(((await res.json()) as { detail?: unknown }).detail)
    } catch {
      // Not JSON; fall back to the status below.
    }
    throw new ApiError(res.status, message ?? `Request failed (${res.status}).`)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  listPatients: (signal?: AbortSignal) => request<PatientListItem[]>('/api/patients', { signal }),
  getPatient: (id: number, signal?: AbortSignal) => request<PatientDetail>(`/api/patients/${id}`, { signal }),
  createPatient: (body: PatientCreate) => request<PatientDetail>('/api/patients', { method: 'POST', json: body }),
  /** Permanent: deletes the patient and all their reminders, doses, messages and flags. */
  deletePatient: (id: number) => request<void>(`/api/patients/${id}`, { method: 'DELETE' }),
  createReminder: (patientId: number, body: ReminderCreate) =>
    request<Reminder>(`/api/patients/${patientId}/reminders`, { method: 'POST', json: body }),
  updateReminder: (id: number, body: ReminderUpdate) =>
    request<Reminder>(`/api/reminders/${id}`, { method: 'PATCH', json: body }),
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'Something went wrong. Try again.'
}
