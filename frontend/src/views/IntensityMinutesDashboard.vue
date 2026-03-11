<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Intensity Minutes</h1>
        <p class="page-sub">Moderate &amp; vigorous activity time — WHO guidelines tracking</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Showing</span>
      <DateRangePicker />
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading intensity data…</span></div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard
          label="Avg Moderate / Day"
          :value="avgModerate"
          unit="min"
          color="#F59E0B"
          :spark-data="rows?.map(d => d.intensity_min_moderate) ?? []"
        />
        <MetricCard
          label="Avg Vigorous / Day"
          :value="avgVigorous"
          unit="min"
          color="#EF4444"
          :spark-data="rows?.map(d => d.intensity_min_vigorous) ?? []"
        />
        <MetricCard
          label="Weekly Equiv. Minutes"
          :value="weeklyEquiv"
          unit="min/wk"
          color="#8B5CF6"
        />
        <MetricCard
          label="WHO Target"
          :value="whoTarget"
          unit="min/wk"
          color="#6B7280"
        />
      </div>

      <!-- WHO status banner -->
      <div class="who-banner" :class="whoBannerClass">
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
          <path v-if="whoMet" fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          <path v-else fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
        <span v-if="whoMet">Meeting WHO guidelines — averaging {{ weeklyEquiv }} vigorous-equivalent min/week (target: ≥150)</span>
        <span v-else>Below WHO guidelines — averaging {{ weeklyEquiv ?? 0 }} vigorous-equivalent min/week (target: ≥150)</span>
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Weekly Intensity Minutes</h2>
          <p class="chart-desc">Total moderate and vigorous intensity minutes per week. The WHO recommends at least 150 min/week of moderate activity or 75 min/week of vigorous activity for cardiovascular health. Vigorous minutes count double — a 30-minute hard run counts as 60 equivalent minutes. The dashed line shows the 150-min vigorous-equivalent threshold.</p>
          <StackedBarChart
            v-if="weeklyCategories.length"
            :categories="weeklyCategories"
            :series="weeklySeries"
            :mark-line="150"
            y-axis-label="min"
          />
          <p v-else class="empty">No intensity data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Daily Intensity Minutes</h2>
          <p class="chart-desc">Moderate (yellow) and vigorous (red) intensity minutes each day. Most days will be zero or low — intensity minutes accumulate during structured workouts and brisk walks. Vigorous minutes are harder to accumulate but count double toward the weekly target.</p>
          <StackedBarChart
            v-if="dailyCategories.length"
            :categories="dailyCategories"
            :series="dailySeries"
            y-axis-label="min"
          />
          <p v-else class="empty">No daily intensity data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Cumulative Vigorous-Equivalent Minutes (Rolling 7-Day)</h2>
          <p class="chart-desc">7-day rolling total of vigorous-equivalent minutes (moderate + 2× vigorous). Staying consistently above 150 min/week reduces risk of cardiovascular disease, type 2 diabetes, and all-cause mortality. Values above 300 min/week deliver additional but diminishing health benefits.</p>
          <TimeSeriesChart
            v-if="rollingEquivSeries.length"
            :series="rollingEquivSeries"
            y-axis-label="min"
          />
          <p v-else class="empty">No data in range.</p>
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

interface DailyRow {
  date: string
  intensity_min_moderate: number | null
  intensity_min_vigorous: number | null
}

const { data: rows, loading, error } = useMetricData<DailyRow[]>("/health/daily")

const WHO_TARGET = 150  // vigorous-equivalent min/week

function avg(vals: (number | null | undefined)[]): number | null {
  const v = vals.filter((x): x is number => x != null)
  return v.length ? Math.round(v.reduce((s, x) => s + x, 0) / v.length) : null
}

const avgModerate = computed(() => avg(rows.value?.map(d => d.intensity_min_moderate) ?? []))
const avgVigorous = computed(() => avg(rows.value?.map(d => d.intensity_min_vigorous) ?? []))

// Vigorous-equivalent minutes per week (moderate + 2×vigorous, 7-day rolling)
const weeklyEquiv = computed(() => {
  if (!rows.value?.length) return null
  const days = rows.value.length
  const totalMod = rows.value.reduce((s, d) => s + (d.intensity_min_moderate ?? 0), 0)
  const totalVig = rows.value.reduce((s, d) => s + (d.intensity_min_vigorous ?? 0), 0)
  const weeksInRange = days / 7
  return weeksInRange > 0 ? Math.round((totalMod + totalVig * 2) / weeksInRange) : null
})

const whoTarget = computed(() => WHO_TARGET)
const whoMet = computed(() => (weeklyEquiv.value ?? 0) >= WHO_TARGET)
const whoBannerClass = computed(() => whoMet.value ? 'who-met' : 'who-miss')

// Daily stacked bar
const dailyCategories = computed(() =>
  (rows.value ?? [])
    .filter(d => d.intensity_min_moderate != null || d.intensity_min_vigorous != null)
    .map(d => d.date)
)
const dailySeries = computed(() => {
  const filtered = (rows.value ?? []).filter(d => d.intensity_min_moderate != null || d.intensity_min_vigorous != null)
  return [
    { name: "Moderate", data: filtered.map(d => d.intensity_min_moderate ?? 0), color: "#F59E0B" },
    { name: "Vigorous", data: filtered.map(d => d.intensity_min_vigorous ?? 0), color: "#EF4444" },
  ]
})

// Weekly aggregation (group by ISO week)
const weeklyCategories = computed(() => {
  const weeks = new Map<string, { mod: number; vig: number }>()
  for (const d of rows.value ?? []) {
    const dt = new Date(d.date)
    // ISO week start (Monday)
    const day = dt.getDay() || 7
    const monday = new Date(dt)
    monday.setDate(dt.getDate() - day + 1)
    const wk = monday.toISOString().slice(0, 10)
    if (!weeks.has(wk)) weeks.set(wk, { mod: 0, vig: 0 })
    const entry = weeks.get(wk)!
    entry.mod += d.intensity_min_moderate ?? 0
    entry.vig += d.intensity_min_vigorous ?? 0
  }
  return [...weeks.keys()].sort()
})

const weeklySeries = computed(() => {
  const weeks = new Map<string, { mod: number; vig: number }>()
  for (const d of rows.value ?? []) {
    const dt = new Date(d.date)
    const day = dt.getDay() || 7
    const monday = new Date(dt)
    monday.setDate(dt.getDate() - day + 1)
    const wk = monday.toISOString().slice(0, 10)
    if (!weeks.has(wk)) weeks.set(wk, { mod: 0, vig: 0 })
    const entry = weeks.get(wk)!
    entry.mod += d.intensity_min_moderate ?? 0
    entry.vig += d.intensity_min_vigorous ?? 0
  }
  const sorted = [...weeks.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  return [
    { name: "Moderate", data: sorted.map(([, v]) => v.mod), color: "#F59E0B" },
    { name: "Vigorous (×2 equiv)", data: sorted.map(([, v]) => v.vig), color: "#EF4444" },
  ]
})

// 7-day rolling vigorous-equivalent total
const rollingEquivSeries = computed(() => {
  const data = rows.value ?? []
  if (!data.length) return []
  const pts = data.map((d, i) => {
    const slice = data.slice(Math.max(0, i - 6), i + 1)
    const equiv = slice.reduce((s, r) => s + (r.intensity_min_moderate ?? 0) + (r.intensity_min_vigorous ?? 0) * 2, 0)
    return [d.date, equiv] as [string, number]
  })
  return [{ name: "7-Day Vigorous-Equiv", data: pts, color: "#8B5CF6", smooth: true }]
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.charts { display: flex; flex-direction: column; gap: 16px; }
.chart-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 20px 8px; }
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 4px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }

.who-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius);
  font-size: 0.82rem;
  font-weight: 500;
}
.who-met { background: #F0FDF4; color: #15803D; border: 1px solid #BBF7D0; }
.who-miss { background: #FEF9C3; color: #A16207; border: 1px solid #FDE68A; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
