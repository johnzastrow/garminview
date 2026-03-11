<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Correlation Explorer</h1>
        <p class="page-sub">Statistical relationships between health & fitness metrics</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Period</span>
      <DateRangePicker />
      <span class="range-note">Correlations are computed from all available data by the analysis engine</span>
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading correlations…</span></div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

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

interface CorrRow { metric_a: string; metric_b: string; r_pearson: number; p_value: number }

const loading = ref(true)
const error = ref<string | null>(null)
const rows = ref<CorrRow[]>([])
const minR = ref(0.3)
const maxP = ref(0.05)
const sort = ref<"r" | "p">("r")

onMounted(async () => {
  try {
    const r = await api.get("/assessments/correlations/matrix")
    rows.value = (r.data.correlations ?? []) as CorrRow[]
  } catch (e: any) {
    error.value = e?.message ?? "Failed to load correlations"
  } finally {
    loading.value = false
  }
})

function sortBy(key: "r" | "p") { sort.value = key }

const filtered = computed(() => {
  let out = rows.value.filter(r => Math.abs(r.r_pearson) >= minR.value && r.p_value <= maxP.value)
  if (sort.value === "r") out = [...out].sort((a, b) => Math.abs(b.r_pearson) - Math.abs(a.r_pearson))
  else out = [...out].sort((a, b) => a.p_value - b.p_value)
  return out
})

const heatmapRows = computed(() =>
  [...rows.value].sort((a, b) => Math.abs(b.r_pearson) - Math.abs(a.r_pearson)).slice(0, 20)
)

function fmt(s: string) { return s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) }
function shortFmt(s: string) { return s.split("_").map(w => w[0]).join("").toUpperCase() }

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
function pClass(p: number): string { return p < 0.05 ? "sig" : "nonsig" }

function barColor(r: number): string {
  return r >= 0 ? "#3B82F6" : "#EF4444"
}
function heatColor(r: number): string {
  const a = Math.abs(r)
  if (r >= 0) return `rgba(59,130,246,${0.15 + a * 0.7})`
  return `rgba(239,68,68,${0.15 + a * 0.7})`
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }
.range-note { font-size: 0.75rem; color: var(--muted); font-style: italic; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: -6px 0 10px; line-height: 1.5; }

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
.empty-state svg { width: 48px; height: 48px; opacity: 0.4; }
.empty-state h2 { font-size: 1.1rem; font-weight: 700; color: var(--text); }
.empty-state p { font-size: 0.88rem; }
.empty-state a { color: var(--accent); text-decoration: underline; }
</style>
