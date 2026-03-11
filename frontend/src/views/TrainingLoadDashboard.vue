<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Training Load</h1>
        <p class="page-sub">Performance Management Chart — fitness, fatigue, and form over time</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Showing</span>
      <DateRangePicker />
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading training load…</span></div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard label="CTL (Fitness)" :value="latest?.ctl ? +latest.ctl.toFixed(1) : null" color="#3B82F6" />
        <MetricCard label="ATL (Fatigue)" :value="latest?.atl ? +latest.atl.toFixed(1) : null" color="#EF4444" />
        <MetricCard label="TSB (Form)" :value="latest?.tsb ? +latest.tsb.toFixed(1) : null" :color="tsbColor" />
        <MetricCard label="TRIMP (7d avg)" :value="trimp7d" color="#F59E0B" />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Performance Management Chart (ATL / CTL / TSB)</h2>
          <p class="chart-desc">CTL (blue) represents long-term fitness built over ~6 weeks. ATL (red) shows recent fatigue from the past ~1 week. TSB (green/orange) is the difference — positive means fresh and ready to race, negative means fatigued but building fitness.</p>
          <PMCChart v-if="chartData.length" :data="chartData" />
          <p v-else class="empty">No training load data in range. Run a sync to compute CTL/ATL from activity data.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Daily Training Impulse (TRIMP)</h2>
          <p class="chart-desc">TRIMP quantifies the physiological stress of each training session using heart rate and duration. Higher values indicate harder sessions. Use this to identify training spikes that may increase injury risk.</p>
          <TimeSeriesChart v-if="trimpSeries.length" :series="trimpSeries" y-axis-label="TRIMP" />
          <p v-else class="empty">No TRIMP data in range.</p>
        </div>
      </div>

      <div class="info-box">
        <strong>Reading the PMC:</strong> Build fitness by keeping CTL trending up. Manage fatigue by ensuring ATL doesn't stay far above CTL for extended periods. A TSB between −10 and −30 is the "sweet spot" for hard training; taper toward 0 before key events.
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import PMCChart from "@/components/charts/PMCChart.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import { useMetricData } from "@/composables/useMetricData"

interface LoadRow { date: string; atl: number | null; ctl: number | null; tsb: number | null; trimp: number | null }

const { data, loading, error } = useMetricData<LoadRow[]>("/training/load")
const chartData = computed(() => data.value ?? [])

const latest = computed(() => data.value?.[data.value.length - 1] ?? null)

const tsbColor = computed(() => {
  const tsb = latest.value?.tsb ?? 0
  if (tsb > 5) return "#16A34A"
  if (tsb < -30) return "#DC2626"
  return "#F59E0B"
})

const trimp7d = computed(() => {
  if (!data.value?.length) return null
  const last7 = data.value.slice(-7).filter(r => r.trimp != null)
  if (!last7.length) return null
  return +(last7.reduce((s, r) => s + (r.trimp ?? 0), 0) / last7.length).toFixed(1)
})

const trimpSeries = computed(() => {
  const rows = data.value?.filter(r => r.trimp != null) ?? []
  if (!rows.length) return []
  return [{ name: "TRIMP", data: rows.map(r => [r.date, r.trimp] as [string, number | null]), color: "#F59E0B" }]
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.charts { display: flex; flex-direction: column; gap: 16px; }
.chart-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 20px 8px; }
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 4px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: -6px 0 10px; line-height: 1.5; }
.info-box { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: var(--radius); padding: 14px 16px; font-size: 0.83rem; color: var(--text); line-height: 1.6; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
