<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Correlation Explorer</h1>
        <p class="page-sub">Statistical relationships between health &amp; fitness metrics</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Period</span>
      <DateRangePicker />
    </div>

    <!-- ── Wellness Trends ────────────────────────────── -->
    <section class="wellness-section">
      <h2 class="section-heading">Wellness Over Time</h2>
      <p class="chart-desc">
        Resting HR and weight are your anchor metrics — both respond to sleep, stress, and training load.
        Use the date range above to zoom in on a specific period.
      </p>

      <div v-if="wellnessLoading" class="loading">
        <div class="spinner"></div><span>Loading wellness data…</span>
      </div>

      <template v-else-if="merged.length >= 3">
        <!-- Two charts side by side -->
        <div class="charts-grid">
          <div class="chart-card">
            <div class="chart-header">
              <span class="chart-title">Resting HR &amp; Weight</span>
              <span v-if="rhrWeightR !== null" class="r-chip" :class="rChipClass(rhrWeightR)">
                r&nbsp;=&nbsp;{{ rhrWeightR.toFixed(2) }}
              </span>
              <span class="chart-note">solid = RHR (left) · dashed = weight (right)</span>
            </div>
            <DualAxisChart :left="rhrAxis" :right="weightAxis" height="260px" />
          </div>

          <div class="chart-card">
            <div class="chart-header">
              <span class="chart-title">All signals (normalized 0–100)</span>
              <span class="chart-note">each metric scaled to its own range · hover for actual values</span>
            </div>
            <NormalizedTrendsChart :series="normalizedSeries" height="260px" />
          </div>
        </div>

        <!-- Key relationship cards -->
        <div class="rel-grid">
          <div
            v-for="rel in keyRelationships"
            :key="rel.key"
            class="rel-card"
          >
            <div class="rel-metrics">
              <span class="rel-m">{{ rel.labelA }}</span>
              <span class="rel-sep">↔</span>
              <span class="rel-m">{{ rel.labelB }}</span>
            </div>
            <template v-if="rel.r !== null">
              <div class="rel-bar-row">
                <span class="rel-r-bar-wrap">
                  <span
                    class="rel-r-bar"
                    :style="{ width: Math.abs(rel.r) * 100 + '%', background: rel.r >= 0 ? '#3B82F6' : '#EF4444' }"
                  ></span>
                </span>
                <span class="rel-r-num" :class="rel.r >= 0 ? 'pos' : 'neg'">{{ rel.r >= 0 ? '+' : '' }}{{ rel.r.toFixed(2) }}</span>
              </div>
              <div class="rel-footer">
                <span class="badge" :class="strengthClass(rel.r)">{{ strength(rel.r) }}</span>
                <span class="rel-dir">{{ rel.r >= 0 ? '↑↑ positive' : '↑↓ inverse' }}</span>
                <span class="rel-n">n={{ rel.n }}</span>
              </div>
            </template>
            <div v-else class="rel-insufficient">insufficient data</div>
          </div>
        </div>
      </template>

      <div v-else class="empty-state small">
        <p>No wellness data in this date range. Try extending the period or syncing from the <a href="/admin">Admin</a> panel.</p>
      </div>
    </section>

    <!-- ── Pre-computed Correlation Matrix ───────────── -->
    <div class="divider-row">
      <span class="divider-label">Pre-computed Correlation Matrix</span>
      <span class="divider-note">Computed by the analysis engine across all historical data</span>
    </div>

    <div v-if="matrixLoading" class="loading"><div class="spinner"></div><span>Loading correlations…</span></div>
    <div v-else-if="matrixError" class="error-msg">{{ matrixError }}</div>

    <template v-else-if="rows.length === 0">
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 12l5-5 5 5M7 17l5-5 5 5"/></svg>
        <h2>No correlations computed yet</h2>
        <p>Run a sync from the <a href="/admin">Admin</a> panel to compute correlations between your metrics.</p>
      </div>
    </template>

    <template v-else>
      <div class="controls">
        <label class="filter-label">
          Min |r|
          <input type="range" min="0" max="1" step="0.05" v-model.number="minR" class="slider" />
          <span class="slider-val">{{ minR.toFixed(2) }}</span>
        </label>
        <label class="filter-label">
          Max p-value
          <input type="range" min="0.01" max="1" step="0.01" v-model.number="maxP" class="slider" />
          <span class="slider-val">{{ maxP.toFixed(2) }}</span>
        </label>
        <span class="result-count">{{ filtered.length }} pairs</span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Metric A</th>
              <th>Metric B</th>
              <th @click="sortBy('r')" class="sortable">r <span class="sort-icon">{{ sort === 'r' ? '↓' : '·' }}</span></th>
              <th @click="sortBy('p')" class="sortable">p-value <span class="sort-icon">{{ sort === 'p' ? '↑' : '·' }}</span></th>
              <th>Strength</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filtered" :key="row.metric_a + row.metric_b">
              <td class="metric-name">{{ fmt(row.metric_a) }}</td>
              <td class="metric-name">{{ fmt(row.metric_b) }}</td>
              <td class="r-val">
                <span class="r-bar-wrap">
                  <span class="r-bar" :style="{ width: Math.abs(row.r_pearson) * 100 + '%', background: barColor(row.r_pearson) }"></span>
                  <span class="r-num">{{ row.r_pearson.toFixed(3) }}</span>
                </span>
              </td>
              <td :class="pClass(row.p_value)">{{ row.p_value < 0.001 ? '<0.001' : row.p_value.toFixed(3) }}</td>
              <td><span class="badge" :class="strengthClass(row.r_pearson)">{{ strength(row.r_pearson) }}</span></td>
              <td class="dir">{{ row.r_pearson >= 0 ? '↑ positive' : '↓ negative' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="heatmap-section">
        <h2 class="section-title">Top Correlations Heatmap</h2>
        <p class="chart-desc">Color intensity shows correlation strength. Blue = positive relationship (both metrics rise together), red = inverse relationship (one rises as the other falls). Only statistically significant pairs (p &lt; 0.05) with |r| ≥ 0.3 are shown by default.</p>
        <div class="heatmap">
          <div v-for="row in heatmapRows" :key="row.metric_a + row.metric_b" class="heat-cell"
               :style="{ background: heatColor(row.r_pearson) }"
               :title="`${fmt(row.metric_a)} ↔ ${fmt(row.metric_b)}: r=${row.r_pearson.toFixed(3)}`">
            <span class="heat-label">{{ shortFmt(row.metric_a) }}</span>
            <span class="heat-sep">↔</span>
            <span class="heat-label">{{ shortFmt(row.metric_b) }}</span>
            <span class="heat-r">{{ row.r_pearson.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { api } from "@/api/client"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import DualAxisChart from "@/components/charts/DualAxisChart.vue"
import NormalizedTrendsChart from "@/components/charts/NormalizedTrendsChart.vue"
import { useMetricData } from "@/composables/useMetricData"
import type { NormSeries } from "@/components/charts/NormalizedTrendsChart.vue"

// ── Types ────────────────────────────────────────────────────────────────────

interface DailySummary {
  date: string
  hr_resting: number | null
  sleep_score: number | null
  stress_avg: number | null
  body_battery_max: number | null
  spo2_avg: number | null
  intensity_min_moderate: number | null
  intensity_min_vigorous: number | null
}

interface WeightRecord {
  date: string
  weight_kg: number | null
}

interface CorrRow { metric_a: string; metric_b: string; r_pearson: number; p_value: number }

interface MergedDay {
  date: string
  rhr: number | null
  weight_kg: number | null
  sleep_score: number | null
  stress_avg: number | null
  body_battery: number | null
  spo2: number | null
  active_min: number | null
}

type MetricKey = keyof Omit<MergedDay, "date">

// ── Wellness data ─────────────────────────────────────────────────────────────

const { data: dailyData, loading: dailyLoading } = useMetricData<DailySummary[]>("/health/daily")
const { data: weightData, loading: weightLoading } = useMetricData<WeightRecord[]>("/body/weight")

const wellnessLoading = computed(() => dailyLoading.value || weightLoading.value)

const merged = computed<MergedDay[]>(() => {
  if (!dailyData.value) return []
  const byDate = new Map<string, number | null>()
  for (const w of weightData.value ?? []) {
    if (w.weight_kg != null) byDate.set(String(w.date), w.weight_kg)
  }
  return dailyData.value.map((d) => ({
    date: String(d.date),
    rhr: d.hr_resting ?? null,
    weight_kg: byDate.get(String(d.date)) ?? null,
    sleep_score: d.sleep_score ?? null,
    stress_avg: d.stress_avg ?? null,
    body_battery: d.body_battery_max ?? null,
    spo2: d.spo2_avg ?? null,
    active_min:
      (d.intensity_min_moderate ?? 0) + (d.intensity_min_vigorous ?? 0) * 2 || null,
  }))
})

// ── Chart series ──────────────────────────────────────────────────────────────

const rhrAxis = computed(() => ({
  name: "Resting HR",
  data: merged.value.map((d) => [d.date, d.rhr] as [string, number | null]),
  color: "#EF4444",
  unit: "bpm",
}))

const weightAxis = computed(() => ({
  name: "Weight",
  data: merged.value.map((d) => [d.date, d.weight_kg] as [string, number | null]),
  color: "#6366F1",
  unit: "kg",
}))

const normalizedSeries = computed<NormSeries[]>(() => [
  {
    name: "Resting HR",
    data: merged.value.map((d) => [d.date, d.rhr] as [string, number | null]),
    color: "#EF4444",
    unit: "bpm",
  },
  {
    name: "Weight",
    data: merged.value.map((d) => [d.date, d.weight_kg] as [string, number | null]),
    color: "#6366F1",
    unit: "kg",
  },
  {
    name: "Sleep Score",
    data: merged.value.map((d) => [d.date, d.sleep_score] as [string, number | null]),
    color: "#8B5CF6",
  },
  {
    name: "Body Battery",
    data: merged.value.map((d) => [d.date, d.body_battery] as [string, number | null]),
    color: "#22C55E",
  },
  {
    name: "Stress",
    data: merged.value.map((d) => [d.date, d.stress_avg] as [string, number | null]),
    color: "#F59E0B",
  },
  {
    name: "SpO₂",
    data: merged.value.map((d) => [d.date, d.spo2] as [string, number | null]),
    color: "#06B6D4",
    unit: "%",
  },
])

// ── Pearson r ─────────────────────────────────────────────────────────────────

function pearsonR(xs: number[], ys: number[]): number | null {
  const n = xs.length
  if (n < 5) return null
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  const num = xs.reduce((s, x, i) => s + (x - mx) * (ys[i]! - my), 0)
  const den = Math.sqrt(
    xs.reduce((s, x) => s + (x - mx) ** 2, 0) *
    ys.reduce((s, y) => s + (y - my) ** 2, 0)
  )
  return den === 0 ? null : num / den
}

function computeR(ka: MetricKey, kb: MetricKey) {
  const pairs = merged.value.filter((d) => d[ka] != null && d[kb] != null)
  const xs = pairs.map((d) => d[ka] as number)
  const ys = pairs.map((d) => d[kb] as number)
  return { r: pearsonR(xs, ys), n: pairs.length }
}

const rhrWeightR = computed(() => computeR("rhr", "weight_kg").r)

interface RelCard {
  key: string
  labelA: string
  labelB: string
  r: number | null
  n: number
}

const keyRelationships = computed<RelCard[]>(() => {
  const pairs: [MetricKey, MetricKey, string, string][] = [
    ["rhr", "weight_kg", "Resting HR", "Weight"],
    ["rhr", "sleep_score", "Resting HR", "Sleep Score"],
    ["rhr", "stress_avg", "Resting HR", "Stress"],
    ["rhr", "body_battery", "Resting HR", "Body Battery"],
    ["sleep_score", "stress_avg", "Sleep Score", "Stress"],
    ["sleep_score", "body_battery", "Sleep Score", "Body Battery"],
    ["body_battery", "stress_avg", "Body Battery", "Stress"],
    ["weight_kg", "sleep_score", "Weight", "Sleep Score"],
  ]
  return pairs
    .map(([ka, kb, la, lb]) => {
      const { r, n } = computeR(ka, kb)
      return { key: `${ka}-${kb}`, labelA: la, labelB: lb, r, n }
    })
    .filter((c) => c.n >= 5)
    .sort((a, b) => Math.abs(b.r ?? 0) - Math.abs(a.r ?? 0))
})

// ── Pre-computed matrix ───────────────────────────────────────────────────────

const matrixLoading = ref(true)
const matrixError = ref<string | null>(null)
const rows = ref<CorrRow[]>([])
const minR = ref(0.3)
const maxP = ref(0.05)
const sort = ref<"r" | "p">("r")

onMounted(async () => {
  try {
    const r = await api.get("/assessments/correlations/matrix")
    rows.value = (r.data.correlations ?? []) as CorrRow[]
  } catch (e: any) {
    matrixError.value = e?.message ?? "Failed to load correlations"
  } finally {
    matrixLoading.value = false
  }
})

function sortBy(key: "r" | "p") { sort.value = key }

const filtered = computed(() => {
  let out = rows.value.filter((r) => Math.abs(r.r_pearson) >= minR.value && r.p_value <= maxP.value)
  if (sort.value === "r") out = [...out].sort((a, b) => Math.abs(b.r_pearson) - Math.abs(a.r_pearson))
  else out = [...out].sort((a, b) => a.p_value - b.p_value)
  return out
})

const heatmapRows = computed(() =>
  [...rows.value].sort((a, b) => Math.abs(b.r_pearson) - Math.abs(a.r_pearson)).slice(0, 20)
)

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(s: string) { return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }
function shortFmt(s: string) { return s.split("_").map((w) => w[0]).join("").toUpperCase() }

function strength(r: number): string {
  const a = Math.abs(r)
  if (a >= 0.7) return "Strong"
  if (a >= 0.4) return "Moderate"
  if (a >= 0.2) return "Weak"
  return "Negligible"
}
function strengthClass(r: number): string {
  const a = Math.abs(r)
  if (a >= 0.7) return "strong"
  if (a >= 0.4) return "moderate"
  if (a >= 0.2) return "weak"
  return "negligible"
}
function rChipClass(r: number): string {
  const a = Math.abs(r)
  if (a >= 0.5) return r >= 0 ? "chip-strong-pos" : "chip-strong-neg"
  if (a >= 0.2) return r >= 0 ? "chip-mod-pos" : "chip-mod-neg"
  return "chip-weak"
}
function pClass(p: number): string { return p < 0.05 ? "sig" : "nonsig" }
function barColor(r: number): string { return r >= 0 ? "#3B82F6" : "#EF4444" }
function heatColor(r: number): string {
  const a = Math.abs(r)
  if (r >= 0) return `rgba(59,130,246,${0.15 + a * 0.7})`
  return `rgba(239,68,68,${0.15 + a * 0.7})`
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1200px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
.range-row { display: flex; align-items: center; gap: 10px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: -6px 0 10px; line-height: 1.5; }

/* ── Wellness section ── */
.wellness-section { display: flex; flex-direction: column; gap: 16px; }
.section-heading { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); }

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 800px) { .charts-grid { grid-template-columns: 1fr; } }

.chart-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chart-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chart-title { font-size: 0.82rem; font-weight: 700; color: var(--text); }
.chart-note { font-size: 0.72rem; color: var(--muted); margin-left: auto; }
.r-chip {
  font-size: 0.73rem; font-weight: 700; font-family: monospace;
  padding: 2px 7px; border-radius: 999px;
}
.chip-strong-pos { background: #DBEAFE; color: #1D4ED8; }
.chip-strong-neg { background: #FEE2E2; color: #B91C1C; }
.chip-mod-pos   { background: #EFF6FF; color: #3B82F6; }
.chip-mod-neg   { background: #FEF2F2; color: #EF4444; }
.chip-weak      { background: var(--border); color: var(--muted); }

/* ── Relationship cards ── */
.rel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.rel-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rel-metrics { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.rel-m { font-size: 0.78rem; font-weight: 700; color: var(--text); }
.rel-sep { font-size: 0.75rem; color: var(--muted); }
.rel-bar-row { display: flex; align-items: center; gap: 6px; }
.rel-r-bar-wrap {
  flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;
}
.rel-r-bar { display: block; height: 100%; border-radius: 3px; transition: width 0.3s; }
.rel-r-num { font-family: monospace; font-size: 0.82rem; font-weight: 700; min-width: 38px; text-align: right; }
.rel-r-num.pos { color: #3B82F6; }
.rel-r-num.neg { color: #EF4444; }
.rel-footer { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.rel-dir { font-size: 0.72rem; color: var(--muted); }
.rel-n { font-size: 0.7rem; color: var(--muted); margin-left: auto; font-family: monospace; }
.rel-insufficient { font-size: 0.72rem; color: var(--muted); font-style: italic; }

/* ── Divider ── */
.divider-row {
  display: flex; align-items: baseline; gap: 10px;
  border-top: 1px solid var(--border); padding-top: 20px;
}
.divider-label { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); }
.divider-note { font-size: 0.72rem; color: var(--muted); font-style: italic; }

/* ── Matrix controls / table / heatmap (unchanged) ── */
.controls { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 18px; }
.filter-label { display: flex; align-items: center; gap: 8px; font-size: 0.82rem; font-weight: 600; color: var(--muted); }
.slider { width: 100px; }
.slider-val { font-family: monospace; font-size: 0.85rem; color: var(--text); min-width: 36px; }
.result-count { margin-left: auto; font-size: 0.8rem; color: var(--muted); }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th { padding: 10px 12px; text-align: left; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); border-bottom: 2px solid var(--border); white-space: nowrap; }
td { padding: 9px 12px; border-bottom: 1px solid var(--border); }
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: var(--text); }
.sort-icon { font-size: 0.7rem; }

.metric-name { font-weight: 500; color: var(--text); }
.r-val { }
.r-bar-wrap { display: flex; align-items: center; gap: 6px; }
.r-bar { height: 8px; border-radius: 4px; min-width: 2px; flex-shrink: 0; }
.r-num { font-family: monospace; font-size: 0.83rem; color: var(--text); min-width: 48px; }
.sig { color: #16A34A; font-family: monospace; font-size: 0.82rem; }
.nonsig { color: var(--muted); font-family: monospace; font-size: 0.82rem; }
.dir { font-size: 0.8rem; color: var(--muted); }

.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.73rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.badge.strong { background: #DCFCE7; color: #15803D; }
.badge.moderate { background: #DBEAFE; color: #1D4ED8; }
.badge.weak { background: #FEF9C3; color: #A16207; }
.badge.negligible { background: var(--border); color: var(--muted); }

.section-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.heatmap-section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }
.heatmap { display: flex; flex-wrap: wrap; gap: 8px; }
.heat-cell { display: flex; align-items: center; gap: 4px; padding: 6px 10px; border-radius: 6px; font-size: 0.75rem; cursor: default; }
.heat-label { font-weight: 600; color: var(--text); }
.heat-sep { color: var(--muted); }
.heat-r { font-family: monospace; font-weight: 700; color: var(--text); }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }

.empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 60px 0; color: var(--muted); text-align: center; }
.empty-state.small { padding: 20px 0; }
.empty-state svg { width: 48px; height: 48px; opacity: 0.4; }
.empty-state h2 { font-size: 1.1rem; font-weight: 700; color: var(--text); }
.empty-state p { font-size: 0.88rem; }
.empty-state a { color: var(--accent); text-decoration: underline; }
</style>
