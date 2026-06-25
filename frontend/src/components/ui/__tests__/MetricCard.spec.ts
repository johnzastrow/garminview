import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from '../MetricCard.vue'

// RouterLink is only rendered when linkTo is set; stub it so we don't need a router.
const mountCard = (props: Record<string, unknown>) =>
  mount(MetricCard, { props: props as never, global: { stubs: { RouterLink: true } } })

describe('MetricCard', () => {
  it('renders the label and unit', () => {
    const w = mountCard({ label: 'Resting HR', value: 52, unit: 'bpm' })
    expect(w.find('.label').text()).toBe('Resting HR')
    expect(w.find('.unit').text()).toBe('bpm')
  })

  it('shows an em-dash when value is null or undefined', () => {
    expect(mountCard({ label: 'x', value: null }).find('.value').text()).toBe('—')
    expect(mountCard({ label: 'x', value: undefined }).find('.value').text()).toBe('—')
  })

  it('renders a numeric value', () => {
    expect(mountCard({ label: 'Steps', value: 42 }).find('.value').text()).toBe('42')
  })

  it('renders a delta with an explicit sign and the unit', () => {
    const up = mountCard({ label: 'x', value: 10, unit: 'kg', delta: 3 })
    expect(up.find('.delta').text()).toContain('+3')
    const down = mountCard({ label: 'x', value: 10, unit: 'kg', delta: -2 })
    expect(down.find('.delta').text()).toContain('-2')
  })

  it('omits the delta element when delta is undefined', () => {
    expect(mountCard({ label: 'x', value: 1 }).find('.delta').exists()).toBe(false)
  })

  it('draws a sparkline only when given more than one point', () => {
    expect(mountCard({ label: 'x', value: 1, sparkData: [1, 2, 3] }).find('.sparkline').exists()).toBe(true)
    expect(mountCard({ label: 'x', value: 1, sparkData: [1] }).find('.sparkline').exists()).toBe(false)
    expect(mountCard({ label: 'x', value: 1 }).find('.sparkline').exists()).toBe(false)
  })
})
