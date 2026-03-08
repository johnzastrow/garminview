<template>
  <div class="metric-card">
    <div class="metric-label">{{ label }}</div>
    <div class="metric-value">
      {{ value !== null && value !== undefined ? value : "—" }}
      <span v-if="unit" class="metric-unit">{{ unit }}</span>
    </div>
    <div v-if="trend" class="metric-trend" :class="trendClass">{{ trend }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{
  label: string
  value: number | string | null | undefined
  unit?: string
  trend?: string
  trendDirection?: "up" | "down" | "neutral"
}>()

const trendClass = computed(() => ({
  "trend-up": props.trendDirection === "up",
  "trend-down": props.trendDirection === "down",
  "trend-neutral": props.trendDirection === "neutral",
}))
</script>

<style scoped>
.metric-card {
  background: var(--color-surface, #fff);
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
.metric-label {
  font-size: 0.75rem;
  color: var(--color-text-muted, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--color-text, #111827);
}
.metric-unit {
  font-size: 0.875rem;
  font-weight: 400;
  color: var(--color-text-muted, #6b7280);
  margin-left: 2px;
}
.metric-trend {
  font-size: 0.75rem;
  margin-top: 4px;
}
.trend-up { color: #10b981; }
.trend-down { color: #ef4444; }
.trend-neutral { color: #6b7280; }
</style>
