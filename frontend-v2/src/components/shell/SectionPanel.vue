<template>
  <nav class="spanel" :aria-label="`${section.title} pages`">
    <div class="head label">{{ section.title }}</div>
    <ul>
      <li v-for="p in section.pages" :key="p.name">
        <RouterLink :to="p.path" :title="p.built ? undefined : 'Not built yet in v2'" class="link" :class="{ unbuilt: !p.built }" active-class="" exact-active-class="active">
          <span>{{ p.title }}</span>
        </RouterLink>
      </li>
    </ul>
    <div class="foot">
      <span class="label">v2 preview</span>
      <span class="num">{{ builtCount }} of {{ ALL_PAGES.length }} built</span>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ALL_PAGES, type SectionDef } from "@/nav/sections"

defineProps<{ section: SectionDef }>()
const builtCount = ALL_PAGES.filter((p) => p.built).length
</script>

<style scoped>
.spanel {
  width: var(--panel-w);
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.head {
  padding: 18px var(--sp-4) 10px;
}
ul {
  list-style: none;
  margin: 0;
  padding: 0 var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow-y: auto;
}
.link {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--sp-2);
  padding: 6px var(--sp-2);
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--text);
  font-size: var(--fs-md);
  position: relative;
}
.link.unbuilt {
  color: var(--muted);
}
.link:hover {
  background: var(--raised);
  color: var(--text);
}
.link.active {
  background: var(--raised);
  color: var(--text);
  box-shadow: inset 2px 0 0 var(--accent);
}
.soon {
  font-size: var(--fs-xs);
  color: var(--faint);
}
.foot {
  margin-top: auto;
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  font-size: var(--fs-xs);
  color: var(--muted);
}
</style>
