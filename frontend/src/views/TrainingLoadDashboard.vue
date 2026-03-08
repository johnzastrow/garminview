<template>
  <div class="dashboard">
    <h1>Training Load (PMC)</h1>
    <DateRangePicker />
    <div v-if="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <PMCChart v-else-if="chartData.length" :data="chartData" />
    <p v-else>No training load data available.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import PMCChart from "@/components/charts/PMCChart.vue"
import { useMetricData } from "@/composables/useMetricData"

interface LoadRow { date: string; atl: number | null; ctl: number | null; tsb: number | null; trimp: number | null }
const { data, loading, error } = useMetricData<LoadRow[]>("/training/load")
const chartData = computed(() => data.value ?? [])
</script>
