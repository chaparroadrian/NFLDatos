const NO_DATA = 'sin datos'

type NumericValue = number | null | undefined

function isFiniteNumber(value: NumericValue): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Formats a rate in the API's 0–1 scale as a percentage. */
export function pct(value: NumericValue): string {
  return isFiniteNumber(value) ? `${(value * 100).toFixed(1)}%` : NO_DATA
}

/** Formats a duration in seconds with one decimal place. */
export function secs(value: NumericValue): string {
  return isFiniteNumber(value) ? `${value.toFixed(1)} s` : NO_DATA
}

/** Formats a finite numeric value with one decimal place. */
export function dec1(value: NumericValue): string {
  return isFiniteNumber(value) ? value.toFixed(1) : NO_DATA
}

/** Formats a count as an integer. API counts are expected to be integral. */
export function int(value: NumericValue): string {
  return isFiniteNumber(value) ? value.toFixed(0) : NO_DATA
}

export const formatPercentage = pct
export const formatSeconds = secs
export const formatDecimal = dec1
export const formatInteger = int
