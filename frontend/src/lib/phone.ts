/**
 * Phone numbers. The API stores digits only in international form without "+"
 * (e.g. "61491570156"). The clinic is in Australia, so local mobiles are typed and shown
 * as "0491 570 156".
 */

/** "0491 570 156" or "+61 491 570 156" → "61491570156". Other formats keep their digits. */
export function toApiPhone(input: string): string {
  const digits = input.replace(/\D/g, '')
  if (/^04\d{8}$/.test(digits)) return `61${digits.slice(1)}`
  return digits
}

/** True for an Australian mobile, or any international number with 8–15 digits. */
export function isValidPhone(input: string): boolean {
  const trimmed = input.trim()
  const digits = trimmed.replace(/\D/g, '')
  if (/^04\d{8}$/.test(digits) || /^614\d{8}$/.test(digits)) return true
  return trimmed.startsWith('+') && digits.length >= 8 && digits.length <= 15
}

/** "61491570156" → "0491 570 156"; anything else → "+<digits>". */
export function formatPhone(apiPhone: string): string {
  const m = /^614(\d{2})(\d{3})(\d{3})$/.exec(apiPhone)
  if (m) return `04${m[1]} ${m[2]} ${m[3]}`
  return apiPhone ? `+${apiPhone}` : ''
}

/** Opens the device's SMS app with the message filled in, addressed to the patient. */
export function smsHref(apiPhone: string, body: string): string {
  // "?&body=" works on both iOS and Android.
  return `sms:+${apiPhone}?&body=${encodeURIComponent(body)}`
}
