<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Calories</h1>
        <p class="page-sub">Daily energy expenditure — total burn, basal metabolism, and active calories</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Showing</span>
      <DateRangePicker />
    </div>

    <div v-if="anyLoading" class="loading"><div class="spinner"></div><span>Loading calorie data…</span></div>
    <div v-else-if="anyError" class="error-msg">{{ anyError }}</div>

    <template v-else>
      <!-- Stat cards -->
      <div class="stat-grid">
        <MetricCard
          label="Avg Daily Total"
          :value="avgTotal"
          unit="kcal"
          color="#EF4444"
          :spark-data="daily?.map(d => d.calories_total) ?? []"
        />
        <MetricCard
          label="Avg BMR"
          :value="avgBmr"
          unit="kcal"
          color="#9CA3AF"
          :spark-data="daily?.map(d => d.calories_bmr) ?? []"
        />
        <MetricCard
          label="Avg Active Calories"
          :value="avgActive"
          unit="kcal"
          color="#F59E0B"
          :spark-data="daily?.map(d => d.calories_active) ?? []"
        />
        <MetricCard
          label="Avg Workout Calories"
          :value="avgWorkoutCal"
          unit="kcal"
          color="#3B82F6"
        />
      </div>

      <!-- Charts -->
      <div class="charts">
        <!-- Stacked total burn -->
        <div class="chart-block">
          <h2 class="chart-title">Daily Calorie Breakdown (BMR + Active)</h2>
          <p class="chart-desc">Each bar shows total daily calorie burn split into basal metabolic rate (gray — calories burned just to stay alive) and active calories (orange — extra burn from movement and exercise). The total bar height is your estimated daily energy expenditure.</p>
          <StackedBarChart
            v-if="stackedCategories.length"
            :categories="stackedCategories"
            :series="stackedSeries"
            y-axis-label="kcal"
          />
          <p v-else class="empty">No calorie data in range.</p>
        </div>

        <!-- Total burn trend line -->
        <div class="chart-block">
          <h2 class="chart-title">Total Daily Burn Trend</h2>
          <p class="chart-desc">7-day rolling average of total daily calorie expenditure. High days reflect intense workout sessions or high step counts; low days are typically rest days. Use this alongside calorie intake to track energy balance over time.</p>
          <TimeSeriesChart
            v-if="totalSeries.length"
            :series="totalSeries"
            y-axis-label="kcal"
          />
          <p v-else class="empty">No total calorie data in range.</p>
        </div>

        <!-- Active calories trend -->
        <div class="chart-block">
          <h2 class="chart-title">Active Calories Trend</h2>
          <p class="chart-desc">Calories burned above your basal rate from all movement — workouts, walking, and general activity. This is the portion of your burn you can directly influence through training and daily habits. Active calories above 400–500 kcal/day indicate a meaningfully active day.</p>
          <TimeSeriesChart
            v-if="activeSeries.length"
            :series="activeSeries"
            y-axis-label="kcal"
          />
          <p v-else class="empty">No active calorie data in range.</p>
        </div>

        <!-- Per-workout calories -->
        <div class="chart-block">
          <h2 class="chart-title">Calories Burned per Workout</h2>
          <p class="chart-desc">Calorie estimate for each recorded workout session, derived from heart rate and duration. Higher-intensity and longer sessions produce higher burns. Compare across sport types to understand which activities deliver the most caloric output per hour.</p>
          <TimeSeriesChart
            v-if="workoutSeries.length"
            :series="workoutSeries"
            y-axis-label="kcal"
          />
          <p v-else class="empty">No workout calorie data in range.</p>
        </div>

        <!-- BMR trend (usually flat, but shows body adaptation) -->
        <div class="chart-block">
          <h2 class="chart-title">Basal Metabolic Rate Trend</h2>
          <p class="chart-desc">BMR is the calories your body burns at complete rest to maintain basic functions (heart, brain, organs). It's calculated from your weight, age, and sex and changes very slowly. A rising BMR may reflect increased muscle mass; a falling BMR can indicate prolonged calorie restriction.</p>
          <TimeSeriesChart
            v-if="bmrSeries.length"
            :series="bmrSeries"
            y-axis-label="kcal"
          />
          <p v-else class="empty">No BMR data in range.</p>
        </div>
      </div>

      <!-- Workout calorie breakdown table -->
      <div class="chart-block table-block" v-if="workouts.length">
        <h2 class="chart-title">Top Calorie-Burning Workouts</h2>
        <p class="chart-desc">Activities ranked by calories burned in the selected period. Useful for understanding which sessions are contributing the most to your weekly energy expenditure.</p>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Activity</th>
              <th>Sport</th>
              <th>Duration</th>
              <th>Calories</th>
              <th>kcal/hr</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in topWorkouts" :key="a.activity_id">
              <td>{{ fmtDate(a.start_time) }}</td>
              <td class="name-cell">{{ a.name || '—' }}</td>
              <td class="sport-cell">{{ a.sport || a.type || '—' }}</td>
              <td>{{ fmtDur(a.elapsed_time_s) }}</td>
              <td class="cal-cell"><strong>{{ a.calories?.toLocaleString() }}</strong> kcal</td>
              <td class="rate-cell">{{ calRate(a) }}</td>
            </tr>
          </tbody>
        </table>
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
  calories_total: number | null
  calories_bmr: number | null
  calories_active: number | null
}

interface Activity {
  activity_id: number
  name: string | null
  sport: string | null
  type: string | null
  start_time: string | null
  elapsed_time_s: number | null
  calories: number | null
}

const { data: daily, loading: l1, error: e1 } = useMetricData<DailyRow[]>("/health/daily")
const { data: activities, loading: l2, error: e2 } = useMetricData<Activity[]>("/activities/")

const anyLoading = computed(() => l1.value || l2.value)
const anyError   = computed(() => e1.value || e2.value)

// 7-day rolling average helper
function rolling7(pts: (number | null)[]): (number | null)[] {
  return pts.map((_, i) => {
    const slice = pts.slice(Math.max(0, i - 6), i + 1).filter((v): v is number => v != null)
    return slice.length ? Math.round(slice.reduce((s, v) => s + v, 0) / slice.length) : null
  })
}

function avg(vals: (number | null | undefined)[]): number | null {
  const v = vals.filter((x): x is number => x != null)
  return v.length ? Math.round(v.reduce((s, x) => s + x, 0) / v.length) : null
}

const avgTotal  = computed(() => avg(daily.value?.map(d => d.calories_total) ?? []))
const avgBmr    = computed(() => avg(daily.value?.map(d => d.calories_bmr) ?? []))
const avgActive = computed(() => avg(daily.value?.map(d => d.calories_active) ?? []))

// Workouts in date range with calories
const workouts = computed(() =>
  (activities.value ?? []).filter(a => a.calories != null && a.calories > 0)
)
const avgWorkoutCal = computed(() => avg(workouts.value.map(a => a.calories)))

// All daily charts use the same canonical row set so X-axes stay aligned
const allRows = computed(() => daily.value ?? [])

// Stacked bar: BMR + active per day
const stackedCategories = computed(() => allRows.value.map(d => d.date))
const stackedSeries = computed(() => [
  { name: "BMR",    data: allRows.value.map(d => d.calories_bmr    ?? 0), color: "#D1D5DB" },
  { name: "Active", data: allRows.value.map(d => d.calories_active ?? 0), color: "#F59E0B" },
])

// Rolling average total
const totalSeries = computed(() => {
  if (!allRows.value.length) return []
  const rolled = rolling7(allRows.value.map(d => d.calories_total))
  return [
    { name: "Total Burn (7d avg)", data: allRows.value.map((d, i) => [d.date, rolled[i]] as [string, number | null]), color: "#EF4444", smooth: true },
    { name: "Daily Total",         data: allRows.value.map(d => [d.date, d.calories_total] as [string, number | null]), color: "#FCA5A5", smooth: false },
  ]
})

const activeSeries = computed(() => {
  if (!allRows.value.length) return []
  return [{ name: "Active Calories", data: allRows.value.map(d => [d.date, d.calories_active] as [string, number | null]), color: "#F59E0B", smooth: true }]
})

const bmrSeries = computed(() => {
  if (!allRows.value.length) return []
  return [{ name: "BMR", data: allRows.value.map(d => [d.date, d.calories_bmr] as [string, number | null]), color: "#9CA3AF", smooth: true }]
})

const workoutSeries = computed(() => {
  const sorted = [...workouts.value]
    .filter(a => a.start_time)
    .sort((a, b) => (a.start_time ?? '') < (b.start_time ?? '') ? -1 : 1)
  if (!sorted.length) return []
  return [{ name: "Workout Calories", data: sorted.map(a => [a.start_time!.slice(0, 10), a.calories] as [string, number | null]), color: "#3B82F6" }]
})

// Top 20 workouts by calories
const topWorkouts = computed(() =>
  [...workouts.value].sort((a, b) => (b.calories ?? 0) - (a.calories ?? 0)).slice(0, 20)
)

function fmtDate(ts: string | null): string {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' })
}

function fmtDur(secs: number | null): string {
  if (!secs) return '—'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function calRate(a: Activity): string {
  if (!a.calories || !a.elapsed_time_s || a.elapsed_time_s < 60) return '—'
  return Math.round(a.calories / (a.elapsed_time_s / 3600)) + ' kcal/hr'
}
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

.table-block { padding-bottom: 16px; }
table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
th { padding: 8px 12px; text-align: left; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); border-bottom: 2px solid var(--border); }
td { padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text); }
.name-cell { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sport-cell { color: var(--muted); font-size: 0.8rem; }
.cal-cell { font-variant-numeric: tabular-nums; }
.rate-cell { font-family: monospace; font-size: 0.8rem; color: var(--muted); }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
