export function fieldDescribedBy(id: string, opts: { helper?: boolean; error?: string | null }) {
  const ids = [opts.helper ? `${id}-helper` : null, opts.error ? `${id}-error` : null].filter(Boolean)
  return ids.length ? ids.join(' ') : undefined
}
