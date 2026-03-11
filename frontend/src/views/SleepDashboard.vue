<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Sleep</h1>
        <p class="page-sub">Sleep duration, stages, and quality</p>
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
          label="Sleep Duration"
          :value="latestDurationH"
          unit="h"
          :spark-data="durationSpark"
          color="#1D4ED8"
        />
        <MetricCard
          label="Sleep Score"
          :value="latest?.score"
          :spark-data="scoreSpark"
          color="#7C3AED"
        />
        <MetricCard
          label="Deep Sleep"
          :value="latestDeepH"
          unit="h"
          :spark-data="deepSpark"
          color="#1E40AF"
        />
        <MetricCard
          label="REM Sleep"
          :value="latestRemH"
          unit="h"
          :spark-data="remSpark"
          color="#5B21B6"
        />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Sleep Duration</h2>
          <p class="chart-desc">Total hours slept each night. The 7-day rolling average (smooth line) filters night-to-night variation to reveal the true trend. Adults need 7–9 hours; consistent short sleep correlates with elevated resting heart rate and reduced HRV.</p>
          <TimeSeriesChart
            v-if="durationSeries.length"
            :series="durationSeries"
            y-axis-label="hours"
          />
          <p v-else class="empty">No sleep data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Sleep Stages</h2>
          <p class="chart-desc">Breakdown of each night into light, deep (slow-wave), and REM sleep. Deep sleep is critical for physical recovery and growth hormone release; REM sleep supports memory consolidation and emotional regulation. Aim for 15–25% deep and 20–25% REM.</p>
          <StackedBarChart
            v-if="data && data.length"
            :categories="dates"
            :series="stageSeries"
            y-axis-label="Minutes"
          />
          <p v-else class="empty">No sleep stage data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Sleep Score</h2>
          <p class="chart-desc">Garmin's composite sleep quality score (0–100) accounting for duration, stage distribution, and restlessness. Scores above 70 are generally considered good; below 60 may indicate poor recovery.</p>
          <TimeSeriesChart
            v-if="scoreSeries.length"
            :series="scoreSeries"
          />
          <p v-else class="empty">No sleep score data in range.</p>
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
import StackedBarChart from "@/components/charts/StackedBarChart.vue"
import { useMetricData } from "@/composables/useMetricData"

interface SleepRow {
  date: string
  total_sleep_min: number | null
  deep_sleep_min: number | null
  light_sleep_min: number | null
  rem_sleep_min: number | null
  awake_min: number | null
  score: number | null
}

const { data, loading, error } = useMetricData<SleepRow[]>("/health/sleep")
const latest = computed(() => data.value?.[data.value.length - 1] ?? null)

const latestDurationH = computed(() => latest.value?.total_sleep_min != null ? +(latest.value.total_sleep_min / 60).toFixed(1) : null)
const latestDeepH = computed(() => latest.value?.deep_sleep_min != null ? +(latest.value.deep_sleep_min / 60).toFixed(1) : null)
const latestRemH = computed(() => latest.value?.rem_sleep_min != null ? +(latest.value.rem_sleep_min / 60).toFixed(1) : null)

const durationSpark = computed(() => data.value?.map((d) => d.total_sleep_min != null ? d.total_sleep_min / 60 : null) ?? [])
const scoreSpark = computed(() => data.value?.map((d) => d.score) ?? [])
const deepSpark = computed(() => data.value?.map((d) => d.deep_sleep_min) ?? [])
const remSpark = computed(() => data.value?.map((d) => d.rem_sleep_min) ?? [])

const dates = computed(() => (data.value ?? []).map((d) => d.date))

const durationSeries = computed(() => {
  if (!data.value) return []
  return [{
    name: "Sleep Duration",
    data: data.value.map((d) => [d.date, d.total_sleep_min != null ? +(d.total_sleep_min / 60).toFixed(2) : null] as [string, number | null]),
    color: "#1D4ED8",
    smooth: true,
  }]
})

const stageSeries = computed(() => [
  { name: "Deep", data: (data.value ?? []).map((d) => d.deep_sleep_min ?? 0), color: "#1d4ed8" },
  { name: "Light", data: (data.value ?? []).map((d) => d.light_sleep_min ?? 0), color: "#60a5fa" },
  { name: "REM", data: (data.value ?? []).map((d) => d.rem_sleep_min ?? 0), color: "#7c3aed" },
  { name: "Awake", data: (data.value ?? []).map((d) => d.awake_min ?? 0), color: "#fbbf24" },
])

const scoreSeries = computed(() => {
  if (!data.value) return []
  return [{
    name: "Sleep Score",
    data: data.value.map((d) => [d.date, d.score] as [string, number | null]),
    color: "#7C3AED",
    smooth: true,
  }]
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
