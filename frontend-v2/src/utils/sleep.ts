// Pure helpers for the Sleep view. No Vue, no DOM, so they are unit-tested directly.

export interface SleepRow {
  date: string
  total_sleep_min: number | null
  deep_sleep_min: number | null
  light_sleep_min: number | null
  rem_sleep_min: number | null
  awake_min: number | null
  score: number | null
}

/** A night with its fields normalized: null means "no recording". */
export interface Night {
  date: string
  total: number | null
  deep: number | null
  light: number | null
  rem: number | null
  awake: number | null
  score: number | null
}

/**
 * The API reports nights without a recording (watch off, not worn) as 0 minutes rather
 * than null. Zero sleep is not a real measurement, so it becomes null for every field.
 */
export function normalizeNights(rows: SleepRow[]): Night[] {
  return rows.map((r) => {
    const missing = !r.total_sleep_min
    const f = (v: number | null) => (missing || v == null ? null : v)
    return {
      date: r.date,
      total: missing ? null : r.total_sleep_min,
      deep: f(r.deep_sleep_min),
      light: f(r.light_sleep_min),
      rem: f(r.rem_sleep_min),
      awake: f(r.awake_min),
      score: missing ? null : r.score,
    }
  })
}

/**
 * Trailing rolling mean over `window` entries, ignoring nulls.
 * Returns null where fewer than `minCount` real values fall in the window,
 * so a run of missing nights shows as a gap instead of a stale average.
 */
export function rollingMean(values: (number | null)[], window = 7, minCount = 4): (number | null)[] {
  return values.map((_, i) => {
    const slice = values.slice(Math.max(0, i - window + 1), i + 1).filter((v): v is number => v != null)
    if (slice.length < minCount) return null
    return slice.reduce((a, b) => a + b, 0) / slice.length
  })
}

export function mean(values: (number | null)[]): number | null {
  const v = values.filter((x): x is number => x != null)
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
}

/** Share of the night in a stage, 0-100. Null when either part is missing. */
export function stageShare(stage: number | null, total: number | null): number | null {
  if (stage == null || !total) return null
  return (stage / total) * 100
}

/** Minutes as "7 h 30 m". */
export function fmtHM(min: number | null | undefined): string {
  if (min == null) return "--"
  const m = Math.round(min)
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} m`
}

/** Garmin sleep score bands. */
export function scoreBand(score: number | null): "excellent" | "good" | "fair" | "poor" | null {
  if (score == null) return null
  if (score >= 90) return "excellent"
  if (score >= 80) return "good"
  if (score >= 60) return "fair"
  return "poor"
}

/** Latest night that has a recording. */
export function lastRecorded(nights: Night[]): Night | null {
  for (let i = nights.length - 1; i >= 0; i--) if (nights[i]!.total != null) return nights[i]!
  return null
}
