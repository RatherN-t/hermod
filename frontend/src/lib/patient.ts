/** Small display helpers for patient records from the API. */

export function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] ?? fullName
}

export function initials(fullName: string): string {
  const words = fullName.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  const first = words[0][0]
  const last = words.length > 1 ? words[words.length - 1][0] : ''
  return `${first}${last}`.toUpperCase()
}

const LANGUAGES: Record<string, string> = { en: 'English', es: 'Spanish' }

export function languageLabel(code: string): string {
  return LANGUAGES[code] ?? code
}
