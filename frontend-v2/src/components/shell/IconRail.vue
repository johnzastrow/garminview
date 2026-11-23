<template>
  <nav class="rail" aria-label="Sections">
    <RouterLink to="/" class="mark num" aria-label="GarminView home">GV</RouterLink>
    <button
      v-for="s in SECTIONS"
      :key="s.id"
      type="button"
      class="sec"
      :class="{ current: s.id === currentSection }"
      :aria-pressed="s.id === open"
      :aria-label="s.title"
      :title="s.title"
      @click="emit('open', s.id)"
    >
      <svg viewBox="0 0 20 20" aria-hidden="true"><path v-for="d in s.icon" :key="d" :d="d" /></svg>
      <span class="cap">{{ s.title }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { SECTIONS, type SectionId } from "@/nav/sections"

defineProps<{ open: SectionId; currentSection: SectionId }>()
const emit = defineEmits<{ open: [id: SectionId] }>()
</script>

<style scoped>
.rail {
  width: var(--rail-w);
  background: var(--canvas);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding-block: var(--sp-3);
}
.mark {
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  color: var(--text);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  margin-bottom: var(--sp-3);
}
.sec {
  position: relative;
  width: 48px;
  padding: 7px 0 5px;
  background: transparent;
  border: 0;
  border-radius: var(--radius);
  color: var(--muted);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.sec svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.cap {
  font-size: 9.5px;
  letter-spacing: 0.03em;
}
.sec:hover {
  background: var(--raised);
  color: var(--text);
}
.sec[aria-pressed="true"] {
  background: var(--raised);
  color: var(--text);
}
/* The section of the page you are on carries a tick on the rail edge, even while another section is open */
.sec.current::before {
  content: "";
  position: absolute;
  left: -4px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--accent);
}
@media (prefers-reduced-motion: no-preference) {
  .sec {
    transition: background-color 0.12s, color 0.12s;
  }
}
</style>
