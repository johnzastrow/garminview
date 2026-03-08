<template>
  <div class="dashboard">
    <h1>Sleep Dashboard</h1>
    <DateRangePicker />
    <div v-if="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <StackedBarChart v-else-if="data && data.length" :categories="dates" :series="stageSeries" y-axis-label="Minutes" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import StackedBarChart from "@/components/charts/StackedBarChart.vue"
import { useMetricData } from "@/composables/useMetricData"

interface SleepRow { date: string; deep_sleep_min: number | null; light_sleep_min: number | null; rem_sleep_min: number | null; awake_min: number | null }
const { data, loading, error } = useMetricData<SleepRow[]>("/health/sleep")
const dates = computed(() => (data.value ?? []).map((d) => d.date))
const stageSeries = computed(() => [
  { name: "Deep", data: (data.value ?? []).map((d) => d.deep_sleep_min ?? 0), color: "#1d4ed8" },
  { name: "Light", data: (data.value ?? []).map((d) => d.light_sleep_min ?? 0), color: "#60a5fa" },
  { name: "REM", data: (data.value ?? []).map((d) => d.rem_sleep_min ?? 0), color: "#7c3aed" },
  { name: "Awake", data: (data.value ?? []).map((d) => d.awake_min ?? 0), color: "#fbbf24" },
])
</script>
