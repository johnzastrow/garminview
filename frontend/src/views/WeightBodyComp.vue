<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Weight &amp; Body Composition</h1>
        <p class="page-sub">Weight and body fat trends</p>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading data…</span>
    </div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard
          label="Weight"
          :value="kgToLbs(latestWeight?.weight_kg)"
          :unit="WEIGHT_UNIT"
          :spark-data="weightSpark"
          color="#3B82F6"
        />
        <MetricCard
          label="Body Fat"
          :value="latestComp?.fat_pct != null ? +latestComp.fat_pct.toFixed(1) : null"
          unit="%"
          :spark-data="fatSpark"
          color="#F59E0B"
        />
        <MetricCard
          label="Muscle Mass"
          :value="kgToLbs(latestComp?.muscle_mass_kg)"
          :unit="WEIGHT_UNIT"
          :spark-data="muscleSpark"
          color="#10B981"
        />
        <MetricCard
          label="BMI"
          :value="latestComp?.bmi != null ? +latestComp.bmi.toFixed(1) : null"
          :spark-data="bmiSpark"
          color="#8B5CF6"
        />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Weight Trend</h2>
          <p class="chart-desc">Body weight over time in lbs. Weight fluctuates ±2–4 lbs daily due to hydration, food timing, and glycogen stores — focus on the 7-day rolling average trend rather than daily values. Sustainable fat loss is typically 1–2 lbs/week.</p>
          <TimeSeriesChart
            v-if="weightSeries.length"
            :series="weightSeries"
            y-axis-label="lbs"
          />
          <p v-else class="empty">No weight data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Body Fat %</h2>
          <p class="chart-desc">Body fat percentage estimated from bioimpedance or skinfold. Values below 20% for men and 28% for women are generally considered healthy for recreational athletes. Changes in body fat % are more meaningful than absolute weight changes.</p>
          <TimeSeriesChart
            v-if="fatSeries.length"
            :series="fatSeries"
            y-axis-label="%"
          />
          <p v-else class="empty">No body composition data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Muscle Mass</h2>
          <p class="chart-desc">Estimated lean muscle mass in lbs. Muscle mass tends to be stable or increase slowly with strength training; a decline may indicate loss of fitness or insufficient protein intake.</p>
          <TimeSeriesChart
            v-if="muscleSeries.length"
            :series="muscleSeries"
            y-axis-label="lbs"
          />
          <p v-else class="empty">No muscle mass data in range.</p>
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
import { useMetricData } from "@/composables/useMetricData"
import { kgToLbs, WEIGHT_UNIT } from "@/utils/units"

interface WeightRow { date: string; weight_kg: number | null }
interface CompRow { date: string; weight_kg: number | null; fat_pct: number | null; muscle_mass_kg: number | null; bmi: number | null }

const { data: weightData, loading: wLoading, error: wError } = useMetricData<WeightRow[]>("/body/weight")
const { data: compData, loading: cLoading, error: cError } = useMetricData<CompRow[]>("/body/composition")

const loading = computed(() => wLoading.value || cLoading.value)
const error = computed(() => wError.value || cError.value)

const latestWeight = computed(() => weightData.value?.[weightData.value.length - 1] ?? null)
const latestComp = computed(() => compData.value?.[compData.value.length - 1] ?? null)

const weightSpark = computed(() => weightData.value?.map((d) => d.weight_kg) ?? [])
const fatSpark = computed(() => compData.value?.map((d) => d.fat_pct) ?? [])
const muscleSpark = computed(() => compData.value?.map((d) => d.muscle_mass_kg) ?? [])
const bmiSpark = computed(() => compData.value?.map((d) => d.bmi) ?? [])

const weightSeries = computed(() => {
  if (!weightData.value?.length) return []
  return [{ name: "Weight", data: weightData.value.map((d) => [d.date, kgToLbs(d.weight_kg)] as [string, number | null]), color: "#3B82F6", smooth: true }]
})

const fatSeries = computed(() => {
  if (!compData.value?.length) return []
  return [{ name: "Body Fat %", data: compData.value.map((d) => [d.date, d.fat_pct] as [string, number | null]), color: "#F59E0B", smooth: true }]
})

const muscleSeries = computed(() => {
  if (!compData.value?.length) return []
  return [{ name: "Muscle Mass", data: compData.value.map((d) => [d.date, kgToLbs(d.muscle_mass_kg)] as [string, number | null]), color: "#10B981", smooth: true }]
})
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
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
