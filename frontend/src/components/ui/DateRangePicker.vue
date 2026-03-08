<template>
  <div class="date-range-picker">
    <div class="preset-buttons">
      <button
        v-for="p in presets"
        :key="p.value"
        :class="['preset-btn', { active: store.preset === p.value }]"
        @click="store.setPreset(p.value as any)"
      >{{ p.label }}</button>
    </div>
    <div class="custom-dates" v-if="store.preset === 'custom'">
      <input type="date" v-model="store.startDate" />
      <span>–</span>
      <input type="date" v-model="store.endDate" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useDateRangeStore } from "@/stores/dateRange"

const store = useDateRangeStore()
const presets = [
  { label: "7d", value: "7d" },
  { label: "30d", value: "30d" },
  { label: "90d", value: "90d" },
  { label: "1y", value: "1y" },
  { label: "Custom", value: "custom" },
]
</script>

<style scoped>
.date-range-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.preset-buttons {
  display: flex;
  gap: 4px;
}
.preset-btn {
  padding: 4px 10px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  font-size: 0.875rem;
}
.preset-btn.active {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}
.custom-dates {
  display: flex;
  align-items: center;
  gap: 6px;
}
.custom-dates input {
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.875rem;
}
</style>
