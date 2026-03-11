<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Recovery &amp; Stress</h1>
        <p class="page-sub">Stress levels and body battery trends</p>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading data…</span>
    </div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard
          label="Avg Stress"
          :value="latest?.stress_avg"
          :spark-data="series('stress_avg')"
          color="#D97706"
        />
        <MetricCard
          label="Body Battery (max)"
          :value="latest?.body_battery_max"
          :spark-data="series('body_battery_max')"
          color="#16A34A"
        />
        <MetricCard
          label="Body Battery (min)"
          :value="latest?.body_battery_min"
          :spark-data="series('body_battery_min')"
          color="#86EFAC"
        />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Stress Level</h2>
          <p class="chart-desc">Average physiological stress score (0–100) estimated from HRV patterns throughout the day. Garmin distinguishes between activity stress and baseline resting stress. Chronic elevated stress (&gt;50 at rest) can impair recovery, sleep quality, and training adaptation.</p>
          <TimeSeriesChart
            v-if="stressSeries.length"
            :series="stressSeries"
            y-axis-label="Stress"
          />
          <p v-else class="empty">No stress data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Body Battery</h2>
          <p class="chart-desc">Body battery tracks your energy reserves throughout the day, draining during activity and stress and recharging during sleep. A consistently low end-of-day body battery (below 20) suggests accumulated fatigue and a need for easier training or more sleep.</p>
          <TimeSeriesChart
            v-if="batterySeries.length"
            :series="batterySeries"
          />
          <p v-else class="empty">No body battery data in range.</p>
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

interface DailySummary {
  date: string
  stress_avg: number | null
  body_battery_max: number | null
  body_battery_min: number | null
}

const { data, loading, error } = useMetricData<DailySummary[]>("/health/daily")
const latest = computed(() => data.value?.[data.value.length - 1] ?? null)

function series(key: keyof DailySummary) {
  return data.value?.map((d) => d[key] as number | null) ?? []
}

const stressSeries = computed(() => {
  if (!data.value) return []
  return [{ name: "Avg Stress", data: data.value.map((d) => [d.date, d.stress_avg] as [string, number | null]), color: "#D97706", smooth: true }]
})

const batterySeries = computed(() => {
  if (!data.value) return []
  return [
    { name: "Battery Max", data: data.value.map((d) => [d.date, d.body_battery_max] as [string, number | null]), color: "#16A34A", smooth: true },
    { name: "Battery Min", data: data.value.map((d) => [d.date, d.body_battery_min] as [string, number | null]), color: "#86EFAC", smooth: true },
  ]
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
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
