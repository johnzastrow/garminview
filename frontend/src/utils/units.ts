// Imperial unit conversion utilities
// All source data from the backend is metric (SI). These helpers convert for display only.

const KM_PER_MILE = 1.60934
const LBS_PER_KG = 2.20462
const FT_PER_M = 3.28084

/** Metres → miles (rounded to dp decimal places) */
export function mToMi(m: number | null | undefined, dp = 2): number | null {
  if (m == null) return null
  return +((m / 1000) / KM_PER_MILE).toFixed(dp)
}

/** km → miles */
export function kmToMi(km: number | null | undefined, dp = 2): number | null {
  if (km == null) return null
  return +(km / KM_PER_MILE).toFixed(dp)
}

/** kg → lbs */
export function kgToLbs(kg: number | null | undefined, dp = 1): number | null {
  if (kg == null) return null
  return +(kg * LBS_PER_KG).toFixed(dp)
}

/** Metres → feet */
export function mToFt(m: number | null | undefined, dp = 0): number | null {
  if (m == null) return null
  return +(m * FT_PER_M).toFixed(dp)
}

/** Pace min/km → min/mile (returns decimal minutes) */
export function paceKmToMi(minPerKm: number | null | undefined, dp = 2): number | null {
  if (minPerKm == null) return null
  return +(minPerKm * KM_PER_MILE).toFixed(dp)
}

/** Speed m/s → mph */
export function msToMph(ms: number | null | undefined, dp = 1): number | null {
  if (ms == null) return null
  return +(ms * 2.23694).toFixed(dp)
}

/** Format decimal minutes as "M:SS" string, e.g. 9.25 → "9:15" */
export function fmtPace(minDecimal: number | null | undefined): string {
  if (minDecimal == null) return '—'
  const m = Math.floor(minDecimal)
  const s = Math.round((minDecimal - m) * 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// Unit label strings
export const DIST_UNIT = 'mi'
export const WEIGHT_UNIT = 'lbs'
export const ELEV_UNIT = 'ft'
export const PACE_UNIT = 'min/mi'
export const SPEED_UNIT = 'mph'
