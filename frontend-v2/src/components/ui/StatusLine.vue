<template>
  <p class="status" :class="kind" :role="kind === 'error' ? 'alert' : 'status'">
    <svg viewBox="0 0 10 10" aria-hidden="true">
      <path v-if="kind === 'error'" d="M1.5 1.5l7 7M8.5 1.5l-7 7" />
      <path v-else-if="kind === 'warn'" d="M5 1 9.5 9H.5Z" />
      <circle v-else cx="5" cy="5" r="3.5" />
    </svg>
    <span><slot /></span>
  </p>
</template>

<script setup lang="ts">
// Status is always an icon plus words, never color alone.
defineProps<{ kind: "error" | "warn" | "info" }>()
</script>

<style scoped>
.status {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
  padding: 10px var(--sp-3);
  border: 1px solid;
  border-radius: var(--radius);
}
svg {
  width: 11px;
  height: 11px;
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
}
.error {
  color: var(--s-err);
}
.warn {
  color: var(--s-warn);
}
.info {
  color: var(--muted);
  border-color: var(--border-strong);
}
</style>
