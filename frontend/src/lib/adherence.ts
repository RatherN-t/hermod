/** Dose numbers the patient list and patient card show, from an API `adherence` object. */
import type { Adherence } from './api'

export interface AdherenceSummary {
  /** Doses marked taken (late still counts as taken). */
  taken: number
  /** Doses whose time has passed and that have an outcome. */
  due: number
}

export function summarizeAdherence(a: Adherence): AdherenceSummary {
  const taken = a.taken + a.late
  return { taken, due: taken + a.missed + a.unknown }
}

export function adherencePercent({ taken, due }: AdherenceSummary): number {
  return due ? Math.round((taken / due) * 100) : 0
}
