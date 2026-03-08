<template>
  <v-chart :option="option" autoresize style="height: 320px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart, BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

interface PMCPoint {
  date: string
  atl: number | null
  ctl: number | null
  tsb: number | null
  trimp: number | null
}

const props = defineProps<{ data: PMCPoint[] }>()

const option = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { data: ["CTL (Fitness)", "ATL (Fatigue)", "TSB (Form)", "TRIMP"] },
  dataZoom: [{ type: "slider", bottom: 0 }],
  xAxis: { type: "category", data: props.data.map((d) => d.date) },
  yAxis: [{ type: "value", name: "Load" }, { type: "value", name: "TRIMP" }],
  series: [
    { name: "CTL (Fitness)", type: "line", smooth: true, data: props.data.map((d) => d.ctl), itemStyle: { color: "#3b82f6" } },
    { name: "ATL (Fatigue)", type: "line", smooth: true, data: props.data.map((d) => d.atl), itemStyle: { color: "#ef4444" } },
    { name: "TSB (Form)", type: "line", smooth: true, data: props.data.map((d) => d.tsb), itemStyle: { color: "#10b981" } },
    { name: "TRIMP", type: "bar", yAxisIndex: 1, data: props.data.map((d) => d.trimp), itemStyle: { color: "#f59e0b", opacity: 0.6 } },
  ],
}))
</script>
