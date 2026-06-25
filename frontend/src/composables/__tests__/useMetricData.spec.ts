import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

// Mock the axios client the composable imports.
vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))
import { api } from '@/api/client'
import { useMetricData } from '../useMetricData'
import { useDateRangeStore } from '@/stores/dateRange'

const mockGet = vi.mocked(api.get)

describe('useMetricData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockGet.mockReset()
  })

  it('fetches immediately and exposes the payload', async () => {
    mockGet.mockResolvedValueOnce({ data: [{ v: 1 }] })
    const { data, loading, error } = useMetricData<{ v: number }[]>('/metrics/x')
    await flushPromises()
    expect(data.value).toEqual([{ v: 1 }])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('passes the active date range as query params', async () => {
    mockGet.mockResolvedValue({ data: [] })
    const store = useDateRangeStore()
    useMetricData('/nutrition/daily')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/nutrition/daily', {
      params: { start: store.startDate, end: store.endDate },
    })
  })

  it('captures the error message and clears loading on failure', async () => {
    mockGet.mockRejectedValueOnce(new Error('boom'))
    const { data, loading, error } = useMetricData('/metrics/x')
    await flushPromises()
    expect(error.value).toBe('boom')
    expect(data.value).toBeNull()
    expect(loading.value).toBe(false)
  })

  it('refetches when the date range changes', async () => {
    mockGet.mockResolvedValue({ data: [] })
    const store = useDateRangeStore()
    useMetricData('/metrics/x')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(1)
    store.setPreset('7d')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(2)
  })
})
