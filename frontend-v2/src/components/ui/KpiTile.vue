<template>
  <div class="tile">
    <div class="label">{{ label }}</div>
    <div class="value num" :style="{ color }">
      {{ value }}<small v-if="unit">{{ unit }}</small>
    </div>
    <div class="foot">{{ foot }}</div>
    <TickScale class="scale" v-bind="scale" :color="color" :aria-label="`${label}: ${value}${unit ? ' ' + unit : ''}`" />
  </div>
</template>

<script setup lang="ts">
import TickScale from "./TickScale.vue"

defineProps<{
  label: string
  /** Pre-formatted display value */
  value: string
  unit?: string
  /** CSS color for the value and the scale marker, usually a data token */
  color: string
  foot: string
  scale: { min: number; max: number; value: number | null; band?: [number, number]; divisions?: number }
}>()
</script>

<style scoped>
.tile {
  background: var(--raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--sp-3) 14px 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 0;
}
.value {
  font-size: var(--fs-num);
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.value small {
  font-size: var(--fs-sm);
  color: var(--muted);
  font-weight: 400;
  letter-spacing: 0;
  margin-left: 5px;
}
.foot {
  font-size: var(--fs-sm);
  color: var(--muted);
  padding-bottom: var(--sp-2);
}
.scale {
  margin: 0 -14px;
}
</style>
