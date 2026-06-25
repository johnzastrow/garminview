import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
import { api } from '@/api/client'
import { useActalogStore } from '../actalog'

const get = vi.mocked(api.get)
const put = vi.mocked(api.put)
const post = vi.mocked(api.post)

describe('actalog store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset(); put.mockReset(); post.mockReset()
  })

  it('fetchWorkouts loads workouts and toggles loading', async () => {
    const rows = [{ id: 1, workout_date: '2026-06-01T00:00:00' }]
    get.mockResolvedValueOnce({ data: rows })
    const s = useActalogStore()
    const p = s.fetchWorkouts()
    expect(s.loading).toBe(true)
    await p
    expect(s.workouts).toEqual(rows)
    expect(s.loading).toBe(false)
    expect(s.error).toBeNull()
  })

  it('fetchWorkouts only sends start/end params when provided', async () => {
    get.mockResolvedValue({ data: [] })
    const s = useActalogStore()
    await s.fetchWorkouts()
    expect(get).toHaveBeenLastCalledWith('/actalog/workouts', { params: {} })
    await s.fetchWorkouts('2026-01-01', '2026-02-01')
    expect(get).toHaveBeenLastCalledWith('/actalog/workouts', {
      params: { start: '2026-01-01', end: '2026-02-01' },
    })
  })

  it('fetchWorkouts records the error message and stops loading on failure', async () => {
    get.mockRejectedValueOnce(new Error('network down'))
    const s = useActalogStore()
    await s.fetchWorkouts()
    expect(s.error).toBe('network down')
    expect(s.loading).toBe(false)
  })

  it('fetchPRs and fetchConfig populate their state', async () => {
    const s = useActalogStore()
    get.mockResolvedValueOnce({ data: [{ id: 9 }] })
    await s.fetchPRs()
    expect(s.prs).toEqual([{ id: 9 }])
    get.mockResolvedValueOnce({ data: { sync_enabled: true } })
    await s.fetchConfig()
    expect(s.config).toEqual({ sync_enabled: true })
  })

  it('saveConfig PUTs the body then refetches config', async () => {
    put.mockResolvedValueOnce({ data: {} })
    get.mockResolvedValueOnce({ data: { sync_enabled: false } })
    const s = useActalogStore()
    await s.saveConfig({ sync_enabled: false, password: 'secret' })
    expect(put).toHaveBeenCalledWith('/admin/actalog/config', { sync_enabled: false, password: 'secret' })
    expect(get).toHaveBeenCalledWith('/admin/actalog/config')
    expect(s.config).toEqual({ sync_enabled: false })
  })

  it('triggerSync POSTs and returns the response payload', async () => {
    post.mockResolvedValueOnce({ data: { started: true } })
    const s = useActalogStore()
    await expect(s.triggerSync()).resolves.toEqual({ started: true })
    expect(post).toHaveBeenCalledWith('/admin/actalog/sync')
  })

  it('workoutsByDate groups by calendar day and skips dateless rows', async () => {
    get.mockResolvedValueOnce({
      data: [
        { id: 1, workout_date: '2026-06-01T07:00:00' },
        { id: 2, workout_date: '2026-06-01T18:00:00' },
        { id: 3, workout_date: '2026-06-02T07:00:00' },
        { id: 4, workout_date: null },
      ],
    })
    const s = useActalogStore()
    await s.fetchWorkouts()
    const map = s.workoutsByDate
    expect(map.get('2026-06-01')).toHaveLength(2)
    expect(map.get('2026-06-02')).toHaveLength(1)
    expect([...map.keys()]).toEqual(['2026-06-01', '2026-06-02'])
  })
})
