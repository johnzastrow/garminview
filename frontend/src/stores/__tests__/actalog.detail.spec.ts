import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock the shared axios client exactly as the existing actalog spec does.
vi.mock('@/api/client', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
import { api } from '@/api/client'
import { useActalogStore } from '../actalog'

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

describe('actalog store — detail fetchers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    post.mockReset()
  })

  it('fetchWorkoutDetail loads a single workout by id', async () => {
    const detail = { id: 7, workout_date: '2026-06-01T00:00:00', movements: [], wods: [] }
    get.mockResolvedValueOnce({ data: detail })
    const s = useActalogStore()
    await s.fetchWorkoutDetail(7)
    expect(get).toHaveBeenCalledWith('/actalog/workouts/7')
    expect(s.selectedWorkout).toEqual(detail)
  })

  it('fetchSessionVitals loads the vitals payload for a workout', async () => {
    const vitals = { workout: { id: 7 }, has_vitals: true, hr_series: [], body_battery: [], stress: [] }
    get.mockResolvedValueOnce({ data: vitals })
    const s = useActalogStore()
    await s.fetchSessionVitals(7)
    expect(get).toHaveBeenCalledWith('/actalog/workouts/7/session-vitals')
    expect(s.sessionVitals).toEqual(vitals)
  })

  it('fetchCrossRef omits empty date params but forwards a provided range', async () => {
    get.mockResolvedValue({ data: [{ workout_date: '2026-06-01' }] })
    const s = useActalogStore()

    await s.fetchCrossRef()
    expect(get).toHaveBeenLastCalledWith('/actalog/cross-reference', { params: {} })

    await s.fetchCrossRef('2026-01-01', '2026-02-01')
    expect(get).toHaveBeenLastCalledWith('/actalog/cross-reference', {
      params: { start: '2026-01-01', end: '2026-02-01' },
    })
    expect(s.crossRef).toEqual([{ workout_date: '2026-06-01' }])
  })

  // Garmin-match API consumed by GarminMatchPanel.vue.
  it('exposes fetchMatchCandidates / setWorkoutMatch actions', () => {
    const s = useActalogStore() as unknown as Record<string, unknown>
    expect(typeof s.fetchMatchCandidates).toBe('function')
    expect(typeof s.setWorkoutMatch).toBe('function')
  })

  it('fetchMatchCandidates GETs the match-candidates endpoint and returns the payload', async () => {
    const payload = {
      workout_date: '2024-01-15T00:00:00',
      current: { status: 'auto', activity: { activity_id: 100 } },
      candidates: [{ activity_id: 100 }, { activity_id: 200 }],
    }
    get.mockResolvedValueOnce({ data: payload })
    const s = useActalogStore()
    const res = await s.fetchMatchCandidates(7)
    expect(get).toHaveBeenCalledWith('/actalog/workouts/7/match-candidates')
    expect(res).toEqual(payload)
  })

  it('setWorkoutMatch POSTs the chosen activity_id and returns the post-update state', async () => {
    const linked = {
      workout_date: '2024-01-15T00:00:00',
      current: { status: 'linked', activity: { activity_id: 200 } },
      candidates: [],
    }
    post.mockResolvedValueOnce({ data: linked })
    const s = useActalogStore()
    const res = await s.setWorkoutMatch(7, 200)
    expect(post).toHaveBeenCalledWith('/actalog/workouts/7/match', { activity_id: 200 })
    expect(res).toEqual(linked)
  })

  it('setWorkoutMatch forwards a null activity_id (confirm no Garmin activity)', async () => {
    const none = {
      workout_date: '2024-01-15T00:00:00',
      current: { status: 'none', activity: null },
      candidates: [],
    }
    post.mockResolvedValueOnce({ data: none })
    const s = useActalogStore()
    await s.setWorkoutMatch(7, null)
    expect(post).toHaveBeenCalledWith('/actalog/workouts/7/match', { activity_id: null })
  })
})
