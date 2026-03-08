import { createRouter, createWebHistory } from "vue-router"

const routes = [
  { path: "/", component: () => import("@/views/DailyOverview.vue") },
  { path: "/sleep", component: () => import("@/views/SleepDashboard.vue") },
  { path: "/body", component: () => import("@/views/WeightBodyComp.vue") },
  { path: "/cardio", component: () => import("@/views/CardiovascularDashboard.vue") },
  { path: "/training", component: () => import("@/views/TrainingLoadDashboard.vue") },
  { path: "/activities", component: () => import("@/views/ActivitySummary.vue") },
  { path: "/running", component: () => import("@/views/RunningDashboard.vue") },
  { path: "/recovery", component: () => import("@/views/RecoveryStress.vue") },
  { path: "/trends", component: () => import("@/views/LongTermTrends.vue") },
  { path: "/correlations", component: () => import("@/views/CorrelationExplorer.vue") },
  { path: "/assessments", component: () => import("@/views/AssessmentsGoals.vue") },
  { path: "/data-quality", component: () => import("@/views/DataQuality.vue") },
  { path: "/admin", component: () => import("@/views/Admin.vue") },
]

export default createRouter({ history: createWebHistory(), routes })
