<template>
  <v-chart :option="option" autoresize style="height: 260px" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

interface Series {
  name: string
  data: [string, number | null][]
  color?: string
  smooth?: boolean
}

const props = defineProps<{
  series: Series[]
  yAxisLabel?: string
}>()

// Compute a sensible Y axis minimum: floor of (min value − 5% of range), floored to a round number
const yMin = computed(() => {
  const vals = props.series.flatMap(s => s.data.map(([, v]) => v)).filter((v): v is number => v != null)
  if (!vals.length) return undefined
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min
  // Don't clip at zero for metrics that are always well above it (e.g. HR, weight)
  // But do use 0 when data naturally starts near zero (e.g. steps, TRIMP, distance)
  const floor = min - range * 0.08
  if (floor <= 0) return 0
  // Round down to nearest "nice" number
  const magnitude = Math.pow(10, Math.floor(Math.log10(range || 1)))
  return Math.floor(floor / magnitude) * magnitude
})

const option = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#fff',
    borderColor: '#E6E4DC',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: '#1A1918', fontSize: 12, fontFamily: 'Bricolage Grotesque, system-ui, sans-serif' },
    extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.10); border-radius: 8px;',
    axisPointer: {
      type: 'cross',
      crossStyle: { color: '#C8C6C0', width: 1 },
      label: { backgroundColor: '#6B6A65', fontSize: 11, padding: [4, 8] },
    },
    formatter(params: any[]) {
      if (!params?.length) return ''
      const date = new Date(params[0].axisValue)
      const dateStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
      const unit = props.yAxisLabel ? ` ${props.yAxisLabel}` : ''
      const rows = params
        .filter(p => p.value != null && p.value[1] != null)
        .map(p => {
          const val = typeof p.value[1] === 'number' ? p.value[1].toLocaleString(undefined, { maximumFractionDigits: 1 }) : p.value[1]
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px;flex-shrink:0"></span>`
          const label = params.length > 1 ? `<span style="color:#6B6A65">${p.seriesName}:</span> ` : ''
          return `<div style="display:flex;align-items:center;gap:2px;margin-top:3px">${dot}${label}<strong>${val}${unit}</strong></div>`
        })
      if (!rows.length) return ''
      return `<div style="font-size:11px;color:#9A9690;margin-bottom:4px">${dateStr}</div>${rows.join('')}`
    },
  },
  legend: props.series.length > 1 ? {
    data: props.series.map(s => s.name),
    textStyle: { color: '#9A9690', fontSize: 11, fontFamily: 'Bricolage Grotesque, system-ui, sans-serif' },
    top: 0,
    right: 0,
  } : { show: false },
  grid: { top: props.series.length > 1 ? 36 : 12, right: 16, bottom: 36, left: 48, containLabel: false },
  dataZoom: [{ type: 'inside', filterMode: 'none' }],
  xAxis: {
    type: 'time',
    axisLine: { lineStyle: { color: '#E6E4DC' } },
    axisTick: { show: false },
    axisLabel: { color: '#9A9690', fontSize: 11, fontFamily: 'Bricolage Grotesque, system-ui, sans-serif' },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'value',
    name: props.yAxisLabel,
    min: yMin.value,
    nameTextStyle: { color: '#9A9690', fontSize: 10 },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#9A9690', fontSize: 11, fontFamily: 'Bricolage Grotesque, system-ui, sans-serif' },
    splitLine: { lineStyle: { color: '#F0EFE9', type: 'dashed' } },
  },
  series: props.series.map(s => ({
    name: s.name,
    type: 'line',
    data: s.data,
    smooth: s.smooth ?? false,
    symbol: 'none',
    lineStyle: { color: s.color, width: 2 },
    itemStyle: { color: s.color },
    connectNulls: false,
    areaStyle: props.series.length === 1 && s.color ? {
      color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: s.color + '28' },
          { offset: 1, color: s.color + '00' },
        ],
      },
    } : undefined,
  })),
}))
</script>
