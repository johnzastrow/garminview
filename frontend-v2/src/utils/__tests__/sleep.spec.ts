import { describe, it, expect } from "vitest"
import { normalizeNights, rollingMean, mean, stageShare, fmtHM, scoreBand, lastRecorded, type SleepRow } from "../sleep"

const row = (date: string, total: number, score: number | null = 80): SleepRow => ({
  date,
  total_sleep_min: total,
  deep_sleep_min: total ? 90 : 0,
  light_sleep_min: total ? 250 : 0,
  rem_sleep_min: total ? 100 : 0,
  awake_min: total ? 10 : 0,
  score,
})

describe("normalizeNights", () => {
  it("turns a zero-minute night into a missing night", () => {
    const [n] = normalizeNights([row("2026-11-15", 0, null)])
    expect(n).toEqual({ date: "2026-11-15", total: null, deep: null, light: null, rem: null, awake: null, score: null })
  })
  it("keeps real nights unchanged", () => {
    const [n] = normalizeNights([row("2026-11-16", 440, 81)])
    expect(n!.total).toBe(440)
    expect(n!.deep).toBe(90)
    expect(n!.score).toBe(81)
  })
})

describe("rollingMean", () => {
  it("averages the trailing window and skips nulls", () => {
    expect(rollingMean([1, 2, 3, 4], 2, 1)).toEqual([1, 1.5, 2.5, 3.5])
    expect(rollingMean([2, null, 4], 3, 1)).toEqual([2, 2, 3])
  })
  it("returns null when the window has too few real values", () => {
    expect(rollingMean([null, null, 5, null], 3, 2)).toEqual([null, null, null, null])
  })
})

describe("small helpers", () => {
  it("mean ignores nulls and returns null for no data", () => {
    expect(mean([2, null, 4])).toBe(3)
    expect(mean([null])).toBeNull()
  })
  it("stageShare needs both parts", () => {
    expect(stageShare(90, 450)).toBe(20)
    expect(stageShare(null, 450)).toBeNull()
    expect(stageShare(90, 0)).toBeNull()
  })
  it("fmtHM pads minutes", () => {
    expect(fmtHM(450)).toBe("7 h 30 m")
    expect(fmtHM(65)).toBe("1 h 05 m")
    expect(fmtHM(null)).toBe("--")
  })
  it("scoreBand uses Garmin bands", () => {
    expect([95, 85, 70, 50, null].map(scoreBand)).toEqual(["excellent", "good", "fair", "poor", null])
  })
  it("lastRecorded skips trailing missing nights", () => {
    const n = normalizeNights([row("2026-11-20", 410), row("2026-11-21", 0, null)])
    expect(lastRecorded(n)!.date).toBe("2026-11-20")
  })
})
