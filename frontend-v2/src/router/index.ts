import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router"
import { ALL_PAGES } from "@/nav/sections"

// Built screens are listed here explicitly; everything else gets the placeholder.
const VIEWS: Record<string, () => Promise<unknown>> = {
  sleep: () => import("@/views/SleepView.vue"),
}

export const routes: RouteRecordRaw[] = [
  ...ALL_PAGES.map((p) => ({
    path: p.path,
    name: p.name,
    component: VIEWS[p.name] ?? (() => import("@/views/PlaceholderView.vue")),
    meta: { title: p.title },
  })),
  { path: "/:pathMatch(.*)*", name: "not-found", component: () => import("@/views/PlaceholderView.vue") },
]

const router = createRouter({ history: createWebHistory(), routes })

router.afterEach((to) => {
  const t = to.meta.title as string | undefined
  document.title = t ? `${t} - GarminView` : "GarminView"
})

export default router
