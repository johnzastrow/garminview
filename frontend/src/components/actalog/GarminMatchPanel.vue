<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { useActalogStore } from "@/stores/actalog"
import type { MatchCandidatesResponse, GarminActivityMatch, MatchStatus } from "@/stores/actalog"

const props = defineProps<{ workoutId: number | null }>()
const emit = defineEmits<{ (e: "changed"): void }>()

const store = useActalogStore()

const data = ref<MatchCandidatesResponse | null>(null)
const expanded = ref(false)
const busy = ref(false)
const error = ref<string | null>(null)

async function load() {
  if (props.workoutId == null) {
    data.value = null
    return
  }
  try {
    error.value = null
    data.value = await store.fetchMatchCandidates(props.workoutId)
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? "Failed to load candidates"
  }
}

watch(() => props.workoutId, load, { immediate: true })

async function selectActivity(activityId: number | null) {
  if (props.workoutId == null) return
  busy.value = true
  try {
    error.value = null
    data.value = await store.setWorkoutMatch(props.workoutId, activityId)
    expanded.value = false
    emit("changed")
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? e?.message ?? "Failed to set match"
  } finally {
    busy.value = false
  }
}

const status = computed<MatchStatus | null>(() => data.value?.current.status ?? null)
const currentActivity = computed<GarminActivityMatch | null>(() => data.value?.current.activity ?? null)

const statusLabel = computed(() => {
  switch (status.value) {
    case "linked":      return "Linked to Garmin activity"
    case "none":        return "No Garmin activity for this workout"
    case "auto":        return "Auto-matched (not yet confirmed)"
    case "ambiguous":   return "Multiple activities — pick one"
    case "unavailable": return "No Garmin activities on this date"
    default:            return ""
  }
})

const statusClass = computed(() => `match-chip match-chip-${status.value ?? 'unknown'}`)

function fmtTime(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function fmtDuration(s: number | null): string {
  if (s == null) return ""
  const m = Math.round(s / 60)
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)}h ${m % 60}m`
}

function summarize(a: GarminActivityMatch): string {
  const parts: string[] = []
  if (a.start_time) parts.push(fmtTime(a.start_time))
  if (a.sport) parts.push(a.sport)
  if (a.elapsed_time_s) parts.push(fmtDuration(a.elapsed_time_s))
  if (a.avg_hr) parts.push(`avg HR ${a.avg_hr}`)
  return parts.join(" · ")
}
</script>

<template>
  <div class="garmin-match">
    <div class="match-row">
      <span :class="statusClass">{{ statusLabel }}</span>
      <span v-if="currentActivity" class="match-summary">
        {{ summarize(currentActivity) }}
      </span>
      <button
        v-if="data"
        class="match-action"
        :disabled="busy"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'Close' : (status === 'linked' || status === 'none' ? 'Change' : 'Pick activity') }}
      </button>
    </div>

    <div v-if="error" class="match-error">{{ error }}</div>

    <!-- Candidate picker -->
    <div v-if="expanded && data" class="match-picker">
      <p v-if="!data.candidates.length" class="muted">
        No Garmin activities found on
        {{ data.workout_date ? data.workout_date.slice(0, 10) : 'this date' }}.
      </p>

      <table v-else class="match-table">
        <thead>
          <tr>
            <th>Start</th>
            <th>Sport</th>
            <th>Duration</th>
            <th>Distance</th>
            <th>Avg HR</th>
            <th>Max HR</th>
            <th>Cal</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in data.candidates"
            :key="c.activity_id"
            :class="{ 'current-match': currentActivity?.activity_id === c.activity_id }"
          >
            <td>{{ fmtTime(c.start_time) }}</td>
            <td>{{ c.sport ?? '—' }}<span v-if="c.sub_sport"> / {{ c.sub_sport }}</span></td>
            <td>{{ fmtDuration(c.elapsed_time_s) }}</td>
            <td>{{ c.distance_m && c.distance_m > 0 ? (c.distance_m / 1000).toFixed(2) + ' km' : '—' }}</td>
            <td>{{ c.avg_hr ?? '—' }}</td>
            <td>{{ c.max_hr ?? '—' }}</td>
            <td>{{ c.calories ?? '—' }}</td>
            <td>
              <button
                class="btn-pick"
                :disabled="busy"
                @click="selectActivity(c.activity_id)"
              >
                {{ currentActivity?.activity_id === c.activity_id ? 'Current' : 'Use this' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="match-footer">
        <button
          class="btn-none"
          :disabled="busy"
          @click="selectActivity(null)"
        >
          None of these &mdash; no Garmin activity for this workout
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.garmin-match {
  margin: 12px 0;
  padding: 10px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.match-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.match-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 0.78rem;
  font-weight: 600;
}
.match-chip-linked      { background: #dcfce7; color: #15803d; }
.match-chip-auto        { background: #fef9c3; color: #854d0e; }
.match-chip-ambiguous   { background: #fed7aa; color: #9a3412; }
.match-chip-none        { background: #e5e7eb; color: #6b7280; }
.match-chip-unavailable { background: #e5e7eb; color: #6b7280; }

.match-summary {
  font-size: 0.85rem;
  color: var(--text);
}

.match-action {
  margin-left: auto;
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 0.82rem;
}
.match-action:hover { border-color: var(--accent); }
.match-action:disabled { opacity: 0.5; cursor: wait; }

.match-error {
  margin-top: 8px;
  padding: 6px 10px;
  background: #fee2e2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #991b1b;
  font-size: 0.82rem;
}

.match-picker {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}

.match-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.match-table th {
  text-align: left;
  padding: 5px 8px;
  color: var(--muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
}
.match-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.match-table tr.current-match {
  background: #ecfccb;
}

.btn-pick {
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 0.78rem;
}
.btn-pick:hover:not(:disabled) { border-color: var(--accent); background: var(--accent-light); }
.btn-pick:disabled { opacity: 0.5; cursor: wait; }

.match-footer {
  margin-top: 10px;
  text-align: right;
}
.btn-none {
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
}
.btn-none:hover:not(:disabled) { border-color: #ef4444; color: #ef4444; }
.btn-none:disabled { opacity: 0.5; cursor: wait; }

.muted { color: var(--muted); font-size: 0.85rem; }
</style>
