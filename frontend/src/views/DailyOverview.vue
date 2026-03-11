<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Daily Overview</h1>
        <p class="page-sub">{{ dateLabel }}</p>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading data…</span>
    </div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <!-- Stat cards -->
      <div class="stat-grid">
        <MetricCard
          label="Steps"
          :value="today?.steps"
          :spark-data="series('steps')"
          color="var(--c-steps)"
        />
        <MetricCard
          label="Resting HR"
          :value="today?.hr_resting"
          unit="bpm"
          :spark-data="series('hr_resting')"
          color="var(--c-rhr)"
        />
        <MetricCard
          label="Avg Stress"
          :value="today?.stress_avg"
          :spark-data="series('stress_avg')"
          color="var(--c-stress)"
        />
        <MetricCard
          label="Body Battery"
          :value="today?.body_battery_max"
          :spark-data="series('body_battery_max')"
          color="var(--c-battery)"
        />
        <MetricCard
          label="SpO₂"
          :value="today?.spo2_avg"
          unit="%"
          :spark-data="series('spo2_avg')"
          color="var(--c-spo2)"
        />
        <MetricCard
          label="Respiration"
          :value="today?.respiration_avg"
          unit="br/min"
          :spark-data="series('respiration_avg')"
          color="var(--c-resp)"
        />
      </div>

      <!-- Date range selector -->
      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <!-- Charts -->
      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Resting Heart Rate</h2>
          <p class="chart-desc">Morning resting heart rate. A sudden increase of 5+ bpm over your baseline is an early warning sign of illness, dehydration, or accumulated training fatigue. Track the 7-day trend, not individual days.</p>
          <TimeSeriesChart
            v-if="rhrSeries.length"
            :series="rhrSeries"
            y-axis-label="BPM"
          />
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Daily Steps</h2>
          <p class="chart-desc">Daily step count. 7,000–10,000 steps/day is associated with significantly reduced all-cause mortality in most studies. Steps include all walking, not just intentional exercise — background activity throughout the day matters as much as formal workouts.</p>
          <TimeSeriesChart
            v-if="stepsSeries.length"
            :series="stepsSeries"
            y-axis-label="Steps"
          />
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Body Battery &amp; Stress</h2>
          <p class="chart-desc">End-of-day body battery level and daily average physiological stress score. Consistently low body battery suggests a recovery deficit; persistent high stress at rest (outside exercise) impairs sleep and recovery.</p>
          <TimeSeriesChart
            v-if="energySeries.length"
            :series="energySeries"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import DateRangePicker from '@/components/ui/DateRangePicker.vue'
import MetricCard from '@/components/ui/MetricCard.vue'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import { useMetricData } from '@/composables/useMetricData'
import { useDateRangeStore } from '@/stores/dateRange'

interface DailySummary {
  date: string
  steps: number | null
  hr_resting: number | null
  sleep_score: number | null
  stress_avg: number | null
  body_battery_max: number | null
  spo2_avg: number | null
  respiration_avg: number | null
  wellness_score: number | null
}

const store = useDateRangeStore()
const { data, loading, error } = useMetricData<DailySummary[]>('/health/daily')

const today = computed(() => data.value?.[data.value.length - 1] ?? null)

const dateLabel = computed(() => {
  if (!today.value) return ''
  return dayjs(today.value.date).format('dddd, MMMM D, YYYY')
})

function series(key: keyof DailySummary) {
  return data.value?.map(d => d[key] as number | null) ?? []
}

// Hex colours for ECharts (which cannot resolve CSS variables)
const HEX = {
  rhr:     '#E5341D',
  steps:   '#1D5CE5',
  battery: '#16A34A',
  stress:  '#D97706',
}

const rhrSeries = computed(() => {
  if (!data.value) return []
  return [{
    name: 'Resting HR',
    data: data.value.map(d => [d.date, d.hr_resting] as [string, number | null]),
    color: HEX.rhr,
    smooth: true,
  }]
})

const stepsSeries = computed(() => {
  if (!data.value) return []
  return [{
    name: 'Steps',
    data: data.value.map(d => [d.date, d.steps] as [string, number | null]),
    color: HEX.steps,
    smooth: false,
  }]
})

const energySeries = computed(() => {
  if (!data.value) return []
  return [
    {
      name: 'Body Battery',
      data: data.value.map(d => [d.date, d.body_battery_max] as [string, number | null]),
      color: HEX.battery,
      smooth: true,
    },
    {
      name: 'Stress',
      data: data.value.map(d => [d.date, d.stress_avg] as [string, number | null]),
      color: HEX.stress,
      smooth: true,
    },
  ]
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1100px;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.page-title {
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
  color: var(--text);
}

.page-sub {
  margin-top: 4px;
  font-size: 0.83rem;
  color: var(--muted);
  font-weight: 400;
}

/* Stat cards */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

/* Date range row */
.range-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.range-label {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
  white-space: nowrap;
}

/* Charts */
.charts {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 20px 8px;
}

.chart-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted);
  margin-bottom: 4px;
}

.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }

/* Loading */
.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 0.875rem;
  padding: 40px 0;
}
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-msg {
  color: #DC2626;
  padding: 16px;
  background: #FEF2F2;
  border-radius: var(--radius);
  font-size: 0.875rem;
}
</style>
