<template>
  <v-chart :option="option" autoresize style="height: 320px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { ScatterChart, LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([ScatterChart, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

interface ScatterPoint { x: string | number; y: number; label?: string }
interface TrendLine { name: string; data: [string | number, number][]; color: string; dashed?: boolean }

const props = defineProps<{
  scatter: ScatterPoint[]
  trends: TrendLine[]
  yAxisLabel?: string
  xIsTime?: boolean
}>()

const option = computed(() => ({
  tooltip: {
    trigger: "item",
    backgroundColor: "#fff",
    borderColor: "#E6E4DC",
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: "#1A1918", fontSize: 12 },
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,0.10); border-radius: 8px;",
    formatter(p: any) {
      if (!p) return ""
      const isScatter = p.seriesName === "Workouts"
      if (isScatter) {
        const [x, y] = p.value
        const dateStr = props.xIsTime
          ? new Date(x).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
          : x
        const unit = props.yAxisLabel ? ` ${props.yAxisLabel}` : ""
        return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${dateStr}</div>` +
          `<div style="display:flex;align-items:center"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#94A3B8;margin-right:6px"></span><strong>${y}${unit}</strong></div>`
      }
      // Trend line hover
      const [x, y] = Array.isArray(p.value) ? p.value : [p.name, p.value]
      const dateStr = props.xIsTime
        ? new Date(x).toLocaleDateString(undefined, { month: "short", year: "numeric" })
        : x
      const unit = props.yAxisLabel ? ` ${props.yAxisLabel}` : ""
      const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>`
      return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${dateStr}</div>` +
        `<div style="display:flex;align-items:center">${dot}<span style="color:#6B6A65">${p.seriesName}:</span>&nbsp;<strong>${Number(y).toFixed(0)}${unit}</strong></div>`
    },
  },
  legend: {
    data: props.trends.map((t) => t.name),
    textStyle: { color: "#9A9690", fontSize: 11 },
    top: 0,
    right: 0,
  },
  grid: { top: 36, right: 16, bottom: 48, left: 52, containLabel: false },
  dataZoom: [{ type: "inside", filterMode: "none" }],
  xAxis: {
    type: props.xIsTime ? "time" : "value",
    axisLine: { lineStyle: { color: "#E6E4DC" } },
    axisTick: { show: false },
    axisLabel: { color: "#9A9690", fontSize: 11 },
    splitLine: { show: false },
  },
  yAxis: {
    type: "value",
    name: props.yAxisLabel,
    nameTextStyle: { color: "#9A9690", fontSize: 10 },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: "#9A9690", fontSize: 11 },
    splitLine: { lineStyle: { color: "#F0EFE9", type: "dashed" } },
  },
  series: [
    {
      name: "Workouts",
      type: "scatter",
      data: props.scatter.map((p) => [p.x, p.y]),
      symbolSize: 5,
      itemStyle: { color: "#CBD5E1", opacity: 0.7 },
      emphasis: { itemStyle: { color: "#64748B", opacity: 1 } },
    },
    ...props.trends.map((t) => ({
      name: t.name,
      type: "line",
      data: t.data,
      smooth: true,
      symbol: "none",
      lineStyle: {
        color: t.color,
        width: 2,
        type: t.dashed ? "dashed" : "solid",
      },
      itemStyle: { color: t.color },
    })),
  ],
}))
</script>
