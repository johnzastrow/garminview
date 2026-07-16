import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Stub vue-echarts (no canvas in jsdom); capture the `option` prop for assertions.
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div class="vchart-stub" />' },
}))

import TimeSeriesChart from '../TimeSeriesChart.vue'

const mountChart = (props: Record<string, unknown>) =>
  mount(TimeSeriesChart, { props: props as never })

const optionOf = (w: ReturnType<typeof mountChart>) =>
  w.findComponent({ name: 'VChart' }).props('option') as any

describe('TimeSeriesChart', () => {
  it('renders a time-axis line series per input series', () => {
    const opt = optionOf(mountChart({
      series: [{ name: 'Weight', data: [['2026-06-01', 80], ['2026-06-02', 81]], color: '#00f' }],
      yAxisLabel: 'kg',
    }))
    expect(opt.xAxis.type).toBe('time')
    expect(opt.series).toHaveLength(1)
    expect(opt.series[0]).toMatchObject({ name: 'Weight', type: 'line', symbol: 'none' })
    expect(opt.yAxis.name).toBe('kg')
  })

  it('hides the legend for a single series and shows it for several', () => {
    const single = optionOf(mountChart({ series: [{ name: 'A', data: [['2026-06-01', 1]] }] }))
    expect(single.legend).toEqual({ show: false })

    const multi = optionOf(mountChart({
      series: [
        { name: 'A', data: [['2026-06-01', 1]] },
        { name: 'B', data: [['2026-06-01', 2]] },
      ],
    }))
    expect(multi.legend.data).toEqual(['A', 'B'])
  })

  it('adds a fill area only when a single coloured series is plotted', () => {
    const filled = optionOf(mountChart({ series: [{ name: 'A', data: [['2026-06-01', 1]], color: '#0a0' }] }))
    expect(filled.series[0].areaStyle).toBeDefined()

    const multi = optionOf(mountChart({
      series: [
        { name: 'A', data: [['2026-06-01', 1]], color: '#0a0' },
        { name: 'B', data: [['2026-06-01', 2]], color: '#a00' },
      ],
    }))
    expect(multi.series[0].areaStyle).toBeUndefined()
  })

  it('clamps the y-axis minimum to 0 when values sit near zero', () => {
    const opt = optionOf(mountChart({
      series: [{ name: 'Steps', data: [['2026-06-01', 100], ['2026-06-02', 200]] }],
    }))
    expect(opt.yAxis.min).toBe(0)
  })

  it('leaves the y-axis minimum undefined when there are no numeric values', () => {
    const opt = optionOf(mountChart({ series: [{ name: 'x', data: [['2026-06-01', null]] }] }))
    expect(opt.yAxis.min).toBeUndefined()
  })
})
