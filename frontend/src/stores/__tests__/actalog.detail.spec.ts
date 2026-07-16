import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock the shared axios client exactly as the existing actalog spec does.
vi.mock('@/api/client', () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
import { api } from '@/api/client'
import { useActalogStore } from '../actalog'

const get = vi.mocked(api.get)

describe('actalog store — detail fetchers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
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

  // Regression guard for the Garmin-match gap: GarminMatchPanel.vue (a work-in-progress
  // component not yet on main) imports MatchCandidatesResponse / GarminActivityMatch /
  // MatchStatus and calls store.fetchMatchCandidates / store.setWorkoutMatch, none of which
  // this store exposes. Documented here rather than papered over. See the task report.
  it('does NOT yet expose the Garmin-match API expected by GarminMatchPanel.vue', () => {
    const s = useActalogStore() as Record<string, unknown>
    expect(s.fetchMatchCandidates).toBeUndefined()
    expect(s.setWorkoutMatch).toBeUndefined()
  })
})
