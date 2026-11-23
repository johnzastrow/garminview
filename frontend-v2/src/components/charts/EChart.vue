<template>
  <VChart class="echart" :style="{ height: `${height}px` }" theme="instrument" :option="option" autoresize />
</template>

<script setup lang="ts">
import VChart from "vue-echarts"
import "@/charts/theme"

withDefaults(defineProps<{ option: Record<string, unknown>; height?: number }>(), { height: 240 })
</script>

<style scoped>
.echart {
  width: 100%;
}
</style>
