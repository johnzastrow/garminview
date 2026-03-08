<template>
  <v-chart :option="option" autoresize style="height: 180px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { HeatmapChart } from "echarts/charts"
import { CalendarComponent, TooltipComponent, VisualMapComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([HeatmapChart, CalendarComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

const props = defineProps<{
  data: [string, number][]
  year: number
  label?: string
  colorRange?: [string, string]
}>()

const option = computed(() => ({
  tooltip: { formatter: (p: { data: [string, number] }) => `${p.data[0]}: ${p.data[1]}` },
  visualMap: {
    min: 0,
    max: Math.max(...props.data.map((d) => d[1]), 1),
    inRange: { color: props.colorRange ?? ["#e0f2fe", "#0369a1"] },
    show: false,
  },
  calendar: {
    range: props.year,
    cellSize: ["auto", 13],
    top: 30,
  },
  series: [{
    type: "heatmap",
    coordinateSystem: "calendar",
    data: props.data,
  }],
}))
</script>
