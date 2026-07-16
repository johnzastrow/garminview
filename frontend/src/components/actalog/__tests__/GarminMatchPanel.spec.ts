import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// The panel talks to the pinia store's fetchMatchCandidates / setWorkoutMatch;
// stub those on the real store instance rather than the api client.
import { useActalogStore } from '@/stores/actalog'
import GarminMatchPanel from '../GarminMatchPanel.vue'

const candidatesPayload = {
  workout_date: '2024-01-15T00:00:00',
  current: {
    status: 'auto',
    activity: {
      activity_id: 100, start_time: '2024-01-15T07:00:00', sport: 'strength_training',
      sub_sport: null, elapsed_time_s: 1790, distance_m: 0, avg_hr: 130, max_hr: 165, calories: 250,
    },
  },
  candidates: [
    {
      activity_id: 100, start_time: '2024-01-15T07:00:00', sport: 'strength_training',
      sub_sport: null, elapsed_time_s: 1790, distance_m: 0, avg_hr: 130, max_hr: 165, calories: 250,
    },
    {
      activity_id: 200, start_time: '2024-01-15T18:00:00', sport: 'walking',
      sub_sport: null, elapsed_time_s: 600, distance_m: 800, avg_hr: 95, max_hr: 110, calories: 60,
    },
  ],
}

const linkedPayload = {
  workout_date: '2024-01-15T00:00:00',
  current: { status: 'linked', activity: candidatesPayload.candidates[1] },
  candidates: candidatesPayload.candidates,
}

describe('GarminMatchPanel', () => {
  let store: ReturnType<typeof useActalogStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useActalogStore()
    store.fetchMatchCandidates = vi.fn().mockResolvedValue(candidatesPayload)
    store.setWorkoutMatch = vi.fn().mockResolvedValue(linkedPayload)
  })

  it('renders the status chip from the loaded match state', async () => {
    const w = mount(GarminMatchPanel, { props: { workoutId: 1 } })
    await flushPromises()
    expect(store.fetchMatchCandidates).toHaveBeenCalledWith(1)
    const chip = w.find('.match-chip')
    expect(chip.exists()).toBe(true)
    expect(chip.classes()).toContain('match-chip-auto')
    expect(chip.text()).toContain('Auto-matched')
  })

  it('shows the candidate table when expanded', async () => {
    const w = mount(GarminMatchPanel, { props: { workoutId: 1 } })
    await flushPromises()
    expect(w.find('.match-table').exists()).toBe(false)
    await w.find('.match-action').trigger('click')
    expect(w.find('.match-table').exists()).toBe(true)
    expect(w.findAll('.match-table tbody tr')).toHaveLength(2)
  })

  it('sets the match and emits "changed" after picking a candidate', async () => {
    const w = mount(GarminMatchPanel, { props: { workoutId: 1 } })
    await flushPromises()
    await w.find('.match-action').trigger('click')
    // Second row = activity 200; pick it.
    const pickButtons = w.findAll('.btn-pick')
    await pickButtons[1]!.trigger('click')
    await flushPromises()
    expect(store.setWorkoutMatch).toHaveBeenCalledWith(1, 200)
    expect(w.emitted('changed')).toBeTruthy()
  })

  it('confirms "no Garmin activity" via the None button (null id)', async () => {
    const w = mount(GarminMatchPanel, { props: { workoutId: 1 } })
    await flushPromises()
    await w.find('.match-action').trigger('click')
    await w.find('.btn-none').trigger('click')
    await flushPromises()
    expect(store.setWorkoutMatch).toHaveBeenCalledWith(1, null)
    expect(w.emitted('changed')).toBeTruthy()
  })
})
