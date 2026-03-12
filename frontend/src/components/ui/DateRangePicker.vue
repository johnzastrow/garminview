<template>
  <div class="range-picker">
    <button
      v-for="p in presets"
      :key="p.value"
      class="pill"
      :class="{ active: store.preset === p.value }"
      @click="store.setPreset(p.value as any)"
    >{{ p.label }}</button>

    <template v-if="store.preset === 'custom'">
      <span class="sep">from</span>
      <input type="date" v-model="store.startDate" class="date-input" />
      <span class="sep">to</span>
      <input type="date" v-model="store.endDate" class="date-input" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useDateRangeStore } from '@/stores/dateRange'

const store = useDateRangeStore()
const presets = [
  { label: '7 days',  value: '7d' },
  { label: '30 days', value: '30d' },
  { label: '90 days', value: '90d' },
  { label: '1 year',  value: '1y' },
  { label: 'Custom',  value: 'custom' },
]
</script>

<style scoped>
.range-picker {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.pill {
  padding: 5px 14px;
  border: 1px solid var(--border);
  border-radius: 100px;
  background: var(--surface);
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--muted);
  transition: all 0.12s;
}
.pill:hover { border-color: var(--accent); color: var(--accent); }
.pill.active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.sep { font-size: 0.8rem; color: var(--muted); padding: 0 2px; }

.date-input {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 0.8rem;
  background: var(--surface);
  color: var(--text);
  outline: none;
}
.date-input:focus { border-color: var(--accent); }
</style>
