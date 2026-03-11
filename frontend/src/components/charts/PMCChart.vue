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
  tooltip: {
    trigger: "axis",
    backgroundColor: "#fff",
    borderColor: "#E6E4DC",
    borderWidth: 1,
    padding: [8, 12],
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,0.10); border-radius: 8px;",
    axisPointer: {
      type: "cross",
      crossStyle: { color: "#C8C6C0", width: 1 },
      label: { backgroundColor: "#6B6A65", fontSize: 11, padding: [4, 8] },
    },
    formatter(params: any[]) {
      if (!params?.length) return ""
      const date = params[0].axisValue
      const rows = params
        .filter(p => p.value != null && !isNaN(p.seriesIndex))
        .map(p => {
          const raw = Array.isArray(p.value) ? p.value[1] : p.value
          if (raw == null) return ""
          const val = typeof raw === "number" ? raw.toLocaleString(undefined, { maximumFractionDigits: 1 }) : raw
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>`
          return `<div style="display:flex;align-items:center;margin-top:3px">${dot}<span style="color:#6B6A65">${p.seriesName}:</span>&nbsp;<strong>${val}</strong></div>`
        })
        .filter(Boolean)
      return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${date}</div>${rows.join("")}`
    },
  },
  legend: { data: ["CTL (Fitness)", "ATL (Fatigue)", "TSB (Form)", "TRIMP"] },
  dataZoom: [{ type: "slider", bottom: 0 }],
  xAxis: { type: "category", data: props.data.map((d) => d.date) },
  yAxis: [{ type: "value", name: "Load", scale: true }, { type: "value", name: "TRIMP", min: 0 }],
  series: [
    { name: "CTL (Fitness)", type: "line", smooth: true, data: props.data.map((d) => d.ctl), itemStyle: { color: "#3b82f6" } },
    { name: "ATL (Fatigue)", type: "line", smooth: true, data: props.data.map((d) => d.atl), itemStyle: { color: "#ef4444" } },
    { name: "TSB (Form)", type: "line", smooth: true, data: props.data.map((d) => d.tsb), itemStyle: { color: "#10b981" } },
    { name: "TRIMP", type: "bar", yAxisIndex: 1, data: props.data.map((d) => d.trimp), itemStyle: { color: "#f59e0b", opacity: 0.6 } },
  ],
}))
</script>
