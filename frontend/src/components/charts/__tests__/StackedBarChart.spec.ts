import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Stub vue-echarts (no canvas in jsdom); capture the `option` prop for assertions.
vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', props: ['option'], template: '<div class="vchart-stub" />' },
}))

import StackedBarChart from '../StackedBarChart.vue'

const mountChart = (props: Record<string, unknown>) =>
  mount(StackedBarChart, { props: props as never })

const optionOf = (w: ReturnType<typeof mountChart>) =>
  w.findComponent({ name: 'VChart' }).props('option') as any

describe('StackedBarChart', () => {
  const base = {
    categories: ['Mon', 'Tue', 'Wed'],
    series: [
      { name: 'Run', data: [1, 2, 3], color: '#f00' },
      { name: 'Bike', data: [4, 5, 6] },
    ],
    yAxisLabel: 'min',
  }

  it('maps categories onto a category x-axis', () => {
    const opt = optionOf(mountChart(base))
    expect(opt.xAxis.type).toBe('category')
    expect(opt.xAxis.data).toEqual(['Mon', 'Tue', 'Wed'])
    expect(opt.yAxis.name).toBe('min')
  })

  it('emits one stacked bar series per input series, preserving colour', () => {
    const opt = optionOf(mountChart(base))
    expect(opt.series).toHaveLength(2)
    expect(opt.series.every((s: any) => s.type === 'bar' && s.stack === 'total')).toBe(true)
    expect(opt.series[0]).toMatchObject({ name: 'Run', data: [1, 2, 3], itemStyle: { color: '#f00' } })
    // No colour supplied -> itemStyle left undefined.
    expect(opt.series[1].itemStyle).toBeUndefined()
    expect(opt.legend.data).toEqual(['Run', 'Bike'])
  })

  it('attaches a reference markLine to the last series only when markLine is set', () => {
    const without = optionOf(mountChart(base))
    expect(without.series.some((s: any) => s.markLine)).toBe(false)

    const withLine = optionOf(mountChart({ ...base, markLine: 150 }))
    expect(withLine.series[0].markLine).toBeUndefined()
    expect(withLine.series[1].markLine).toBeDefined()
    expect(withLine.series[1].markLine.data[0]).toEqual({ yAxis: 150 })
  })
})
