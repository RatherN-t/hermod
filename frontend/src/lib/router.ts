import { useEffect, useState } from 'react'

/** Minimal hash router: `#/` is the patient list, `#/patients/:id` is one patient. */
export type Route = { page: 'patients' } | { page: 'patient'; id: string }

export function parseRoute(hash: string): Route {
  const match = /^#\/patients\/([^/]+)$/.exec(hash)
  return match ? { page: 'patient', id: decodeURIComponent(match[1]) } : { page: 'patients' }
}

export const patientHref = (id: string) => `#/patients/${encodeURIComponent(id)}`
export const patientsHref = '#/'

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
