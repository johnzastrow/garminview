<template>
  <v-chart :option="option" autoresize style="height: 280px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer])

interface BarSeries {
  name: string
  data: number[]
  color?: string
}

const props = defineProps<{
  categories: string[]
  series: BarSeries[]
  yAxisLabel?: string
  markLine?: number  // optional horizontal reference line value
}>()

const option = computed(() => {
  const series = props.series.map((s, i) => ({
    name: s.name,
    type: "bar",
    stack: "total",
    data: s.data,
    itemStyle: s.color ? { color: s.color } : undefined,
    // attach markLine to last series so it renders on top
    ...(props.markLine != null && i === props.series.length - 1 ? {
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: { type: "dashed", color: "#6B7280", width: 1.5 },
        label: { formatter: `WHO target: ${props.markLine} min/wk`, position: "end", fontSize: 11, color: "#6B7280" },
        data: [{ yAxis: props.markLine }],
      }
    } : {}),
  }))
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { data: props.series.map((s) => s.name) },
    dataZoom: [{ type: "inside" }],
    xAxis: { type: "category", data: props.categories },
    yAxis: { type: "value", name: props.yAxisLabel },
    series,
  }
})
</script>
