import { useEffect, useState } from 'react'

/** Minimal hash router: `#/` (or `#/?page=2`) is the patient list, `#/patients/:id` is one patient. */
export type Route = { page: 'patients'; listPage: number } | { page: 'patient'; id: string }

export function parseRoute(hash: string): Route {
  const match = /^#\/patients\/([^/]+)$/.exec(hash)
  if (match) return { page: 'patient', id: decodeURIComponent(match[1]) }
  const n = Number(/[?&]page=(\d+)/.exec(hash)?.[1] ?? 1)
  return { page: 'patients', listPage: Math.max(1, n) }
}

export const patientHref = (id: number | string) => `#/patients/${encodeURIComponent(id)}`
export const patientsHref = '#/'
export const patientsPageHref = (n: number) => (n <= 1 ? patientsHref : `#/?page=${n}`)

export function useRoute(): Route {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash)
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return parseRoute(hash)
}
