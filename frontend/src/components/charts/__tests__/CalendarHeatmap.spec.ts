import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Stub vue-echarts (no canvas in jsdom); capture the `option` prop for assertions.
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div class="vchart-stub" />' },
}))

import CalendarHeatmap from '../CalendarHeatmap.vue'

const mountChart = (props: Record<string, unknown>) =>
  mount(CalendarHeatmap, { props: props as never })

const optionOf = (w: ReturnType<typeof mountChart>) =>
  w.findComponent({ name: 'VChart' }).props('option') as any

describe('CalendarHeatmap', () => {
  const data: [string, number][] = [
    ['2026-01-01', 3],
    ['2026-01-02', 7],
    ['2026-01-03', 0],
  ]

  it('feeds the data through a calendar heatmap series for the given year', () => {
    const opt = optionOf(mountChart({ data, year: 2026 }))
    expect(opt.calendar.range).toBe(2026)
    expect(opt.series[0].type).toBe('heatmap')
    expect(opt.series[0].coordinateSystem).toBe('calendar')
    expect(opt.series[0].data).toEqual(data)
  })

  it('scales the visualMap max to the largest value', () => {
    const opt = optionOf(mountChart({ data, year: 2026 }))
    expect(opt.visualMap.max).toBe(7)
  })

  it('keeps a visualMap max of at least 1 for all-zero / empty data', () => {
    expect(optionOf(mountChart({ data: [], year: 2026 })).visualMap.max).toBe(1)
    expect(optionOf(mountChart({ data: [['2026-01-01', 0]], year: 2026 })).visualMap.max).toBe(1)
  })

  it('honours a custom colour range when provided', () => {
    const opt = optionOf(mountChart({ data, year: 2026, colorRange: ['#fff', '#000'] }))
    expect(opt.visualMap.inRange.color).toEqual(['#fff', '#000'])
  })
})
