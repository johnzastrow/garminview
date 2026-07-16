import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DateRangePicker from '../DateRangePicker.vue'
import { useDateRangeStore } from '@/stores/dateRange'

const mountPicker = () => mount(DateRangePicker)

describe('DateRangePicker', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders one pill per preset', () => {
    const w = mountPicker()
    const pills = w.findAll('.pill')
    expect(pills).toHaveLength(5)
    expect(pills.map((p) => p.text())).toEqual(['7 days', '30 days', '90 days', '1 year', 'Custom'])
  })

  it('marks the store default (90d) active and hides the custom date inputs', () => {
    const w = mountPicker()
    const active = w.findAll('.pill').filter((p) => p.classes().includes('active'))
    expect(active).toHaveLength(1)
    expect(active[0]!.text()).toBe('90 days')
    expect(w.find('input[type="date"]').exists()).toBe(false)
  })

  it('clicking a preset pill drives the store and moves the active highlight', async () => {
    const w = mountPicker()
    const store = useDateRangeStore()
    await w.findAll('.pill')[0]!.trigger('click') // "7 days"
    expect(store.preset).toBe('7d')
    const active = w.findAll('.pill').filter((p) => p.classes().includes('active'))
    expect(active).toHaveLength(1)
    expect(active[0]!.text()).toBe('7 days')
  })

  it('selecting Custom reveals two bound date inputs', async () => {
    const w = mountPicker()
    const store = useDateRangeStore()
    await w.findAll('.pill')[4]!.trigger('click') // "Custom"
    expect(store.preset).toBe('custom')
    const dates = w.findAll('input[type="date"]')
    expect(dates).toHaveLength(2)
    expect((dates[0]!.element as HTMLInputElement).value).toBe(store.startDate)
    expect((dates[1]!.element as HTMLInputElement).value).toBe(store.endDate)
  })
})
