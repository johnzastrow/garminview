<template>
  <div class="page">
    <PageHeader :section="sectionTitle" :title="page?.title ?? 'Page not found'" :summary="page?.summary" />
    <div class="empty">
      <template v-if="page">
        <p>This screen is not built in v2 yet. Screens are added one at a time.</p>
        <p class="muted">Built so far: <RouterLink to="/sleep">Sleep</RouterLink>.</p>
      </template>
      <p v-else>No page at this address. Pick a section on the left.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import PageHeader from "@/components/ui/PageHeader.vue"
import { ALL_PAGES, SECTIONS } from "@/nav/sections"

const route = useRoute()
const page = computed(() => ALL_PAGES.find((p) => p.name === route.name))
const sectionTitle = computed(() => SECTIONS.find((s) => s.id === page.value?.section)?.title ?? "")
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  max-width: 1180px;
}
.empty {
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  padding: var(--sp-6);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.empty a {
  color: var(--accent);
}
</style>
