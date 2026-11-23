<template>
  <div class="seg" role="group" aria-label="Date range">
    <button
      v-for="p in RANGE_PRESETS"
      :key="p.id"
      type="button"
      :aria-pressed="range.preset === p.id"
      @click="range.preset = p.id"
    >
      {{ p.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { RANGE_PRESETS, useRangeStore } from "@/stores/range"

const range = useRangeStore()
</script>

<style scoped>
.seg {
  display: inline-flex;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  overflow: hidden;
}
button {
  font-family: var(--font-num);
  font-size: var(--fs-xs);
  background: transparent;
  color: var(--muted);
  border: 0;
  border-right: 1px solid var(--border-strong);
  padding: 5px 11px;
  cursor: pointer;
}
button:last-child {
  border-right: 0;
}
button[aria-pressed="true"] {
  background: var(--accent);
  color: var(--on-accent);
  font-weight: 500;
}
button:hover:not([aria-pressed="true"]) {
  background: var(--raised);
  color: var(--text);
}
</style>
