<template>
  <div class="shell">
    <IconRail :open="openSection" :current-section="currentSection" @open="openSection = $event" />
    <SectionPanel :section="sectionDef" />
    <main class="main" id="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute } from "vue-router"
import IconRail from "@/components/shell/IconRail.vue"
import SectionPanel from "@/components/shell/SectionPanel.vue"
import { SECTIONS, sectionOfPage, type SectionId } from "@/nav/sections"

const route = useRoute()
const currentSection = computed<SectionId>(() => sectionOfPage(route.name as string))

// The open section follows navigation, but the rail can open another section to browse
// its pages without leaving the current one.
const openSection = ref<SectionId>(currentSection.value)
watch(currentSection, (s) => (openSection.value = s))

const sectionDef = computed(() => SECTIONS.find((s) => s.id === openSection.value)!)
</script>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--rail-w) var(--panel-w) minmax(0, 1fr);
  height: 100%;
}
.main {
  overflow-y: auto;
  padding: var(--sp-5) var(--sp-6) var(--sp-6);
  min-width: 0;
}
</style>
