<template>
  <v-chart :option="option" autoresize :style="{ height: height ?? '280px' }" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

export interface DualAxisSeries {
  name: string
  data: [string, number | null][]
  color: string
  unit?: string
}

const props = defineProps<{
  left: DualAxisSeries
  right: DualAxisSeries
  height?: string
}>()

function bounds(data: [string, number | null][]) {
  const vals = data.flatMap(([, v]) => (v != null ? [v] : []))
  if (!vals.length) return { min: undefined, max: undefined }
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const pad = (max - min) * 0.14 || 2
  return { min: parseFloat((min - pad).toFixed(1)), max: parseFloat((max + pad).toFixed(1)) }
}

const option = computed(() => {
  const lb = bounds(props.left.data)
  const rb = bounds(props.right.data)
  return {
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
          .filter((p) => p.value?.[1] != null)
          .map((p) => {
            const unit = p.seriesIndex === 0 ? (props.left.unit ?? "") : (props.right.unit ?? "")
            const val = Number(p.value[1]).toLocaleString(undefined, { maximumFractionDigits: 1 })
            const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>`
            return `<div style="display:flex;align-items:center;gap:2px;margin-top:3px">${dot}<span style="color:#6B6A65">${p.seriesName}:</span>&nbsp;<strong>${val}${unit}</strong></div>`
          })
        return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${dateStr}</div>${rows.join("")}`
      },
    },
    legend: {
      data: [props.left.name, props.right.name],
      textStyle: { color: "#9A9690", fontSize: 11 },
      top: 0,
      right: 0,
    },
    grid: { top: 36, right: 72, bottom: 36, left: 52 },
    dataZoom: [{ type: "inside", filterMode: "none" }],
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: "#E6E4DC" } },
      axisTick: { show: false },
      axisLabel: { color: "#9A9690", fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        name: props.left.unit,
        min: lb.min,
        max: lb.max,
        nameTextStyle: { color: props.left.color, fontSize: 10, padding: [0, 0, 0, 4] },
        axisLine: { show: true, lineStyle: { color: props.left.color + "60" } },
        axisTick: { show: false },
        axisLabel: { color: props.left.color, fontSize: 11 },
        splitLine: { lineStyle: { color: "#F0EFE9", type: "dashed" } },
      },
      {
        type: "value",
        name: props.right.unit,
        min: rb.min,
        max: rb.max,
        nameTextStyle: { color: props.right.color, fontSize: 10, padding: [0, 4, 0, 0] },
        axisLine: { show: true, lineStyle: { color: props.right.color + "60" } },
        axisTick: { show: false },
        axisLabel: { color: props.right.color, fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: props.left.name,
        type: "line",
        yAxisIndex: 0,
        data: props.left.data,
        smooth: true,
        symbol: "none",
        lineStyle: { color: props.left.color, width: 2 },
        itemStyle: { color: props.left.color },
        connectNulls: false,
      },
      {
        name: props.right.name,
        type: "line",
        yAxisIndex: 1,
        data: props.right.data,
        smooth: true,
        symbol: "none",
        lineStyle: { color: props.right.color, width: 2, type: "dashed" },
        itemStyle: { color: props.right.color },
        connectNulls: false,
      },
    ],
  }
})
</script>
