import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import dayjs from 'dayjs'
import { useDateRangeStore } from '../dateRange'

describe('dateRange store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Freeze "now" so date math is deterministic.
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-15T12:00:00Z'))
  })
  afterEach(() => vi.useRealTimers())

  it('defaults to a 90-day window ending today', () => {
    const s = useDateRangeStore()
    expect(s.preset).toBe('90d')
    expect(s.endDate).toBe(dayjs().format('YYYY-MM-DD'))
    expect(s.startDate).toBe(dayjs().subtract(90, 'day').format('YYYY-MM-DD'))
  })

  it.each([
    ['7d', 7],
    ['30d', 30],
    ['90d', 90],
    ['1y', 365],
  ] as const)('setPreset(%s) sets start = today - %i days', (preset, days) => {
    const s = useDateRangeStore()
    s.setPreset(preset)
    expect(s.preset).toBe(preset)
    expect(s.endDate).toBe(dayjs().format('YYYY-MM-DD'))
    expect(s.startDate).toBe(dayjs().subtract(days, 'day').format('YYYY-MM-DD'))
  })

  it('setPreset("custom") refreshes endDate but leaves startDate untouched', () => {
    const s = useDateRangeStore()
    s.setPreset('7d')
    const startBefore = s.startDate
    s.setPreset('custom')
    expect(s.preset).toBe('custom')
    expect(s.startDate).toBe(startBefore) // custom = caller controls start
    expect(s.endDate).toBe(dayjs().format('YYYY-MM-DD'))
  })
})
