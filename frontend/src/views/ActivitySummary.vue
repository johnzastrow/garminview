<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Activity Summary</h1>
        <p class="page-sub">{{ totalActivities }} activities in range</p>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading data…</span>
    </div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard label="Activities" :value="totalActivities" color="#3B82F6" />
        <MetricCard label="Total Distance" :value="totalDistanceMi" unit="mi" color="#10B981" />
        <MetricCard label="Total Calories" :value="totalCalories" unit="kcal" color="#F59E0B" />
        <MetricCard label="Avg HR" :value="avgHR" unit="bpm" color="#E5341D" />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Distance per Activity</h2>
          <p class="chart-desc">Distance of each activity in km. Useful for tracking how your workout lengths vary over time and spotting progression in long-distance sessions. Filter by sport type in the Running dashboard for a more focused view.</p>
          <TimeSeriesChart
            v-if="distanceSeries.length"
            :series="distanceSeries"
            y-axis-label="mi"
          />
          <p v-else class="empty">No activity data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Heart Rate per Activity</h2>
          <p class="chart-desc">Average heart rate for each activity session. Comparing HR across similar activities over time reveals cardiovascular fitness gains — the same effort produces a lower HR as you adapt.</p>
          <TimeSeriesChart
            v-if="hrSeries.length"
            :series="hrSeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No HR data in range.</p>
        </div>
      </div>

      <div class="chart-block activity-table-block">
        <h2 class="chart-title">Recent Activities</h2>
        <p class="chart-desc">Complete log of all activities in the selected period, including sport type, distance, duration, average heart rate, and calorie estimate. Click column headers to sort.</p>
        <table class="activity-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Name</th>
              <th>Sport</th>
              <th>Distance</th>
              <th>Duration</th>
              <th>Avg HR</th>
              <th>Calories</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in activities" :key="a.activity_id">
              <td>{{ formatDate(a.start_time) }}</td>
              <td class="name-cell">{{ a.name || "—" }}</td>
              <td>{{ a.sport || a.type || "—" }}</td>
              <td>{{ a.distance_m ? mToMi(a.distance_m, 1) + " mi" : "—" }}</td>
              <td>{{ formatDuration(a.elapsed_time_s) }}</td>
              <td>{{ a.avg_hr ? a.avg_hr + " bpm" : "—" }}</td>
              <td>{{ a.calories ? a.calories + " kcal" : "—" }}</td>
            </tr>
            <tr v-if="!activities?.length">
              <td colspan="7" class="empty-row">No activities in range.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import dayjs from "dayjs"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import { useMetricData } from "@/composables/useMetricData"
import { mToMi, DIST_UNIT } from "@/utils/units"

interface Activity {
  activity_id: number
  name: string | null
  type: string | null
  sport: string | null
  start_time: string | null
  elapsed_time_s: number | null
  distance_m: number | null
  calories: number | null
  avg_hr: number | null
  training_load: number | null
}

const { data: activities, loading, error } = useMetricData<Activity[]>("/activities/")

// API returns DESC order; reverse for chronological charts
const chronological = computed(() => activities.value ? [...activities.value].reverse() : [])

const totalActivities = computed(() => activities.value?.length ?? 0)
const totalDistanceMi = computed(() => {
  const totalM = activities.value?.reduce((s, a) => s + (a.distance_m ?? 0), 0) ?? 0
  const mi = totalM / 1609.344
  return mi > 0 ? +mi.toFixed(1) : null
})
const totalCalories = computed(() => {
  const c = activities.value?.reduce((s, a) => s + (a.calories ?? 0), 0) ?? 0
  return c > 0 ? c : null
})
const avgHR = computed(() => {
  const withHR = activities.value?.filter((a) => a.avg_hr) ?? []
  if (!withHR.length) return null
  return Math.round(withHR.reduce((s, a) => s + (a.avg_hr ?? 0), 0) / withHR.length)
})

const distanceSeries = computed(() => {
  if (!chronological.value.length) return []
  return [{
    name: "Distance",
    data: chronological.value
      .filter((a) => a.start_time && a.distance_m)
      .map((a) => [a.start_time!.slice(0, 10), mToMi(a.distance_m!, 2)!] as [string, number]),
    color: "#10B981",
  }]
})

const hrSeries = computed(() => {
  if (!chronological.value.length) return []
  return [{
    name: "Avg HR",
    data: chronological.value
      .filter((a) => a.start_time && a.avg_hr)
      .map((a) => [a.start_time!.slice(0, 10), a.avg_hr] as [string, number | null]),
    color: "#E5341D",
  }]
})

function formatDate(ts: string | null) {
  return ts ? dayjs(ts).format("MMM D") : "—"
}

function formatDuration(secs: number | null) {
  if (!secs) return "—"
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); font-weight: 400; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }
.charts { display: flex; flex-direction: column; gap: 16px; }
.chart-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 20px 8px; }
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }
.activity-table-block { padding-bottom: 16px; }
.activity-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.activity-table th { text-align: left; padding: 6px 10px; color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); }
.activity-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text); }
.activity-table tr:last-child td { border-bottom: none; }
.name-cell { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-row { text-align: center; color: var(--muted); padding: 20px; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
