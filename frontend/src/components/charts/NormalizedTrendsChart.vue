<template>
  <v-chart :option="option" autoresize :style="{ height: height ?? '220px' }" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

export interface NormSeries {
  name: string
  data: [string, number | null][]
  color: string
  unit?: string
}

const props = defineProps<{
  series: NormSeries[]
  height?: string
}>()

// Normalize each series to [0, 100] range, embedding actual values in each point
// so the tooltip can show real values while the chart shows relative position.
function buildChartData(s: NormSeries) {
  const vals = s.data.flatMap(([, v]) => (v != null ? [v] : []))
  if (!vals.length) return []
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  return s.data.map(([d, v]) => {
    if (v == null) return null
    return {
      value: [d, ((v - min) / range) * 100],
      rawVal: v,
      unit: s.unit ?? "",
    }
  })
}

const option = computed(() => ({
  tooltip: {
    trigger: "axis",
    backgroundColor: "#fff",
    borderColor: "#E6E4DC",
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: "#1A1918", fontSize: 12 },
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,0.10); border-radius: 8px;",
    axisPointer: { type: "cross", crossStyle: { color: "#C8C6C0", width: 1 } },
    formatter(params: any[]) {
      if (!params?.length) return ""
      const date = new Date(params[0].axisValue)
      const dateStr = date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
      const rows = params
        .filter((p) => p.data?.rawVal != null)
        .map((p) => {
          const val = Number(p.data.rawVal).toLocaleString(undefined, { maximumFractionDigits: 1 })
          const unit = p.data.unit ? ` ${p.data.unit}` : ""
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px;flex-shrink:0"></span>`
          return `<div style="display:flex;align-items:center;gap:2px;margin-top:3px">${dot}<span style="color:#6B6A65">${p.seriesName}:</span>&nbsp;<strong>${val}${unit}</strong></div>`
        })
      if (!rows.length) return ""
      return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${dateStr}</div>${rows.join("")}`
    },
  },
  legend: {
    data: props.series.map((s) => s.name),
    textStyle: { color: "#9A9690", fontSize: 11 },
    top: 0,
    right: 0,
  },
  grid: { top: 36, right: 16, bottom: 36, left: 40 },
  dataZoom: [{ type: "inside", filterMode: "none" }],
  xAxis: {
    type: "time",
    axisLine: { lineStyle: { color: "#E6E4DC" } },
    axisTick: { show: false },
    axisLabel: { color: "#9A9690", fontSize: 11 },
    splitLine: { show: false },
  },
  yAxis: {
    type: "value",
    min: 0,
    max: 100,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    splitLine: { lineStyle: { color: "#F0EFE9", type: "dashed" } },
  },
  series: props.series.map((s) => ({
    name: s.name,
    type: "line",
    data: buildChartData(s),
    smooth: true,
    symbol: "none",
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    connectNulls: false,
  })),
}))
</script>
