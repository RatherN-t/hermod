import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

type Key = string | number | null

interface ApiState<T> {
  /** The key the data/error belong to. */
  key: Key
  data: T | undefined
  error: Error | undefined
  loading: boolean
}

/**
 * Fetch on mount and whenever `key` changes (e.g. a patient id); the previous request is
 * aborted. `reload()` refetches while keeping the current data on screen, and resolves once
 * it's done.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, key: Key = null) {
  const [state, setState] = useState<ApiState<T>>({ key, data: undefined, error: undefined, loading: true })
  const fetcherRef = useRef(fetcher)
  const keyRef = useRef(key)
  const controller = useRef<AbortController | null>(null)

  useLayoutEffect(() => {
    fetcherRef.current = fetcher
    keyRef.current = key
  })

  const reload = useCallback(async () => {
    controller.current?.abort()
    const ctrl = new AbortController()
    controller.current = ctrl
    const forKey = keyRef.current
    const keep = (s: ApiState<T>) => (s.key === forKey ? s.data : undefined)
    setState((s) => ({ key: forKey, data: keep(s), error: undefined, loading: true }))
    try {
      const data = await fetcherRef.current(ctrl.signal)
      if (!ctrl.signal.aborted) setState({ key: forKey, data, error: undefined, loading: false })
    } catch (e) {
      if (!ctrl.signal.aborted) setState((s) => ({ key: forKey, data: keep(s), error: e as Error, loading: false }))
    }
  }, [])

  useEffect(() => {
    void reload()
    return () => controller.current?.abort()
  }, [key, reload])

  // Data for an old key (e.g. the previous patient) is never shown for the new one.
  if (state.key !== key) return { data: undefined, error: undefined, loading: true, reload }
  return { data: state.data, error: state.error, loading: state.loading, reload }
}
