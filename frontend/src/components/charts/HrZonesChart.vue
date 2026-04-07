<template>
  <div v-if="!hasData" class="empty-state">
    Set your Max HR and Resting HR in
    <router-link to="/profile">Profile</router-link>
    to enable zone analysis.
  </div>
  <v-chart v-else :option="option" autoresize style="height: 320px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { BarChart, LineChart } from "echarts/charts"
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
])

export interface HRZonesDay {
  date: string
  z2_min: number | null
  z3_min: number | null
  z4_min: number | null
  z5_min: number | null
  valid_max_hr: number | null
  raw_max_hr: number | null
  rejected_count: number | null
  total_count: number | null
}

const props = defineProps<{ data: HRZonesDay[] }>()

const hasData = computed(() => props.data.length > 0)

const dates = computed(() => props.data.map((d) => d.date))
const dataByDate = computed(() => new Map(props.data.map((d) => [d.date, d])))

const option = computed(() => ({
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    backgroundColor: "#fff",
    borderColor: "#E6E4DC",
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: "#1A1918", fontSize: 12 },
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,0.10); border-radius: 8px;",
    formatter(params: any[]) {
      if (!params?.length) return ""
      const date = new Date(params[0].axisValue)
      const dateStr = date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
      const row = dataByDate.value.get(params[0].axisValue) ?? null
      const rejected = row?.rejected_count ?? 0
      const total = row?.total_count ?? 0
      const rawMax = row?.raw_max_hr
      const rejectedNote =
        rejected > 0
          ? `<div style="color:#f87171;margin-top:4px;font-size:11px">[!] ${rejected}/${total} readings rejected (raw max: ${rawMax} bpm)</div>`
          : ""
      const bars = params
        .filter((p) => p.seriesType === "bar" && p.value?.[1] != null && p.value[1] > 0)
        .map((p) => {
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${p.color};margin-right:6px"></span>`
          return `<div style="display:flex;align-items:center;margin-top:3px">${dot}<span style="color:#6B6A65">${p.seriesName}:</span>&nbsp;<strong>${p.value[1]} min</strong></div>`
        })
      const lines = params
        .filter((p) => p.seriesType === "line" && p.value?.[1] != null)
        .map((p) => {
          const dot = `<span style="display:inline-block;width:14px;height:2px;background:${p.color};margin-right:6px;vertical-align:middle"></span>`
          return `<div style="display:flex;align-items:center;margin-top:3px">${dot}<span style="color:#6B6A65">${p.seriesName}:</span>&nbsp;<strong>${p.value[1]} bpm</strong></div>`
        })
      return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${dateStr}</div>${[...bars, ...lines].join("")}${rejectedNote}`
    },
  },
  legend: {
    data: ["Z2 Aerobic", "Z3 Tempo", "Z4 Threshold", "Z5 VO₂max", "Max HR (valid)", "Raw max HR"],
    textStyle: { color: "#9A9690", fontSize: 11 },
    top: 0,
    right: 0,
    itemWidth: 14,
    itemHeight: 10,
  },
  grid: { top: 48, right: 72, bottom: 36, left: 52 },
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
      name: "min",
      nameTextStyle: { color: "#9A9690", fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#9A9690", fontSize: 11 },
      splitLine: { lineStyle: { color: "#F0EFE9", type: "dashed" } },
    },
    {
      type: "value",
      name: "bpm",
      nameTextStyle: { color: "#60a5fa", fontSize: 10 },
      axisLine: { show: true, lineStyle: { color: "#60a5fa40" } },
      axisTick: { show: false },
      axisLabel: { color: "#60a5fa", fontSize: 11 },
      splitLine: { show: false },
    },
  ],
  series: [
    {
      name: "Z2 Aerobic",
      type: "bar",
      stack: "zones",
      yAxisIndex: 0,
      data: props.data.map((d) => [d.date, d.z2_min]),
      itemStyle: { color: "#22c55e", opacity: 0.85 },
    },
    {
      name: "Z3 Tempo",
      type: "bar",
      stack: "zones",
      yAxisIndex: 0,
      data: props.data.map((d) => [d.date, d.z3_min]),
      itemStyle: { color: "#f59e0b", opacity: 0.85 },
    },
    {
      name: "Z4 Threshold",
      type: "bar",
      stack: "zones",
      yAxisIndex: 0,
      data: props.data.map((d) => [d.date, d.z4_min]),
      itemStyle: { color: "#f97316", opacity: 0.85 },
    },
    {
      name: "Z5 VO₂max",
      type: "bar",
      stack: "zones",
      yAxisIndex: 0,
      data: props.data.map((d) => [d.date, d.z5_min]),
      itemStyle: { color: "#ef4444", opacity: 0.85 },
    },
    {
      name: "Max HR (valid)",
      type: "line",
      yAxisIndex: 1,
      data: props.data.map((d) => [d.date, d.valid_max_hr]),
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { color: "#60a5fa", width: 2.5 },
      itemStyle: { color: "#60a5fa" },
      connectNulls: false,
    },
    {
      name: "Raw max HR",
      type: "line",
      yAxisIndex: 1,
      data: props.data.map((d) => [d.date, d.raw_max_hr]),
      symbol: (value: [string, number | null], _params: any) => {
        // Diamond on spike days (gap > 10 bpm)
        const row = dataByDate.value.get(value[0]) ?? null
        if (
          row?.raw_max_hr != null &&
          row?.valid_max_hr != null &&
          row.raw_max_hr - row.valid_max_hr > 10
        ) {
          return "diamond"
        }
        return "none"
      },
      symbolSize: 8,
      lineStyle: { color: "#f87171", width: 1.5, type: "dashed" },
      itemStyle: { color: "#f87171" },
      connectNulls: false,
    },
  ],
}))
</script>

<style scoped>
.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--muted);
  font-size: 0.875rem;
}
.empty-state a {
  color: var(--accent);
  text-decoration: none;
}
</style>
