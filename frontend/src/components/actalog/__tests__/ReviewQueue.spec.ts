import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Mock the API client. Route by URL so both the queue and the status/count call resolve.
vi.mock('@/api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
import { api } from '@/api/client'
import ReviewQueue from '../ReviewQueue.vue'

const get = vi.mocked(api.get)

const makeItem = (over: Record<string, unknown> = {}) => ({
  id: 1, workout_id: 10, workout_name: 'Fran', workout_date: '2026-06-01T00:00:00',
  content_class: 'WORKOUT', parse_status: 'pending', parsed_at: null, reviewed_at: null,
  error_message: null, llm_model: 'llama3', raw_notes: '21-15-9', formatted_markdown: '# Fran',
  parsed_json: null, parse_duration_s: null, llm_tokens_prompt: null, llm_tokens_generated: null,
  llm_inference_s: null, performance_notes: null, ...over,
})

// Resolve queue + status endpoints; queue items are configured per-test.
function stubApi(items: unknown[], staged = items.length) {
  get.mockImplementation((url?: string) => {
    if (String(url).includes('/parser/status')) {
      return Promise.resolve({ data: { total_staged: staged, running: false } })
    }
    return Promise.resolve({ data: { items } })
  })
}

describe('ReviewQueue', () => {
  beforeEach(() => get.mockReset())

  it('renders the empty state when no items are pending', async () => {
    stubApi([], 0)
    const w = mount(ReviewQueue)
    await flushPromises()
    expect(w.find('.empty').exists()).toBe(true)
    expect(w.find('.empty').text()).toContain('No pending reviews found')
    expect(w.find('.review-table').exists()).toBe(false)
  })

  it('fetches the queue with the default pending filter on mount', async () => {
    stubApi([])
    mount(ReviewQueue)
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/admin/actalog/parser/queue', {
      params: { order: 'desc', status: 'pending' },
    })
  })

  it('renders one table row per queue item', async () => {
    stubApi([makeItem({ id: 1, workout_name: 'Fran' }), makeItem({ id: 2, workout_name: 'Grace' })])
    const w = mount(ReviewQueue)
    await flushPromises()
    const rows = w.findAll('.review-row')
    expect(rows).toHaveLength(2)
    expect(w.text()).toContain('Fran')
    expect(w.text()).toContain('Grace')
  })

  it('shows the pending badge with the staged count', async () => {
    stubApi([makeItem()], 5)
    const w = mount(ReviewQueue)
    await flushPromises()
    expect(w.find('.pending-badge').text()).toBe('5 pending')
  })

  it('opens the detail panel with action buttons when a row is clicked', async () => {
    stubApi([makeItem({ workout_name: 'Cindy' })])
    const w = mount(ReviewQueue)
    await flushPromises()
    expect(w.find('.detail-panel').exists()).toBe(false)
    await w.find('.review-row').trigger('click')
    expect(w.find('.detail-panel').exists()).toBe(true)
    expect(w.find('.detail-header').text()).toContain('Cindy')
    // Pending items expose approve / reject affordances.
    expect(w.find('.btn-success').text()).toContain('Approve')
    expect(w.find('.btn-danger').text()).toContain('Reject')
  })

  it('refetches with the chosen status when the filter changes', async () => {
    stubApi([])
    const w = mount(ReviewQueue)
    await flushPromises()
    get.mockClear()
    await w.find('.filter-select').setValue('approved')
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/admin/actalog/parser/queue', {
      params: { order: 'desc', status: 'approved' },
    })
  })
})
