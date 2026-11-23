<template>
  <section class="panel" :aria-labelledby="hid">
    <header class="ph">
      <h2 :id="hid" class="label">{{ title }}</h2>
      <div class="extra"><slot name="extra" /></div>
    </header>
    <div class="pb" :class="{ flush }"><slot /></div>
  </section>
</template>

<script setup lang="ts">
import { useId } from "vue"

defineProps<{ title: string; /** No inner padding, for tables */ flush?: boolean }>()
const hid = useId()
</script>

<style scoped>
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  min-width: 0;
}
.ph {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-4);
  justify-content: space-between;
  align-items: center;
  padding: 10px var(--sp-4);
  border-bottom: 1px solid var(--border);
  min-height: 41px;
}
.extra {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  align-items: center;
  font-size: var(--fs-sm);
  color: var(--muted);
}
.pb {
  padding: var(--sp-3) var(--sp-4) var(--sp-2);
}
.pb.flush {
  padding: 0;
}
</style>
