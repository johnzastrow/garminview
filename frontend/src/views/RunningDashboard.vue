<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Running</h1>
        <p class="page-sub">Pace, mileage, and effort trends</p>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading data…</span>
    </div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard label="Runs" :value="totalRuns" color="#3B82F6" />
        <MetricCard label="Total Distance" :value="totalMi" unit="mi" color="#10B981" />
        <MetricCard label="Avg Pace" :value="avgPaceLabel" color="#7C3AED" />
        <MetricCard label="Avg HR" :value="avgHR" unit="bpm" color="#E5341D" />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Pace Trend (min/mi)</h2>
          <p class="chart-desc">Average pace per running session in min/mi. Faster pace at the same heart rate over time is the clearest sign of improving aerobic efficiency (running economy). Compare pace at similar HR values across months to gauge fitness gains.</p>
          <TimeSeriesChart
            v-if="paceSeries.length"
            :series="paceSeries"
            y-axis-label="min/mi"
          />
          <p v-else class="empty">No running data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Distance per Run</h2>
          <p class="chart-desc">Distance of each individual run. Useful for identifying outliers (very long or very short sessions) and tracking progression of long run distance over a training cycle.</p>
          <TimeSeriesChart
            v-if="distanceSeries.length"
            :series="distanceSeries"
            y-axis-label="mi"
          />
          <p v-else class="empty">No running data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Heart Rate per Run</h2>
          <p class="chart-desc">Average heart rate for each running session. At constant effort, a declining HR trend over weeks indicates improving cardiovascular fitness. Use alongside pace to track aerobic efficiency.</p>
          <TimeSeriesChart
            v-if="hrSeries.length"
            :series="hrSeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No HR data in range.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import { useMetricData } from "@/composables/useMetricData"
import { mToMi, paceKmToMi, DIST_UNIT, PACE_UNIT } from "@/utils/units"

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
}

// sport filter handled server-side via query param (useMetricData passes start/end only)
// We fetch all activities and filter by sport client-side to support varied sport naming.
const { data: allActivities, loading, error } = useMetricData<Activity[]>("/activities/")

const runs = computed(() =>
  (allActivities.value ?? []).filter((a) => {
    const s = (a.sport ?? a.type ?? "").toLowerCase()
    return s.includes("run") || s.includes("trail")
  })
)

// Chronological order for charts
const chronological = computed(() => [...runs.value].reverse())

const totalRuns = computed(() => runs.value.length)
const totalMi = computed(() => {
  const mi = runs.value.reduce((s, a) => s + (a.distance_m ?? 0), 0) / 1609.344
  return mi > 0 ? +mi.toFixed(1) : null
})
const avgHR = computed(() => {
  const withHR = runs.value.filter((a) => a.avg_hr)
  if (!withHR.length) return null
  return Math.round(withHR.reduce((s, a) => s + (a.avg_hr ?? 0), 0) / withHR.length)
})
const avgPaceMin = computed(() => {
  const valid = runs.value.filter((a) => a.elapsed_time_s && a.distance_m && a.distance_m > 100)
  if (!valid.length) return null
  const paces = valid.map((a) => paceKmToMi(a.elapsed_time_s! / 60 / (a.distance_m! / 1000)) ?? 0)
  return paces.reduce((s, p) => s + p, 0) / paces.length
})
const avgPaceLabel = computed(() => {
  if (!avgPaceMin.value) return null
  const min = Math.floor(avgPaceMin.value)
  const sec = Math.round((avgPaceMin.value - min) * 60)
  return `${min}:${sec.toString().padStart(2, "0")}`
})

const paceSeries = computed(() => {
  const pts = chronological.value
    .filter((a) => a.start_time && a.elapsed_time_s && a.distance_m && a.distance_m > 100)
    .map((a) => {
      const pace = paceKmToMi(a.elapsed_time_s! / 60 / (a.distance_m! / 1000)) ?? 0
      return [a.start_time!.slice(0, 10), +pace.toFixed(2)] as [string, number]
    })
  return pts.length ? [{ name: "Pace", data: pts, color: "#7C3AED" }] : []
})

const distanceSeries = computed(() => {
  const pts = chronological.value
    .filter((a) => a.start_time && a.distance_m)
    .map((a) => [a.start_time!.slice(0, 10), mToMi(a.distance_m!, 2)!] as [string, number])
  return pts.length ? [{ name: "Distance", data: pts, color: "#10B981" }] : []
})

const hrSeries = computed(() => {
  const pts = chronological.value
    .filter((a) => a.start_time && a.avg_hr)
    .map((a) => [a.start_time!.slice(0, 10), a.avg_hr] as [string, number | null])
  return pts.length ? [{ name: "Avg HR", data: pts, color: "#E5341D" }] : []
})
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
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 4px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
