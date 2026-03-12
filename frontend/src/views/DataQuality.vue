<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Data Quality</h1>
        <p class="page-sub">Coverage, completeness, and integrity of your Garmin data</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Showing</span>
      <DateRangePicker />
    </div>

    <div v-if="anyLoading" class="loading"><div class="spinner"></div><span>Analyzing data quality…</span></div>
    <div v-else-if="anyError" class="error-msg">{{ anyError }}</div>

    <template v-else>
      <!-- Coverage summary cards -->
      <div class="metric-row">
        <div class="metric-card">
          <span class="metric-label">Days with Steps</span>
          <span class="metric-value">{{ coverageSummary.stepsdays }}</span>
          <span class="metric-unit">/ {{ coverageSummary.totaldays }} days</span>
          <div class="cover-bar"><div class="cover-fill steps" :style="{ width: pct(coverageSummary.stepsdays, coverageSummary.totaldays) }"></div></div>
        </div>
        <div class="metric-card">
          <span class="metric-label">Days with Sleep</span>
          <span class="metric-value">{{ coverageSummary.sleepdays }}</span>
          <span class="metric-unit">/ {{ coverageSummary.totaldays }} days</span>
          <div class="cover-bar"><div class="cover-fill sleep" :style="{ width: pct(coverageSummary.sleepdays, coverageSummary.totaldays) }"></div></div>
        </div>
        <div class="metric-card">
          <span class="metric-label">Days with HR</span>
          <span class="metric-value">{{ coverageSummary.hrdays }}</span>
          <span class="metric-unit">/ {{ coverageSummary.totaldays }} days</span>
          <div class="cover-bar"><div class="cover-fill hr" :style="{ width: pct(coverageSummary.hrdays, coverageSummary.totaldays) }"></div></div>
        </div>
        <div class="metric-card">
          <span class="metric-label">Quality Flags</span>
          <span class="metric-value" :class="{ 'flag-red': qualityData.total_flags > 0 }">{{ qualityData.total_flags }}</span>
          <span class="metric-unit">flagged records</span>
          <div class="cover-bar"><div class="cover-fill flags" :style="{ width: qualityData.total_flags > 0 ? '100%' : '0%' }"></div></div>
        </div>
      </div>

      <!-- Data quality flags -->
      <div class="panel">
        <h2 class="section-title">Quality Flags</h2>
        <p class="chart-desc">Data quality flags are automatically raised when the analysis engine detects anomalies — missing values for expected dates, physiological outliers (e.g. resting HR > 120), or implausible sensor readings. Review flagged dates in the source FIT files if a pattern is detected.</p>
        <div v-if="qualityData.total_flags === 0" class="empty-inline">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          No quality flags found — data looks complete.
        </div>
        <table v-else>
          <thead><tr><th>Date</th><th>Metric</th><th>Flag Type</th></tr></thead>
          <tbody>
            <tr v-for="(f, i) in qualityData.flags" :key="i">
              <td>{{ f.date }}</td>
              <td class="metric-name">{{ fmt(f.metric) }}</td>
              <td><span class="flag-badge" :class="f.flag_type">{{ fmt(f.flag_type) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="qualityData.total_flags > 50" class="truncation-note">
          Showing first 50 of {{ qualityData.total_flags }} flags.
        </p>
      </div>

      <!-- Anomaly detection -->
      <div class="panel">
        <h2 class="section-title">Detected Anomalies</h2>
        <p class="chart-desc">Probable sensor spikes and physiologically implausible readings detected across your data. Excluded anomalies are skipped in athlete metric calculations (e.g. measured max HR). Toggle any row to exclude or re-include it.</p>
        <div v-if="anomaliesLoading" class="loading" style="padding:12px 0"><div class="spinner"></div><span>Scanning for anomalies…</span></div>
        <div v-else-if="anomalies.length === 0" class="empty-inline">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          No anomalies detected in your data.
        </div>
        <table v-else class="anomaly-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Source</th>
              <th>Metric</th>
              <th>Value</th>
              <th>Severity</th>
              <th>Message</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in anomalies" :key="a.anomaly_id" :class="{ 'row-excluded': a.excluded }">
              <td class="col-date">{{ a.date }}</td>
              <td class="col-source">{{ fmtTable(a.source_table) }}</td>
              <td class="col-metric">{{ fmt(a.metric) }}</td>
              <td class="col-value">{{ a.value.toLocaleString() }}</td>
              <td>
                <span class="sev-badge" :class="a.severity">{{ a.severity }}</span>
              </td>
              <td class="col-message">{{ a.message }}</td>
              <td class="col-action">
                <button
                  class="excl-btn"
                  :class="{ active: a.excluded, loading: togglingIds.has(a.anomaly_id) }"
                  :disabled="togglingIds.has(a.anomaly_id)"
                  @click="toggleExclusion(a)"
                  :title="a.excluded ? 'Click to re-include in calculations' : 'Click to exclude from calculations'"
                >
                  {{ a.excluded ? "Excluded" : "Include" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="truncation-note" v-if="anomalies.length >= 100">
          Showing up to 100 anomalies. Resolve high-severity items first.
        </p>
      </div>

      <!-- Daily coverage chart -->
      <div class="panel">
        <h2 class="section-title">Daily Coverage (Steps, Sleep, RHR)</h2>
        <p class="chart-desc">Each square represents one day in the selected range. Green = all three key metrics (steps, resting HR, and sleep) are recorded. Amber = at least one metric is present. Gray = no data. Gaps in coverage are usually caused by not wearing the device or a sync issue.</p>
        <div v-if="coverageChart.dates.length === 0" class="empty-inline">No daily data in range.</div>
        <div v-else class="coverage-grid">
          <div v-for="(d, i) in coverageChart.dates" :key="d" class="day-cell"
               :class="coverageChart.classes[i]"
               :title="`${d}: ${coverageChart.labels[i]}`">
          </div>
        </div>
        <div class="legend">
          <span class="leg-item"><span class="leg-dot full"></span>Full coverage</span>
          <span class="leg-item"><span class="leg-dot partial"></span>Partial</span>
          <span class="leg-item"><span class="leg-dot missing"></span>Missing</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import { useMetricData } from "@/composables/useMetricData"
import { api } from "@/api/client"

interface DailySummary { date: string; steps: number | null; hr_resting: number | null }
interface SleepRow { date: string; total_sleep_min: number | null }
interface QualityFlag { date: string; metric: string; flag_type: string }
interface QualityResponse { total_flags: number; flags: QualityFlag[] }

interface Anomaly {
  anomaly_id: string
  source_table: string
  record_id: string
  date: string
  metric: string
  value: number
  anomaly_type: string
  severity: string
  message: string
  excluded: boolean
  flag_id: number | null
}

const { data: daily,   loading: l1, error: e1 } = useMetricData<DailySummary[]>("/health/daily")
const { data: sleep,   loading: l2, error: e2 } = useMetricData<SleepRow[]>("/health/sleep")
const { data: quality, loading: l3, error: e3 } = useMetricData<QualityResponse>("/assessments/data-quality/completeness")

const anomalies = ref<Anomaly[]>([])
const anomaliesLoading = ref(false)
const togglingIds = ref<Set<string>>(new Set())

async function loadAnomalies() {
  anomaliesLoading.value = true
  try {
    const r = await api.get("/admin/anomalies")
    anomalies.value = r.data.anomalies ?? []
  } catch {
    anomalies.value = []
  } finally {
    anomaliesLoading.value = false
  }
}

async function toggleExclusion(a: Anomaly) {
  if (togglingIds.value.has(a.anomaly_id)) return
  togglingIds.value = new Set([...togglingIds.value, a.anomaly_id])
  try {
    if (a.excluded) {
      await api.delete("/admin/anomalies/exclude", {
        params: { source_table: a.source_table, record_id: a.record_id },
      })
      a.excluded = false
      a.flag_id = null
    } else {
      const r = await api.post("/admin/anomalies/exclude", null, {
        params: {
          source_table: a.source_table,
          record_id: a.record_id,
          date: a.date,
          metric: a.metric,
          value: String(a.value),
          message: a.message,
        },
      })
      a.excluded = true
      a.flag_id = r.data.id
    }
  } finally {
    const next = new Set(togglingIds.value)
    next.delete(a.anomaly_id)
    togglingIds.value = next
  }
}

onMounted(loadAnomalies)

const anyLoading = computed(() => l1.value || l2.value || l3.value)
const anyError   = computed(() => e1.value || e2.value || e3.value)

const qualityData = computed<QualityResponse>(() =>
  quality.value ?? { total_flags: 0, flags: [] }
)

const coverageSummary = computed(() => {
  const ds = daily.value ?? []
  const sl = sleep.value ?? []
  const sleepDates = new Set(sl.map(r => r.date))
  const totaldays = ds.length
  const stepsdays = ds.filter(d => d.steps != null && d.steps > 0).length
  const hrdays    = ds.filter(d => d.hr_resting != null).length
  const sleepdays = ds.filter(d => sleepDates.has(d.date)).length
  return { totaldays, stepsdays, hrdays, sleepdays }
})

const coverageChart = computed(() => {
  const ds = daily.value ?? []
  const sl = sleep.value ?? []
  const sleepDates = new Set(sl.map(r => r.date))
  const dates: string[] = []
  const classes: string[] = []
  const labels: string[] = []
  for (const d of ds) {
    dates.push(d.date)
    const hasSteps   = d.steps != null && d.steps > 0
    const hasHR      = d.hr_resting != null
    const hasSleep   = sleepDates.has(d.date)
    const count      = [hasSteps, hasHR, hasSleep].filter(Boolean).length
    classes.push(count === 3 ? "full" : count > 0 ? "partial" : "missing")
    const parts = [hasSteps ? "steps" : "", hasHR ? "HR" : "", hasSleep ? "sleep" : ""].filter(Boolean)
    labels.push(parts.length ? parts.join(", ") : "no data")
  }
  return { dates, classes, labels }
})

function pct(n: number, total: number): string {
  if (!total) return "0%"
  return Math.round((n / total) * 100) + "%"
}

function fmt(s: string) { return s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) }
function fmtTable(t: string) {
  const map: Record<string, string> = {
    monitoring_heart_rate: "Monitoring HR",
    activities: "Activity",
    daily_summary: "Daily Summary",
  }
  return map[t] ?? fmt(t)
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }

.metric-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.metric-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; display: flex; flex-direction: column; gap: 2px; }
.metric-label { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
.metric-value { font-size: 2rem; font-weight: 800; color: var(--text); line-height: 1.1; }
.metric-value.flag-red { color: #DC2626; }
.metric-unit { font-size: 0.78rem; color: var(--muted); }
.cover-bar { height: 6px; background: var(--border); border-radius: 3px; margin-top: 8px; overflow: hidden; }
.cover-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
.cover-fill.steps { background: #3B82F6; }
.cover-fill.sleep { background: #7C3AED; }
.cover-fill.hr    { background: #E5341D; }
.cover-fill.flags { background: #DC2626; }

.section-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }
.panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }

table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th { padding: 8px 12px; text-align: left; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); border-bottom: 2px solid var(--border); }
td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
.metric-name { font-weight: 500; color: var(--text); }
.flag-badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; background: #FEF3C7; color: #D97706; }
.flag-badge.missing { background: #FEE2E2; color: #DC2626; }
.flag-badge.outlier { background: #EDE9FE; color: #7C3AED; }
.truncation-note { margin-top: 10px; font-size: 0.8rem; color: var(--muted); }

.coverage-grid { display: flex; flex-wrap: wrap; gap: 3px; }
.day-cell { width: 12px; height: 12px; border-radius: 2px; cursor: default; }
.day-cell.full    { background: #16A34A; }
.day-cell.partial { background: #FBBF24; }
.day-cell.missing { background: var(--border); }

.legend { display: flex; gap: 16px; margin-top: 12px; }
.leg-item { display: flex; align-items: center; gap: 5px; font-size: 0.78rem; color: var(--muted); }
.leg-dot { width: 10px; height: 10px; border-radius: 2px; }
.leg-dot.full    { background: #16A34A; }
.leg-dot.partial { background: #FBBF24; }
.leg-dot.missing { background: var(--border); }

.empty-inline { display: flex; align-items: center; gap: 8px; font-size: 0.87rem; color: var(--muted); padding: 12px 0; }
.empty-inline svg { width: 20px; height: 20px; color: #16A34A; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }

/* Anomaly table */
.anomaly-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.anomaly-table th { padding: 8px 10px; text-align: left; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); border-bottom: 2px solid var(--border); white-space: nowrap; }
.anomaly-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
.row-excluded td { opacity: 0.5; }
.col-date { white-space: nowrap; font-variant-numeric: tabular-nums; color: var(--muted); }
.col-source { white-space: nowrap; font-weight: 600; color: var(--text); }
.col-metric { white-space: nowrap; }
.col-value { white-space: nowrap; font-weight: 700; font-variant-numeric: tabular-nums; }
.col-message { max-width: 360px; line-height: 1.4; color: var(--muted); }
.col-action { white-space: nowrap; }

.sev-badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
.sev-badge.high   { background: #FEE2E2; color: #DC2626; }
.sev-badge.medium { background: #FEF3C7; color: #D97706; }
.sev-badge.low    { background: #DBEAFE; color: #2563EB; }

.excl-btn {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--muted);
  transition: background 0.12s, color 0.12s, opacity 0.12s;
}
.excl-btn:hover:not(:disabled) { background: var(--accent-light); color: var(--accent); border-color: var(--accent); }
.excl-btn.active { background: #FEE2E2; color: #DC2626; border-color: #FCA5A5; }
.excl-btn.active:hover:not(:disabled) { background: #FEF2F2; }
.excl-btn.loading { opacity: 0.5; cursor: wait; }
</style>
