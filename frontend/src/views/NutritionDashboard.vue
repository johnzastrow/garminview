<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Nutrition</h1>
        <p class="page-sub">MyFitnessPal import — calories, macros, energy balance</p>
      </div>
    </header>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading data…</span></div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="nutrition.length">
      <div class="stat-grid">
        <MetricCard label="Calories In" :value="latest?.calories_in" unit="kcal" :spark-data="spark('calories_in')" color="#3B82F6" />
        <MetricCard label="Protein" :value="latest?.protein_g ? Math.round(latest.protein_g) : null" unit="g" :spark-data="spark('protein_g')" color="#10B981" />
        <MetricCard label="Carbs" :value="latest?.carbs_g ? Math.round(latest.carbs_g) : null" unit="g" :spark-data="spark('carbs_g')" color="#F59E0B" />
        <MetricCard label="Fat" :value="latest?.fat_g ? Math.round(latest.fat_g) : null" unit="g" :spark-data="spark('fat_g')" color="#EF4444" />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Energy Balance (Calories In vs. Out)</h2>
          <p class="chart-desc">Daily energy balance = calories consumed (from MyFitnessPal) minus calories burned (from Garmin). A sustained deficit drives fat loss; a surplus supports muscle building. A deficit of ~500 kcal/day yields approximately 1 lb fat loss per week.</p>
          <TimeSeriesChart v-if="energySeries.length" :series="energySeries" y-axis-label="kcal" />
          <p v-else class="empty">No energy balance data. Ensure Garmin daily summaries are synced alongside MFP data.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Macros (Protein / Carbs / Fat)</h2>
          <p class="chart-desc">Daily breakdown of calories from protein, carbohydrates, and fat. Protein (4 kcal/g) is critical for muscle repair and satiety; target 0.7–1.0 g/lb body weight for athletes. Carbohydrates fuel high-intensity exercise; fat supports hormonal health.</p>
          <StackedBarChart
            v-if="nutrition.length"
            :categories="nutrition.map(d => d.date)"
            :series="macroSeries"
            y-axis-label="g"
          />
          <p v-else class="empty">No macro data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Calorie Intake Trend</h2>
          <p class="chart-desc">Daily calorie intake from your MyFitnessPal food diary. Day-to-day variation is normal; focus on the weekly average. Consistent logging is more valuable than perfect accuracy.</p>
          <TimeSeriesChart v-if="calorieSeries.length" :series="calorieSeries" y-axis-label="kcal" />
          <p v-else class="empty">No calorie data in range.</p>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">
      <p>No MFP nutrition data found. Export your data from MyFitnessPal (Settings → Export Data), unzip, and place the CSV files in the configured <code>mfp_data_dir</code>, then run a sync.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import StackedBarChart from "@/components/charts/StackedBarChart.vue"
import { useMetricData } from "@/composables/useMetricData"

interface NutritionRow {
  date: string
  calories_in: number | null
  carbs_g: number | null
  fat_g: number | null
  protein_g: number | null
  sodium_mg: number | null
  sugar_g: number | null
  fiber_g: number | null
}

interface EnergyRow {
  date: string
  calories_in: number | null
  calories_out: number | null
  energy_balance: number | null
}

const { data: nutrition, loading: nLoading, error: nError } = useMetricData<NutritionRow[]>("/nutrition/daily")
const { data: balance, loading: bLoading, error: bError } = useMetricData<EnergyRow[]>("/nutrition/energy-balance")

const loading = computed(() => nLoading.value || bLoading.value)
const error = computed(() => nError.value || bError.value)
const latest = computed(() => nutrition.value?.[nutrition.value.length - 1] ?? null)

function spark(key: keyof NutritionRow) {
  return nutrition.value?.map((d) => d[key] as number | null) ?? []
}

const calorieSeries = computed(() => {
  if (!nutrition.value?.length) return []
  return [{ name: "Calories In", data: nutrition.value.map(d => [d.date, d.calories_in] as [string, number | null]), color: "#3B82F6", smooth: true }]
})

const energySeries = computed(() => {
  if (!balance.value?.length) return []
  const rows = balance.value.filter(r => r.calories_in != null || r.calories_out != null)
  if (!rows.length) return []
  return [
    { name: "Calories In", data: rows.map(r => [r.date, r.calories_in] as [string, number | null]), color: "#3B82F6", smooth: true },
    { name: "Calories Out", data: rows.map(r => [r.date, r.calories_out] as [string, number | null]), color: "#F59E0B", smooth: true },
    { name: "Balance", data: rows.map(r => [r.date, r.energy_balance] as [string, number | null]), color: "#10B981", smooth: true },
  ]
})

const macroSeries = computed(() => [
  { name: "Protein", data: (nutrition.value ?? []).map(d => Math.round(d.protein_g ?? 0)), color: "#10B981" },
  { name: "Carbs",   data: (nutrition.value ?? []).map(d => Math.round(d.carbs_g ?? 0)),   color: "#F59E0B" },
  { name: "Fat",     data: (nutrition.value ?? []).map(d => Math.round(d.fat_g ?? 0)),     color: "#EF4444" },
])
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
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 4px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
.empty-state { padding: 48px 0; color: var(--muted); font-size: 0.9rem; }
.empty-state code { background: var(--bg); padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }
</style>
