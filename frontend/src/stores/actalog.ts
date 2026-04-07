import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { api } from "@/api/client"

export interface WorkoutListItem {
  id: number
  workout_date: string | null
  workout_name: string | null
  workout_type: string | null
  total_time_s: number | null
}

export interface MovementItem {
  id: number
  workout_id: number | null
  movement_id: number | null
  sets: number | null
  reps: number | null
  weight_kg: number | null
  time_s: number | null
  rpe: number | null
  is_pr: boolean
  order_index: number | null
}

export interface WodItem {
  id: number
  workout_id: number | null
  wod_id: number | null
  score_value: string | null
  time_s: number | null
  rounds: number | null
  reps: number | null
  weight_kg: number | null
  rpe: number | null
  is_pr: boolean
  order_index: number | null
}

export interface WorkoutDetail extends WorkoutListItem {
  notes: string | null
  movements: MovementItem[]
  wods: WodItem[]
}

export interface SessionVitals {
  workout: WorkoutDetail
  has_vitals: boolean
  hr_series: { ts: string; hr: number }[]
  body_battery: { ts: string; value: number; type: string }[]
  stress: { ts: string; level: number }[]
}

export interface PRItem {
  movement_id: number
  movement_name: string | null
  movement_type: string | null
  max_weight_kg: number | null
  max_reps: number | null
  best_time_s: number | null
  workout_date: string | null
}

export interface CrossRefItem {
  workout_date: string | null
  workout_name: string | null
  workout_type: string | null
  total_volume_kg: number | null
  body_battery_max: number | null
  hr_resting: number | null
  sleep_score: number | null
  stress_avg: number | null
}

export interface ActalogConfig {
  url: string | null
  email: string | null
  has_password: boolean
  weight_unit: string | null
  sync_interval_hours: number | null
  sync_enabled: boolean
  last_sync: string | null
}

export const useActalogStore = defineStore("actalog", () => {
  const workouts = ref<WorkoutListItem[]>([])
  const selectedWorkout = ref<WorkoutDetail | null>(null)
  const sessionVitals = ref<SessionVitals | null>(null)
  const prs = ref<PRItem[]>([])
  const crossRef = ref<CrossRefItem[]>([])
  const config = ref<ActalogConfig | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchWorkouts(start?: string, end?: string) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = {}
      if (start) params.start = start
      if (end) params.end = end
      const { data } = await api.get("/actalog/workouts", { params })
      workouts.value = data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkoutDetail(id: number) {
    const { data } = await api.get(`/actalog/workouts/${id}`)
    selectedWorkout.value = data
  }

  async function fetchSessionVitals(id: number) {
    const { data } = await api.get(`/actalog/workouts/${id}/session-vitals`)
    sessionVitals.value = data
  }

  async function fetchPRs() {
    const { data } = await api.get("/actalog/prs")
    prs.value = data
  }

  async function fetchCrossRef(start?: string, end?: string) {
    const params: Record<string, string> = {}
    if (start) params.start = start
    if (end) params.end = end
    const { data } = await api.get("/actalog/cross-reference", { params })
    crossRef.value = data
  }

  async function fetchConfig() {
    const { data } = await api.get("/admin/actalog/config")
    config.value = data
  }

  async function saveConfig(updates: Partial<ActalogConfig> & { password?: string }) {
    // PUT /admin/actalog/config accepts a JSON body (not query params)
    await api.put("/admin/actalog/config", updates)
    await fetchConfig()
  }

  async function triggerSync() {
    const { data } = await api.post("/admin/actalog/sync")
    return data
  }

  const workoutsByDate = computed(() => {
    const map = new Map<string, WorkoutListItem[]>()
    for (const w of workouts.value) {
      if (!w.workout_date) continue
      const day = w.workout_date.slice(0, 10)
      const existing = map.get(day) ?? []
      existing.push(w)
      map.set(day, existing)
    }
    return map
  })

  return {
    workouts, selectedWorkout, sessionVitals, prs, crossRef, config,
    loading, error, workoutsByDate,
    fetchWorkouts, fetchWorkoutDetail, fetchSessionVitals,
    fetchPRs, fetchCrossRef, fetchConfig, saveConfig, triggerSync,
  }
})
