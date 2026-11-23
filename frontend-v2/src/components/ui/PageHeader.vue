<template>
  <header class="page-header">
    <div class="titles">
      <div class="label">{{ section }}</div>
      <h1>{{ title }}</h1>
      <p v-if="summary" class="summary"><slot name="summary">{{ summary }}</slot></p>
    </div>
    <div class="controls"><slot /></div>
  </header>
</template>

<script setup lang="ts">
defineProps<{ section: string; title: string; summary?: string }>()
</script>

<style scoped>
.page-header {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4) var(--sp-6);
  justify-content: space-between;
  align-items: flex-end;
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--border);
}
.titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
h1 {
  font-size: var(--fs-xl);
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.summary {
  color: var(--muted);
  font-size: var(--fs-md);
  margin-top: 2px;
}
.controls {
  display: flex;
  gap: var(--sp-3);
  align-items: center;
}
</style>
