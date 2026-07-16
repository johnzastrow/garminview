import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Mock the API client before importing the component.
vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))
import { api } from '@/api/client'
import TasksPanel from '../TasksPanel.vue'

const get = vi.mocked(api.get)

// RouterLink is used for linked rows; stub it to a plain anchor so no router is needed.
const mountPanel = () =>
  mount(TasksPanel, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })

const syncRow = {
  item_type: 'sync', action_key: null, title: 'Garmin sync', detail: 'activities',
  link: null, count: null, timestamp: '2026-06-15T10:00:00Z', duration_s: 42,
  records_upserted: 1234, status: 'success',
}
const actionRow = {
  item_type: 'action', action_key: 'review', title: 'Review queue', detail: '3 pending',
  link: '/actalog/review', count: 3, timestamp: null, duration_s: null,
  records_upserted: null, status: null,
}

describe('TasksPanel', () => {
  beforeEach(() => get.mockReset())

  it('renders nothing when the feed is empty', async () => {
    get.mockResolvedValueOnce({ data: [] })
    const w = mountPanel()
    await flushPromises()
    expect(w.find('.tasks-panel').exists()).toBe(false)
  })

  it('fetches the task feed with a limit on mount', async () => {
    get.mockResolvedValueOnce({ data: [] })
    mountPanel()
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/admin/tasks', { params: { limit: 10 } })
  })

  it('renders a row per item with its title and detail', async () => {
    get.mockResolvedValueOnce({ data: [syncRow, actionRow] })
    const w = mountPanel()
    await flushPromises()
    const rows = w.findAll('.task-row')
    expect(rows).toHaveLength(2)
    expect(w.text()).toContain('Garmin sync')
    expect(w.text()).toContain('Review queue')
    expect(w.text()).toContain('3 pending')
  })

  it('styles action vs sync rows and their status dots differently', async () => {
    get.mockResolvedValueOnce({ data: [syncRow, actionRow] })
    const w = mountPanel()
    await flushPromises()
    const rows = w.findAll('.task-row')
    expect(rows[0]!.classes()).toContain('task-sync')
    expect(rows[0]!.find('.dot').classes()).toContain('dot-success')
    expect(rows[1]!.classes()).toContain('task-action')
    expect(rows[1]!.find('.dot').classes()).toContain('dot-action')
  })

  it('shows sync metadata (duration + record count) only for sync rows', async () => {
    get.mockResolvedValueOnce({ data: [syncRow, actionRow] })
    const w = mountPanel()
    await flushPromises()
    const rows = w.findAll('.task-row')
    expect(rows[0]!.find('.task-meta').exists()).toBe(true)
    expect(rows[0]!.text()).toContain('1,234 records')
    expect(rows[1]!.find('.task-meta').exists()).toBe(false)
  })

  it('swallows a fetch failure and renders nothing', async () => {
    get.mockRejectedValueOnce(new Error('boom'))
    const w = mountPanel()
    await flushPromises()
    expect(w.find('.tasks-panel').exists()).toBe(false)
  })
})
