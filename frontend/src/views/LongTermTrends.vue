<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Long-Term Trends</h1>
        <p class="page-sub">Multi-year view across all health & fitness domains</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Showing</span>
      <DateRangePicker />
    </div>

    <div v-if="anyLoading" class="loading"><div class="spinner"></div><span>Loading data…</span></div>
    <div v-else-if="anyError" class="error-msg">{{ anyError }}</div>

    <template v-else>
      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Resting Heart Rate (30-day rolling avg)</h2>
          <p class="chart-desc">30-day rolling average of daily resting HR smooths short-term noise to reveal the true cardiovascular fitness trend. A declining RHR over months is one of the clearest physiological signatures of improving aerobic fitness.</p>
          <TimeSeriesChart v-if="rhrSeries.length" :series="rhrSeries" y-axis-label="BPM" />
          <p v-else class="empty">No RHR data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Daily Steps (30-day rolling avg)</h2>
          <p class="chart-desc">Long-term background activity trend. The 30-day average reveals lifestyle activity patterns, seasonal changes (less walking in winter), and the impact of major life changes on daily movement.</p>
          <TimeSeriesChart v-if="stepsSeries.length" :series="stepsSeries" y-axis-label="Steps" />
          <p v-else class="empty">No steps data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Sleep Duration (30-day rolling avg)</h2>
          <p class="chart-desc">Long-term sleep duration trend. Chronic sleep restriction (averaging below 7 hours) is associated with impaired recovery, elevated cortisol, and reduced athletic performance. Seasonal and lifestyle patterns are clearly visible at this timescale.</p>
          <TimeSeriesChart v-if="sleepSeries.length" :series="sleepSeries" y-axis-label="hours" />
          <p v-else class="empty">No sleep data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Training Fitness (CTL) &amp; Fatigue (ATL)</h2>
          <p class="chart-desc">Chronic Training Load (blue, fitness) and Acute Training Load (red, fatigue) over the full period of record. The gap between CTL and ATL represents your form — use this to plan training blocks and peaking phases.</p>
          <TimeSeriesChart v-if="ctlSeries.length" :series="ctlSeries" />
          <p v-else class="empty">No training load data in range. Run a sync to compute CTL/ATL.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Body Weight</h2>
          <p class="chart-desc">Long-term body weight trend. At this timescale, seasonal weight patterns (holiday weight gain, summer leanness), the effect of training cycles, and dietary changes are clearly visible.</p>
          <TimeSeriesChart v-if="weightSeries.length" :series="weightSeries" y-axis-label="lbs" />
          <p v-else class="empty">No weight data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Body Battery &amp; Stress</h2>
          <p class="chart-desc">Long-term patterns in energy (body battery max, green) and physiological stress (daily average, amber). The inverse relationship between these metrics reveals periods of good vs. poor recovery.</p>
          <TimeSeriesChart v-if="energySeries.length" :series="energySeries" />
          <p v-else class="empty">No body battery data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">VO₂max Over Time (Garmin FirstBeat)</h2>
          <p class="chart-desc">
            VO₂max (ml/kg/min) estimated by the Garmin FirstBeat algorithm from GPS + HR data on running activities.
            Each point represents one qualifying run. An upward trend over months indicates improving aerobic fitness;
            a downward trend during unstructured training periods is normal and expected.
            Values typically range 35–75 for recreational runners.
          </p>
          <div v-if="v2Loading" class="loading" style="padding:16px 0;"><div class="spinner"></div><span>Loading…</span></div>
          <template v-else-if="vo2Series.length">
            <TimeSeriesChart :series="vo2Series" y-axis-label="ml/kg/min" />
          </template>
          <p v-else class="empty">No VO₂max data in range. Run activities with GPS + HR to generate estimates.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Fitness Age Over Time</h2>
          <p class="chart-desc">
            Fitness age derived from Garmin VO₂max estimates and your chronological age using Cooper Institute norms.
            A fitness age <strong>below</strong> chronological age indicates above-average aerobic fitness for your demographic.
            Because it's VO₂max-derived, it updates only when a qualifying run produces a new VO₂max estimate.
          </p>
          <div v-if="v2Loading" class="loading" style="padding:16px 0;"><div class="spinner"></div><span>Loading…</span></div>
          <template v-else-if="fitnessAgeSeries.length">
            <TimeSeriesChart :series="fitnessAgeSeries" y-axis-label="years" />
          </template>
          <p v-else class="empty">No fitness age data in range.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import { useMetricData } from "@/composables/useMetricData"
import { kgToLbs } from "@/utils/units"
import { api } from "@/api/client"

interface DailySummary {
  date: string; steps: number | null; hr_resting: number | null
  stress_avg: number | null; body_battery_max: number | null
}
interface SleepRow { date: string; total_sleep_min: number | null }
interface LoadRow { date: string; atl: number | null; ctl: number | null }
interface WeightRow { date: string; weight_kg: number | null }
interface VO2Point { date: string; vo2max: number }

const { data: daily,  loading: l1, error: e1 } = useMetricData<DailySummary[]>("/health/daily")
const { data: sleep,  loading: l2, error: e2 } = useMetricData<SleepRow[]>("/health/sleep")
const { data: load,   loading: l3, error: e3 } = useMetricData<LoadRow[]>("/training/load")
const { data: weight, loading: l4, error: e4 } = useMetricData<WeightRow[]>("/body/weight")

const anyLoading = computed(() => l1.value || l2.value || l3.value || l4.value)
const anyError   = computed(() => e1.value || e2.value || e3.value || e4.value)

// VO2max trend — loaded separately (not date-range reactive; all-time for trends)
const vo2Points = ref<VO2Point[]>([])
const v2Loading = ref(true)
const athleteAge = ref<number | null>(null)

onMounted(async () => {
  try {
    const [v2resp, profileResp] = await Promise.all([
      api.get("/activities/vo2max-trend"),
      api.get("/admin/athlete-metrics"),
    ])
    vo2Points.value = v2resp.data
    athleteAge.value = profileResp.data.age ?? null
  } catch { /* ignore */ } finally {
    v2Loading.value = false
  }
})

// 30-day rolling average for a [date,value] series
function rolling(pts: [string, number | null][], w = 30): [string, number | null][] {
  return pts.map((_, i) => {
    const slice = pts.slice(Math.max(0, i - w + 1), i + 1)
    const valid = slice.filter(([, v]) => v !== null) as [string, number][]
    const avg = valid.length ? valid.reduce((s, [, v]) => s + v, 0) / valid.length : null
    return [pts[i][0], avg !== null ? +avg.toFixed(1) : null]
  })
}

const rhrSeries = computed(() => {
  if (!daily.value?.length) return []
  const raw = daily.value.map(d => [d.date, d.hr_resting] as [string, number | null])
  return [{ name: "RHR (30d avg)", data: rolling(raw), color: "#E5341D", smooth: true }]
})

const stepsSeries = computed(() => {
  if (!daily.value?.length) return []
  const raw = daily.value.map(d => [d.date, d.steps] as [string, number | null])
  return [{ name: "Steps (30d avg)", data: rolling(raw), color: "#1D5CE5", smooth: true }]
})

const sleepSeries = computed(() => {
  if (!sleep.value?.length) return []
  const raw = sleep.value.map(d => [d.date, d.total_sleep_min != null ? +(d.total_sleep_min / 60).toFixed(2) : null] as [string, number | null])
  return [{ name: "Sleep (30d avg)", data: rolling(raw), color: "#7C3AED", smooth: true }]
})

const ctlSeries = computed(() => {
  if (!load.value?.length) return []
  return [
    { name: "CTL (Fitness)",  data: load.value.map(d => [d.date, d.ctl] as [string, number | null]), color: "#3B82F6", smooth: true },
    { name: "ATL (Fatigue)", data: load.value.map(d => [d.date, d.atl] as [string, number | null]), color: "#EF4444", smooth: true },
  ]
})

const weightSeries = computed(() => {
  if (!weight.value?.length) return []
  return [{ name: "Weight", data: weight.value.map(d => [d.date, kgToLbs(d.weight_kg)] as [string, number | null]), color: "#10B981", smooth: true }]
})

const energySeries = computed(() => {
  if (!daily.value?.length) return []
  return [
    { name: "Body Battery", data: daily.value.map(d => [d.date, d.body_battery_max] as [string, number | null]), color: "#16A34A", smooth: true },
    { name: "Stress",       data: daily.value.map(d => [d.date, d.stress_avg]       as [string, number | null]), color: "#D97706", smooth: true },
  ]
})

const vo2Series = computed(() => {
  if (!vo2Points.value.length) return []
  return [{
    name: "VO₂max (Garmin)",
    data: vo2Points.value.map(p => [p.date, p.vo2max] as [string, number]),
    color: "#10B981",
    smooth: false,
  }]
})

// Fitness age from VO2max: Cooper Institute norms interpolation (simplified linear)
// Fitness age ≈ chronological age adjusted by deviation from population mean VO2max
function fitnessAgeFromVo2(vo2: number, age: number): number {
  // Approximate: every 3.5 ml/kg/min above average reduces fitness age by ~5 years
  // Population mean VO2max for males declines ~0.46/yr from ~49 at 20
  const popMean = Math.max(20, 49 - 0.46 * (age - 20))
  const delta = (vo2 - popMean) / 3.5 * 5
  return Math.round(Math.max(18, age - delta))
}

const fitnessAgeSeries = computed(() => {
  if (!vo2Points.value.length || athleteAge.value == null) return []
  const age = athleteAge.value
  return [{
    name: "Fitness Age",
    data: vo2Points.value.map(p => {
      const fa = fitnessAgeFromVo2(p.vo2max, age)
      return [p.date, fa] as [string, number]
    }),
    color: "#3B82F6",
    smooth: false,
  }]
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
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
