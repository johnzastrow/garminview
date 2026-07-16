import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// vue-echarts needs a real <canvas> / ResizeObserver; jsdom has neither. Replace the
// module with a light stub that just records the `option` prop, so we can assert the
// data->option transform without a renderer.
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div class="vchart-stub" />' },
}))

import HrZonesChart from '../HrZonesChart.vue'
import type { HRZonesDay } from '../HrZonesChart.vue'

const findChart = (w: ReturnType<typeof mountChart>) => w.findComponent({ name: 'VChart' })
const mountChart = (data: HRZonesDay[]) => mount(HrZonesChart, { props: { data } })

const day = (over: Partial<HRZonesDay> = {}): HRZonesDay => ({
  date: '2026-06-01', z2_min: 10, z3_min: 5, z4_min: 3, z5_min: 1,
  valid_max_hr: 180, raw_max_hr: 182, rejected_count: 0, total_count: 100, ...over,
})

describe('HrZonesChart', () => {
  it('shows a profile-setup prompt (no chart) when there is no data', () => {
    const w = mountChart([])
    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.find('.empty-state').text()).toContain('Max HR')
    expect(findChart(w).exists()).toBe(false)
  })

  it('renders the chart and drops the empty state once data arrives', () => {
    const w = mountChart([day()])
    expect(w.find('.empty-state').exists()).toBe(false)
    expect(findChart(w).exists()).toBe(true)
  })

  it('builds four stacked zone bars plus two HR lines on a time axis', () => {
    const w = mountChart([day({ date: '2026-06-01' }), day({ date: '2026-06-02' })])
    const opt = findChart(w).props('option') as any
    expect(opt.xAxis.type).toBe('time')
    const types = opt.series.map((s: any) => s.type)
    expect(types.filter((t: string) => t === 'bar')).toHaveLength(4)
    expect(types.filter((t: string) => t === 'line')).toHaveLength(2)
    // Each series carries one [date, value] point per day.
    expect(opt.series[0].data).toHaveLength(2)
    expect(opt.series[0].data[0]).toEqual(['2026-06-01', 10])
  })
})
