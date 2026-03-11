<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Max HR &amp; Aging</h1>
        <p class="page-sub">How your heart rate ceiling has changed over time</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Period</span>
      <DateRangePicker />
      <span class="range-note">All-time view — shows complete activity history regardless of date filter</span>
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading data…</span></div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="yearData.length">
      <div class="stat-grid">
        <MetricCard label="Latest P90 Max HR" :value="latest?.annual_p90_hr ? Math.round(latest.annual_p90_hr) : null" unit="bpm" color="#E5341D" />
        <MetricCard label="Age-Predicted Max" :value="latest?.age_predicted_max ? Math.round(latest.age_predicted_max) : null" unit="bpm" color="#9A9690" />
        <MetricCard label="% of Predicted" :value="latest?.pct_age_predicted ? +latest.pct_age_predicted.toFixed(1) : null" unit="%" color="#7C3AED" />
        <MetricCard
          label="Decline Rate"
          :value="latest?.decline_rate_bpm_per_year ? +latest.decline_rate_bpm_per_year.toFixed(2) : null"
          unit="bpm/yr"
          color="#F59E0B"
        />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Workout Max HR vs. Age-Predicted (all time)</h2>
          <p class="chart-desc">Each point is a qualifying aerobic workout (≥10 min, max HR ≥130 bpm). The red line tracks your annual 90th-percentile max HR; the dashed gray line is the Tanaka age-predicted ceiling (208 − 0.7 × age). Values above the dashed line indicate you're exceeding your predicted maximum.</p>
          <ScatterTrendChart
            v-if="scatterReady"
            :scatter="workoutScatter"
            :trends="agingTrends"
            y-axis-label="BPM"
            :x-is-time="true"
          />
          <p v-else class="empty">No activity HR data available.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Annual Max HR Distribution</h2>
          <p class="chart-desc">Annual peak HR (lightest) shows your absolute ceiling each year. P90 (darkest) filters out anomalies for a robust trend. The gray line is the Tanaka predicted ceiling for your age that year.</p>
          <TimeSeriesChart
            v-if="annualSeries.length"
            :series="annualSeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No annual data.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">HR Reserve per Year (Max − Resting)</h2>
          <p class="chart-desc">Heart rate reserve (HRR) = annual P90 max HR minus average resting HR. A higher HRR indicates greater cardiovascular fitness and training adaptability. Elite endurance athletes typically maintain HRR above 130 bpm.</p>
          <TimeSeriesChart
            v-if="reserveSeries.length"
            :series="reserveSeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No HR reserve data.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">% of Age-Predicted Max</h2>
          <p class="chart-desc">Percentage of your observed P90 max HR relative to the Tanaka age-predicted maximum. Values above 100% indicate your measured peak exceeds the formula prediction — common in well-trained athletes.</p>
          <TimeSeriesChart
            v-if="pctSeries.length"
            :series="pctSeries"
            y-axis-label="%"
          />
          <p v-else class="empty">No % predicted data.</p>
        </div>
      </div>

      <div class="chart-block notes-block">
        <h2 class="chart-title">Methodology</h2>
        <p class="note">P90 = 90th percentile of max HR across all qualifying aerobic sessions (≥10 min, max HR ≥130 bpm) in each year. Age-predicted line uses Tanaka (2001): <em>208 − 0.7 × age</em>. Decline rate is a linear regression slope on annual P90 values; expected physiological rate ≈ −1 bpm/yr.</p>
      </div>
    </template>

    <div v-else class="empty-state">
      <p>No max HR aging data yet. Run a sync to populate activity data, then the analysis engine will compute this automatically.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import ScatterTrendChart from "@/components/charts/ScatterTrendChart.vue"
import { api } from "@/api/client"
import { ref, onMounted } from "vue"

interface YearRow {
  year: number
  annual_peak_hr: number | null
  annual_p95_hr: number | null
  annual_p90_hr: number | null
  activity_count: number | null
  age_predicted_max: number | null
  hr_reserve: number | null
  pct_age_predicted: number | null
  decline_rate_bpm_per_year: number | null
}

interface Activity {
  activity_id: number
  start_time: string | null
  max_hr: number | null
  elapsed_time_s: number | null
  sport: string | null
  type: string | null
}

// Year data does not filter by date range
const yearData = ref<YearRow[]>([])
const activities = ref<Activity[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const [yearsRes, actRes] = await Promise.all([
      api.get("/training/max-hr-aging"),
      api.get("/activities/", { params: { limit: 500 } }),
    ])
    yearData.value = yearsRes.data ?? []
    activities.value = actRes.data ?? []
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const latest = computed(() => yearData.value[yearData.value.length - 1] ?? null)

// Scatter: individual workout max_hr values over time
const workoutScatter = computed(() =>
  activities.value
    .filter((a) => a.start_time && a.max_hr && (a.elapsed_time_s ?? 0) >= 600 && a.max_hr >= 130)
    .map((a) => ({ x: a.start_time!.slice(0, 10), y: a.max_hr! }))
)

const scatterReady = computed(() => workoutScatter.value.length > 0 || yearData.value.length > 0)

// Trend lines for the scatter chart
const agingTrends = computed(() => {
  const lines = []
  if (yearData.value.length) {
    lines.push({
      name: "P90 Max HR",
      data: yearData.value
        .filter((r) => r.annual_p90_hr)
        .map((r) => [`${r.year}-07-01`, r.annual_p90_hr!] as [string, number]),
      color: "#E5341D",
    })
    const withPred = yearData.value.filter((r) => r.age_predicted_max)
    if (withPred.length) {
      lines.push({
        name: "Age-Predicted (Tanaka)",
        data: withPred.map((r) => [`${r.year}-07-01`, r.age_predicted_max!] as [string, number]),
        color: "#9CA3AF",
        dashed: true,
      })
    }
  }
  return lines
})

const annualSeries = computed(() => {
  if (!yearData.value.length) return []
  return [
    { name: "P90 Max HR", data: yearData.value.filter(r => r.annual_p90_hr).map(r => [`${r.year}-07-01`, r.annual_p90_hr!] as [string, number]), color: "#E5341D", smooth: true },
    { name: "Annual Peak HR", data: yearData.value.filter(r => r.annual_peak_hr).map(r => [`${r.year}-07-01`, r.annual_peak_hr!] as [string, number]), color: "#FCA5A5", smooth: false },
    { name: "Age-Predicted", data: yearData.value.filter(r => r.age_predicted_max).map(r => [`${r.year}-07-01`, r.age_predicted_max!] as [string, number]), color: "#D1D5DB", smooth: true },
  ]
})

const reserveSeries = computed(() => {
  const rows = yearData.value.filter(r => r.hr_reserve)
  if (!rows.length) return []
  return [{ name: "HR Reserve", data: rows.map(r => [`${r.year}-07-01`, r.hr_reserve!] as [string, number]), color: "#7C3AED", smooth: true }]
})

const pctSeries = computed(() => {
  const rows = yearData.value.filter(r => r.pct_age_predicted)
  if (!rows.length) return []
  return [{ name: "% of Age-Predicted", data: rows.map(r => [`${r.year}-07-01`, r.pct_age_predicted!] as [string, number]), color: "#3B82F6", smooth: true }]
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); font-weight: 400; }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }
.range-note { font-size: 0.75rem; color: var(--muted); font-style: italic; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: -6px 0 10px; line-height: 1.5; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.charts { display: flex; flex-direction: column; gap: 16px; }
.chart-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 20px 8px; }
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.notes-block { padding-bottom: 20px; }
.note { font-size: 0.82rem; color: var(--muted); line-height: 1.6; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
.empty-state { padding: 48px 0; color: var(--muted); font-size: 0.9rem; }
</style>
