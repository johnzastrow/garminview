<template>
  <v-chart :option="option" autoresize style="height: 280px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

interface BarSeries {
  name: string
  data: number[]
  color?: string
}

const props = defineProps<{
  categories: string[]
  series: BarSeries[]
  yAxisLabel?: string
}>()

const option = computed(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  legend: { data: props.series.map((s) => s.name) },
  dataZoom: [{ type: "inside" }],
  xAxis: { type: "category", data: props.categories },
  yAxis: { type: "value", name: props.yAxisLabel },
  series: props.series.map((s) => ({
    name: s.name,
    type: "bar",
    stack: "total",
    data: s.data,
    itemStyle: s.color ? { color: s.color } : undefined,
  })),
}))
</script>
