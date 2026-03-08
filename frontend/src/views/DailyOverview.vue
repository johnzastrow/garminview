<template>
  <div class="dashboard">
    <h1>Daily Overview</h1>
    <DateRangePicker />
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <div class="metric-grid">
        <MetricCard label="Steps" :value="today?.steps" unit=" steps" />
        <MetricCard label="Resting HR" :value="today?.hr_resting" unit=" bpm" />
        <MetricCard label="Sleep Score" :value="today?.sleep_score" unit="/100" />
        <MetricCard label="Stress" :value="today?.stress_avg" />
        <MetricCard label="Body Battery" :value="today?.body_battery_max" />
        <MetricCard label="SpO2" :value="today?.spo2_avg" unit="%" />
      </div>
      <TimeSeriesChart v-if="rhrSeries.length" :series="rhrSeries" y-axis-label="BPM" />
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
  steps: number | null
  hr_resting: number | null
  sleep_score: number | null
  stress_avg: number | null
  body_battery_max: number | null
  spo2_avg: number | null
}

const { data, loading, error } = useMetricData<DailySummary[]>("/health/daily")
const today = computed(() => data.value?.[data.value.length - 1] ?? null)
const rhrSeries = computed(() => {
  if (!data.value) return []
  return [{ name: "Resting HR", data: data.value.map((d) => [d.date, d.hr_resting] as [string, number | null]), color: "#ef4444", smooth: true }]
})
</script>

<style scoped>
.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; margin: 16px 0; }
.loading, .error { padding: 24px; text-align: center; }
.error { color: #ef4444; }
</style>
