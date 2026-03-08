<template>
  <v-chart :option="option" autoresize style="height: 300px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart } from "echarts/charts"
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

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
  showRollingAvg?: boolean
  rollingDays?: number
}>()

const option = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { data: props.series.map((s) => s.name) },
  dataZoom: [{ type: "inside" }],
  xAxis: { type: "time" },
  yAxis: { type: "value", name: props.yAxisLabel },
  series: props.series.map((s) => ({
    name: s.name,
    type: "line",
    data: s.data,
    smooth: s.smooth ?? false,
    itemStyle: s.color ? { color: s.color } : undefined,
    connectNulls: false,
  })),
}))
</script>
