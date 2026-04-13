<script setup lang="ts">
import { ref, onMounted, computed, watch } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart, BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import { useActalogStore, type WorkoutListItem } from "@/stores/actalog"
import { useDateRangeStore } from "@/stores/dateRange"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import DualAxisChart from "@/components/charts/DualAxisChart.vue"
import ReviewQueue from "@/components/actalog/ReviewQueue.vue"
import { api } from "@/api/client"
import { marked } from "marked"
import { useRoute } from "vue-router"

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent, CanvasRenderer])

const store = useActalogStore()
const dateRange = useDateRangeStore()
const route = useRoute()

const activeTab = ref<"workouts" | "movements" | "wods" | "prs" | "cross" | "calendar" | "qa" | "review" | "settings">("workouts")

// Review tab — pending count badge
const reviewPendingCount = ref(0)
async function fetchReviewPendingCount() {
  try {
    const { data } = await api.get("/admin/actalog/parser/status")
    reviewPendingCount.value = data.total_staged ?? 0
  } catch { /* ignore */ }
}

// Settings tab state
const settingsLoading = ref(true)
const settingsForm = ref({
  url: "",
  email: "",
  password: "",
  sync_enabled: false,
  ollama_url: "",
  model: "",
  min_note_length: 20,
  system_prompt: "",
})
const settingsShowPw = ref(false)
const settingsMsg = ref("")
const settingsMsgOk = ref(true)
const settingsParserRunning = ref(false)
let _settingsPollTimer: ReturnType<typeof setInterval> | null = null

async function loadSettingsConfig() {
  settingsLoading.value = true
  try {
    const [actalogR, parserR] = await Promise.all([
      api.get("/admin/actalog/config"),
      api.get("/admin/actalog/parser/config"),
    ])
    const ac = actalogR.data
    settingsForm.value.url = ac.url ?? ""
    settingsForm.value.email = ac.email ?? ""
    settingsForm.value.sync_enabled = ac.sync_enabled ?? false
    const pc = parserR.data
    settingsForm.value.ollama_url = pc.ollama_url ?? ""
    settingsForm.value.model = pc.model ?? ""
    settingsForm.value.min_note_length = pc.min_note_length ?? 20
    settingsForm.value.system_prompt = pc.system_prompt ?? ""
  } catch { /* ignore */ }
  finally { settingsLoading.value = false }
}

async function saveSettingsConfig() {
  settingsMsg.value = ""
  try {
    await Promise.all([
      api.post("/admin/actalog/config", {
        url: settingsForm.value.url,
        email: settingsForm.value.email,
        password: settingsForm.value.password || undefined,
        sync_enabled: settingsForm.value.sync_enabled,
      }),
      api.post("/admin/actalog/parser/config", {
        ollama_url: settingsForm.value.ollama_url,
        model: settingsForm.value.model,
        min_note_length: settingsForm.value.min_note_length,
        system_prompt: settingsForm.value.system_prompt,
      }),
    ])
    settingsMsg.value = "Config saved."
    settingsMsgOk.value = true
  } catch (e: any) {
    settingsMsg.value = `Save failed: ${e.response?.data?.detail ?? e.message}`
    settingsMsgOk.value = false
  }
}

async function testSettingsConnection() {
  settingsMsg.value = ""
  try {
    await api.post("/admin/actalog/test-connection", null, {
      params: {
        url: settingsForm.value.url,
        email: settingsForm.value.email,
        password: settingsForm.value.password,
      },
    })
    settingsMsg.value = "Connection successful."
    settingsMsgOk.value = true
  } catch (e: any) {
    settingsMsg.value = `Connection failed: ${e.response?.data?.detail ?? e.message}`
    settingsMsgOk.value = false
  }
}

async function settingsRunParser() {
  settingsMsg.value = ""
  try {
    await api.post("/admin/actalog/parser/run")
    settingsParserRunning.value = true
    _startSettingsPolling()
  } catch (e: any) {
    settingsMsg.value = `Parser run failed: ${e.response?.data?.detail ?? e.message}`
    settingsMsgOk.value = false
  }
}

async function settingsReparseAll() {
  if (!confirm("Delete all non-approved parse records and reparse everything? Approved notes are not affected.")) return
  settingsMsg.value = ""
  try {
    await api.post("/admin/actalog/parser/reparse-all")
    settingsParserRunning.value = true
    _startSettingsPolling()
  } catch (e: any) {
    settingsMsg.value = `Reparse failed: ${e.response?.data?.detail ?? e.message}`
    settingsMsgOk.value = false
  }
}

async function _settingsPollStatus() {
  try {
    const r = await api.get("/admin/actalog/parser/status")
    if (!r.data.running && settingsParserRunning.value) {
      settingsParserRunning.value = false
      settingsMsg.value = "Run complete."
      settingsMsgOk.value = true
      if (_settingsPollTimer) { clearInterval(_settingsPollTimer); _settingsPollTimer = null }
    }
  } catch { /* ignore */ }
}

function _startSettingsPolling() {
  if (_settingsPollTimer) return
  _settingsPollTimer = setInterval(_settingsPollStatus, 4000)
}

// ── Tab 1: Workouts ─────────────────────────────────────────────────
const expandedWorkout = ref<number | null>(null)

async function toggleExpand(id: number) {
  if (expandedWorkout.value === id) {
    expandedWorkout.value = null
    return
  }
  expandedWorkout.value = id
  await store.fetchWorkoutDetail(id)
}

function fmtDuration(s: number | null): string {
  if (!s) return "—"
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function typeColor(t: string | null): string {
  return ({ strength: "#3B82F6", metcon: "#F97316", cardio: "#22C55E", mixed: "#A855F7" } as Record<string, string>)[t ?? ""] ?? "#9A9690"
}

// ── Tab 2: Movement Progress ────────────────────────────────────────
const movements = ref<{ id: number; name: string | null; movement_type: string | null }[]>([])
const selectedMovement = ref<number | null>(null)
const movementHistory = ref<any[]>([])
const sidebarError = ref("")

async function loadMovements() {
  sidebarError.value = ""
  try {
    const { data } = await api.get("/actalog/movements")
    movements.value = data
  } catch {
    sidebarError.value = "Failed to load movements."
  }
}

async function selectMovement(id: number) {
  selectedMovement.value = id
  sidebarError.value = ""
  try {
    const { data } = await api.get(`/actalog/movements/${id}/history`)
    movementHistory.value = data
  } catch {
    sidebarError.value = "Failed to load movement history."
  }
}

const movementChartOption = computed(() => ({
  tooltip: { trigger: "axis" },
  xAxis: { type: "time" },
  yAxis: { type: "value", name: "kg" },
  series: [{
    type: "line",
    data: movementHistory.value
      .filter((r: any) => r.weight_kg != null)
      .map((r: any) => [r.workout_date, r.weight_kg]),
    smooth: true,
    symbol: "none",
    lineStyle: { color: "#3B82F6", width: 2 },
    markPoint: {
      data: movementHistory.value
        .filter((r: any) => r.is_pr)
        .map((r: any) => ({ xAxis: r.workout_date, yAxis: r.weight_kg, symbol: "circle", symbolSize: 8, itemStyle: { color: "#F97316" } })),
    },
  }],
}))

// ── Tab 3: WOD Progress ─────────────────────────────────────────────
const wods = ref<{ id: number; name: string | null; regime: string | null; score_type: string | null }[]>([])
const selectedWod = ref<number | null>(null)
const wodHistory = ref<any[]>([])
const selectedWodMeta = computed(() => wods.value.find(w => w.id === selectedWod.value) ?? null)

async function loadWods() {
  sidebarError.value = ""
  try {
    const { data } = await api.get("/actalog/wods")
    wods.value = data
  } catch {
    sidebarError.value = "Failed to load WODs."
  }
}

async function selectWod(id: number) {
  selectedWod.value = id
  sidebarError.value = ""
  try {
    const { data } = await api.get(`/actalog/wods/${id}/history`)
    wodHistory.value = data
  } catch {
    sidebarError.value = "Failed to load WOD history."
  }
}

const wodChartOption = computed(() => {
  const meta = selectedWodMeta.value
  if (!meta || !wodHistory.value.length) return null
  const isTime = meta.score_type === "Time"
  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: any[]) => {
        const p = params[0]
        if (!p) return ""
        const val = isTime
          ? `${Math.floor(p.value[1] / 60)}:${String(p.value[1] % 60).padStart(2, "0")}`
          : p.value[1]
        return `${new Date(p.value[0]).toLocaleDateString()}: ${val}`
      },
    },
    xAxis: { type: "time" },
    yAxis: {
      type: "value",
      name: isTime ? "seconds (lower=better)" : meta.score_type ?? "",
      inverse: isTime,
    },
    series: [{
      type: "line",
      data: wodHistory.value
        .filter((r: any) => isTime ? r.time_s != null : (r.rounds != null || r.weight_kg != null))
        .map((r: any) => {
          const y = isTime ? r.time_s : (meta?.score_type === "Max Weight" ? r.weight_kg : r.rounds)
          return [r.workout_date, y]
        }),
      smooth: true,
      symbol: "none",
      lineStyle: { color: "#F97316", width: 2 },
      markPoint: {
        data: wodHistory.value
          .filter((r: any) => r.is_pr)
          .map((r: any) => {
            const y = isTime ? r.time_s : (meta?.score_type === "Max Weight" ? r.weight_kg : r.rounds)
            return { xAxis: r.workout_date, yAxis: y, symbol: "circle", symbolSize: 8, itemStyle: { color: "#EF4444" } }
          }),
      },
    }],
  }
})

// ── Tab 5: Cross-reference ──────────────────────────────────────────
const crossSignal = ref<"body_battery_max" | "hr_resting" | "sleep_score" | "stress_avg">("body_battery_max")

const crossChartLeft = computed(() => ({
  name: "Volume (kg)",
  data: store.crossRef.map(r => [r.workout_date ?? "", r.total_volume_kg ?? null]) as [string, number | null][],
  color: "#3B82F6",
  unit: "kg",
}))

const crossChartRight = computed(() => {
  const labels: Record<string, string> = {
    body_battery_max: "Body Battery", hr_resting: "RHR (bpm)",
    sleep_score: "Sleep Score", stress_avg: "Stress",
  }
  const colors: Record<string, string> = {
    body_battery_max: "#22C55E", hr_resting: "#EF4444", sleep_score: "#8B5CF6", stress_avg: "#F97316",
  }
  return {
    name: labels[crossSignal.value] ?? crossSignal.value,
    data: store.crossRef.map(r => [r.workout_date ?? "", (r as any)[crossSignal.value] ?? null]) as [string, number | null][],
    color: colors[crossSignal.value] ?? "#9A9690",
    unit: "",
  }
})

// ── Tab 6: Calendar ─────────────────────────────────────────────────
const calYear = ref(new Date().getFullYear())
const calMonth = ref(new Date().getMonth()) // 0-indexed
const selectedDay = ref<string | null>(null)

const calDays = computed((): Array<{ date: string; day: number; workouts: WorkoutListItem[] } | null> => {
  const first = new Date(calYear.value, calMonth.value, 1)
  const totalDays = new Date(calYear.value, calMonth.value + 1, 0).getDate()
  const startPad = first.getDay()
  const cells: Array<{ date: string; day: number; workouts: WorkoutListItem[] } | null> = []
  for (let i = 0; i < startPad; i++) cells.push(null)
  for (let d = 1; d <= totalDays; d++) {
    const dateStr = `${calYear.value}-${String(calMonth.value + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`
    cells.push({ date: dateStr, day: d, workouts: store.workoutsByDate.get(dateStr) ?? [] })
  }
  return cells
})

function prevMonth() {
  if (calMonth.value === 0) { calYear.value--; calMonth.value = 11 } else calMonth.value--
}
function nextMonth() {
  if (calMonth.value === 11) { calYear.value++; calMonth.value = 0 } else calMonth.value++
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"]

async function selectDay(dateStr: string) {
  selectedDay.value = dateStr
  const dayWorkouts = store.workoutsByDate.get(dateStr)
  const first = dayWorkouts?.[0]
  if (first) {
    await store.fetchSessionVitals(first.id)
  }
}

const hrChartOption = computed(() => {
  const vitals = store.sessionVitals
  if (!vitals?.has_vitals || !vitals.hr_series.length) return null
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "time", axisLabel: { color: "#9A9690", fontSize: 10 } },
    yAxis: { type: "value", name: "bpm", axisLabel: { color: "#9A9690", fontSize: 10 } },
    series: [{
      type: "line",
      data: vitals.hr_series.map(p => [p.ts, p.hr]),
      smooth: false,
      symbol: "none",
      lineStyle: { color: "#EF4444", width: 1.5 },
      areaStyle: { color: "rgba(239,68,68,0.08)" },
    }],
  }
})

// ── Tab 7: QA Review ─────────────────────────────────────────────────
interface ParseRecord {
  id: number
  workout_id: number | null
  workout_name: string | null
  workout_date: string | null
  content_class: string | null
  parse_status: string | null
  parsed_at: string | null
  reviewed_at: string | null
  error_message: string | null
  llm_model: string | null
  raw_notes: string | null
  formatted_markdown: string | null
  parsed_json: string | null
  parse_duration_s: number | null
  llm_tokens_prompt: number | null
  llm_tokens_generated: number | null
  llm_inference_s: number | null
}
interface ParsedWod {
  name: string
  alt_name?: string | null
  name_source?: string | null
  regime?: string | null
  score_type?: string | null
  rpe?: number | null
  intended_stimulus?: string | null
  scaling_tiers?: {
    rx?: { movement: string; reps?: number | null; sets?: number | null; weight_lbs?: number | null; notes?: string | null }[]
    intermediate?: { movement: string; reps?: number | null; sets?: number | null; weight_lbs?: number | null; notes?: string | null }[]
    foundations?: { movement: string; reps?: number | null; sets?: number | null; weight_lbs?: number | null; notes?: string | null }[]
  }
}

const qaFilter = ref<"all" | "pending" | "approved" | "rejected" | "skipped">("pending")
const qaRecords = ref<ParseRecord[]>([])
const qaTotal = ref(0)
const qaLoading = ref(false)
const qaError = ref("")
const qaSelected = ref<ParseRecord | null>(null)
const qaEditMarkdown = ref("")
const qaEditRaw = ref("")
const qaActionMsg = ref("")
const qaActionOk = ref(false)
const qaActionBusy = ref(false)

const qaParsedWods = computed((): ParsedWod[] => {
  if (!qaSelected.value?.parsed_json) return []
  try {
    return JSON.parse(qaSelected.value.parsed_json).wods ?? []
  } catch { return [] }
})

const qaMarkdownHtml = computed((): string => {
  const src = qaEditMarkdown.value.trim()
  if (!src) return "<p class=\"qa-md-empty\">No markdown generated.</p>"
  return marked.parse(src) as string
})

const qaPerformanceNotes = computed((): string | null => {
  if (!qaSelected.value?.parsed_json) return null
  try {
    return JSON.parse(qaSelected.value.parsed_json).performance_notes ?? null
  } catch { return null }
})

function qaWodMismatch(r: ParseRecord): { jsonCount: number; mdCount: number } | null {
  if (!r.parsed_json || !r.formatted_markdown) return null
  let jsonCount = 0
  try {
    jsonCount = JSON.parse(r.parsed_json).wods?.length ?? 0
  } catch { return null }
  if (jsonCount === 0) return null
  const mdCount = r.formatted_markdown.split("\n").filter(line => line.startsWith("# ")).length
  if (mdCount === jsonCount) return null
  return { jsonCount, mdCount }
}

function qaSelectRecord(r: ParseRecord) {
  qaSelected.value = r
  qaEditMarkdown.value = r.formatted_markdown ?? ""
  qaEditRaw.value = r.raw_notes ?? ""
  qaActionMsg.value = ""
}

async function loadQaQueue() {
  qaLoading.value = true
  qaError.value = ""
  try {
    const params = qaFilter.value !== "all" ? `?status=${qaFilter.value}` : ""
    const { data } = await api.get(`/admin/actalog/parser/queue${params}`)
    qaRecords.value = data.items
    qaTotal.value = data.total
  } catch (e: any) {
    qaError.value = e.response?.data?.detail ?? e.message
  } finally {
    qaLoading.value = false
  }
}

async function qaApprove() {
  if (!qaSelected.value) return
  qaActionBusy.value = true
  qaActionMsg.value = ""
  try {
    await api.post(`/admin/actalog/parser/approve/${qaSelected.value.id}`, {
      formatted_markdown: qaEditMarkdown.value || null,
    })
    qaActionMsg.value = "Approved."
    qaActionOk.value = true
    await loadQaQueue()
    qaSelected.value = null
  } catch (e: any) {
    qaActionMsg.value = e.response?.data?.detail ?? e.message
    qaActionOk.value = false
  } finally {
    qaActionBusy.value = false
  }
}

async function qaReject() {
  if (!qaSelected.value) return
  qaActionBusy.value = true
  qaActionMsg.value = ""
  try {
    await api.post(`/admin/actalog/parser/reject/${qaSelected.value.id}`)
    qaActionMsg.value = "Rejected."
    qaActionOk.value = true
    await loadQaQueue()
    qaSelected.value = null
  } catch (e: any) {
    qaActionMsg.value = e.response?.data?.detail ?? e.message
    qaActionOk.value = false
  } finally {
    qaActionBusy.value = false
  }
}

async function qaReparse() {
  if (!qaSelected.value?.workout_id) return
  qaActionBusy.value = true
  qaActionMsg.value = ""
  try {
    await api.post(`/admin/actalog/parser/reparse/${qaSelected.value.workout_id}`)
    qaActionMsg.value = "Re-queued for parsing."
    qaActionOk.value = true
    await loadQaQueue()
    qaSelected.value = null
  } catch (e: any) {
    qaActionMsg.value = e.response?.data?.detail ?? e.message
    qaActionOk.value = false
  } finally {
    qaActionBusy.value = false
  }
}

watch(qaFilter, loadQaQueue)

// ── Lifecycle ────────────────────────────────────────────────────────
onMounted(async () => {
  // Support ?tab=review (or any tab) in URL
  if (route.query.tab && typeof route.query.tab === "string") {
    const validTabs = ["workouts","movements","wods","prs","cross","calendar","qa","review","settings"]
    if (validTabs.includes(route.query.tab)) {
      activeTab.value = route.query.tab as any
    }
  }

  await store.fetchWorkouts(dateRange.startDate, dateRange.endDate)
  await store.fetchPRs()
  await store.fetchCrossRef(dateRange.startDate, dateRange.endDate)
  await loadMovements()
  await loadWods()
  fetchReviewPendingCount()

  // Load settings config if that tab is active
  if (activeTab.value === "settings") loadSettingsConfig()
})

watch([() => dateRange.startDate, () => dateRange.endDate], async () => {
  await store.fetchWorkouts(dateRange.startDate, dateRange.endDate)
  await store.fetchCrossRef(dateRange.startDate, dateRange.endDate)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Actalog</h1>
      <DateRangePicker />
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar">
      <button v-for="tab in ['workouts','movements','wods','prs','cross','calendar','qa','review','settings']" :key="tab"
        :class="['tab-btn', { active: activeTab === tab }]"
        @click="activeTab = tab as any; if(tab==='qa') loadQaQueue(); if(tab==='settings') loadSettingsConfig()">
        {{ ({ workouts: 'Workouts', movements: 'Movements', wods: 'WODs', prs: 'Personal Records', cross: 'Cross-Reference', calendar: 'Calendar', qa: 'QA Review', review: 'Review', settings: 'Settings' } as Record<string,string>)[tab] }}
        <span v-if="tab === 'review' && reviewPendingCount > 0" class="tab-badge">{{ reviewPendingCount }}</span>
      </button>
    </div>

    <!-- ── Tab 1: Workouts ──────────────────────────────────────── -->
    <div v-if="activeTab === 'workouts'" class="tab-content">
      <div v-if="store.loading" class="muted">Loading…</div>
      <div v-else-if="!store.workouts.length" class="muted">No workouts found. Run a sync from Admin → Actalog.</div>
      <table v-else class="data-table">
        <thead><tr><th>Date</th><th>Name</th><th>Type</th><th>Duration</th><th></th></tr></thead>
        <tbody>
          <template v-for="w in store.workouts" :key="w.id">
            <tr class="workout-row">
              <td>{{ w.workout_date?.slice(0, 10) ?? "—" }}</td>
              <td>{{ w.workout_name ?? "—" }}</td>
              <td><span class="type-badge" :style="{ background: typeColor(w.workout_type) + '20', color: typeColor(w.workout_type) }">{{ w.workout_type ?? "—" }}</span></td>
              <td>{{ fmtDuration(w.total_time_s) }}</td>
              <td><button class="link-btn" @click="toggleExpand(w.id)">{{ expandedWorkout === w.id ? 'Collapse' : 'Expand' }}</button></td>
            </tr>
            <tr v-if="expandedWorkout === w.id && store.selectedWorkout?.id === w.id" class="expand-row">
              <td colspan="5">
                <div class="expand-body">
                  <div v-if="store.selectedWorkout.movements.length">
                    <p class="section-label">Movements</p>
                    <table class="inner-table">
                      <thead><tr><th>#</th><th>Movement ID</th><th>Sets</th><th>Reps</th><th>Weight</th><th>RPE</th><th>PR</th></tr></thead>
                      <tbody>
                        <tr v-for="m in store.selectedWorkout.movements" :key="m.id">
                          <td>{{ m.order_index ?? "—" }}</td>
                          <td>{{ m.movement_id }}</td>
                          <td>{{ m.sets ?? "—" }}</td>
                          <td>{{ m.reps ?? "—" }}</td>
                          <td>{{ m.weight_kg != null ? m.weight_kg + ' kg' : '—' }}</td>
                          <td>{{ m.rpe ?? "—" }}</td>
                          <td>{{ m.is_pr ? '★' : '' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="store.selectedWorkout.wods.length" style="margin-top:12px">
                    <p class="section-label">WODs</p>
                    <table class="inner-table">
                      <thead><tr><th>Score</th><th>RPE</th><th>PR</th></tr></thead>
                      <tbody>
                        <tr v-for="wod in store.selectedWorkout.wods" :key="wod.id">
                          <td>{{ wod.score_value ?? "—" }}</td>
                          <td>{{ wod.rpe ?? "—" }}</td>
                          <td>{{ wod.is_pr ? '★' : '' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p v-if="store.selectedWorkout.notes" class="notes-text">{{ store.selectedWorkout.notes }}</p>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- ── Tab 2: Movements ─────────────────────────────────────── -->
    <div v-if="activeTab === 'movements'" class="tab-content">
      <div class="split-layout">
        <div class="split-sidebar">
          <p class="section-label">Select Movement</p>
          <div class="movement-list">
            <button v-for="m in movements" :key="m.id"
              :class="['movement-item', { active: selectedMovement === m.id }]"
              @click="selectMovement(m.id)">
              {{ m.name }}
            </button>
          </div>
        </div>
        <div class="split-main">
          <div v-if="!selectedMovement" class="muted">Select a movement to see its history.</div>
          <div v-if="sidebarError" class="err-msg">{{ sidebarError }}</div>
          <template v-else>
            <v-chart v-if="movementHistory.some((r: any) => r.weight_kg)" :option="movementChartOption" autoresize style="height:240px" />
            <table v-if="movementHistory.length" class="data-table" style="margin-top:16px">
              <thead><tr><th>Date</th><th>Sets</th><th>Reps</th><th>Weight</th><th>RPE</th><th>PR</th></tr></thead>
              <tbody>
                <tr v-for="r in movementHistory" :key="(r as any).id">
                  <td>{{ (r as any).workout_date?.slice(0,10) ?? "—" }}</td>
                  <td>{{ (r as any).sets ?? "—" }}</td>
                  <td>{{ (r as any).reps ?? "—" }}</td>
                  <td>{{ (r as any).weight_kg != null ? (r as any).weight_kg + ' kg' : '—' }}</td>
                  <td>{{ (r as any).rpe ?? "—" }}</td>
                  <td>{{ (r as any).is_pr ? '★' : '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </div>
    </div>

    <!-- ── Tab 3: WOD Progress ────────────────────────────────── -->
    <div v-if="activeTab === 'wods'" class="tab-content">
      <div class="split-layout">
        <div class="split-sidebar">
          <p class="section-label">Select WOD</p>
          <div class="movement-list">
            <button v-for="w in wods" :key="w.id"
              :class="['movement-item', { active: selectedWod === w.id }]"
              @click="selectWod(w.id)">
              {{ w.name }}<span v-if="w.regime" class="wod-regime"> · {{ w.regime }}</span>
            </button>
          </div>
        </div>
        <div class="split-main">
          <div v-if="!selectedWod" class="muted">Select a WOD to see its performance history.</div>
          <div v-if="sidebarError" class="err-msg">{{ sidebarError }}</div>
          <template v-else>
            <div class="wod-meta" v-if="selectedWodMeta">
              Score type: <strong>{{ selectedWodMeta.score_type ?? "—" }}</strong>
              <span v-if="selectedWodMeta.score_type === 'Time'" class="muted"> (lower is better)</span>
              <span v-else class="muted"> (higher is better)</span>
            </div>
            <v-chart v-if="wodChartOption" :option="wodChartOption" autoresize style="height:240px;margin-top:12px" />
            <table v-if="wodHistory.length" class="data-table" style="margin-top:16px">
              <thead><tr><th>Date</th><th>Score</th><th>RPE</th><th>PR</th></tr></thead>
              <tbody>
                <tr v-for="r in wodHistory" :key="(r as any).id">
                  <td>{{ (r as any).workout_date?.slice(0,10) ?? "—" }}</td>
                  <td>{{ (r as any).score_value ?? "—" }}</td>
                  <td>{{ (r as any).rpe ?? "—" }}</td>
                  <td>{{ (r as any).is_pr ? '★' : '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </div>
    </div>

    <!-- ── Tab 4: PRs ──────────────────────────────────────────── -->
    <div v-if="activeTab === 'prs'" class="tab-content">
      <div v-if="!store.prs.length" class="muted">No PRs yet. Sync data first.</div>
      <table v-else class="data-table">
        <thead><tr><th>Movement</th><th>Type</th><th>Best Weight</th><th>Best Reps</th><th>Best Time</th><th>Date</th></tr></thead>
        <tbody>
          <tr v-for="pr in store.prs" :key="pr.movement_id">
            <td>{{ pr.movement_name ?? "—" }}</td>
            <td>{{ pr.movement_type ?? "—" }}</td>
            <td>{{ pr.max_weight_kg != null ? pr.max_weight_kg + ' kg' : '—' }}</td>
            <td>{{ pr.max_reps ?? "—" }}</td>
            <td>{{ pr.best_time_s != null ? Math.floor(pr.best_time_s/60) + ':' + String(pr.best_time_s%60).padStart(2,'0') : '—' }}</td>
            <td>{{ pr.workout_date?.slice(0,10) ?? "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Tab 5: Cross-Reference ──────────────────────────────── -->
    <div v-if="activeTab === 'cross'" class="tab-content">
      <div class="toolbar">
        <label>Garmin signal:</label>
        <select v-model="crossSignal" class="select-sm">
          <option value="body_battery_max">Body Battery</option>
          <option value="hr_resting">Resting HR</option>
          <option value="sleep_score">Sleep Score</option>
          <option value="stress_avg">Stress</option>
        </select>
      </div>
      <div v-if="!store.crossRef.length" class="muted">No cross-reference data. Sync Actalog and Garmin data first.</div>
      <DualAxisChart v-else :left="crossChartLeft" :right="crossChartRight" height="300px" />
    </div>

    <!-- ── Tab 6: Calendar ─────────────────────────────────────── -->
    <div v-if="activeTab === 'calendar'" class="tab-content">
      <div class="cal-nav">
        <button class="link-btn" @click="prevMonth">◀</button>
        <span class="cal-title">{{ MONTH_NAMES[calMonth] }} {{ calYear }}</span>
        <button class="link-btn" @click="nextMonth">▶</button>
      </div>
      <div class="cal-grid">
        <div v-for="d in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']" :key="d" class="cal-header">{{ d }}</div>
        <div
          v-for="(cell, i) in calDays"
          :key="i"
          :class="['cal-cell', { empty: !cell, active: cell?.date === selectedDay, 'has-workout': cell && cell.workouts.length > 0 }]"
          @click="cell && cell.workouts.length && selectDay(cell.date)"
        >
          <template v-if="cell">
            <span class="cal-day-num">{{ cell.day }}</span>
            <div class="cal-dots">
              <span v-for="w in cell.workouts.slice(0,3)" :key="w.id"
                class="cal-dot" :style="{ background: typeColor(w.workout_type) }" />
            </div>
          </template>
        </div>
      </div>

      <!-- Session Vitals Panel -->
      <div v-if="selectedDay && store.sessionVitals" class="vitals-panel">
        <h3>{{ selectedDay }} — {{ store.sessionVitals.workout.workout_name ?? "Unnamed" }}</h3>
        <div class="vitals-meta">
          <span>Type: {{ store.sessionVitals.workout.workout_type ?? "—" }}</span>
          <span>Duration: {{ fmtDuration(store.sessionVitals.workout.total_time_s) }}</span>
        </div>
        <div v-if="store.sessionVitals.workout.movements.length">
          <p class="section-label">Movements</p>
          <table class="inner-table">
            <thead><tr><th>Sets</th><th>Reps</th><th>Weight</th><th>RPE</th><th>PR</th></tr></thead>
            <tbody>
              <tr v-for="m in store.sessionVitals.workout.movements" :key="m.id">
                <td>{{ m.sets ?? "—" }}</td><td>{{ m.reps ?? "—" }}</td>
                <td>{{ m.weight_kg != null ? m.weight_kg + ' kg' : '—' }}</td>
                <td>{{ m.rpe ?? "—" }}</td><td>{{ m.is_pr ? '★' : '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <template v-if="store.sessionVitals.has_vitals">
          <p class="section-label" style="margin-top:16px">Heart Rate During Workout</p>
          <v-chart v-if="hrChartOption" :option="hrChartOption" autoresize style="height:200px" />
        </template>
        <p v-else class="muted vitals-none">No duration recorded — heart rate window unavailable.</p>
      </div>
    </div>

    <!-- ── Tab 7: QA Review ──────────────────────────────────────── -->
    <div v-if="activeTab === 'qa'" class="tab-content">

      <!-- Filter bar -->
      <div class="qa-filter-bar">
        <button v-for="f in ['pending','approved','rejected','skipped','all']" :key="f"
          :class="['qa-filter-btn', { active: qaFilter === f }]"
          @click="qaFilter = f as any">
          {{ f.charAt(0).toUpperCase() + f.slice(1) }}
        </button>
        <span class="muted" style="margin-left:auto;font-size:0.83rem">{{ qaTotal }} records</span>
      </div>

      <div v-if="qaLoading" class="muted">Loading…</div>
      <div v-if="qaError" class="err-msg">{{ qaError }}</div>

      <!-- Record list -->
      <table v-if="!qaLoading && qaRecords.length" class="data-table qa-list">
        <thead>
          <tr>
            <th>Date</th><th>Workout</th><th>Class</th><th>Status</th><th>WODs</th><th>Model</th><th>Parsed</th><th>Time</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in qaRecords" :key="r.id"
            :class="['clickable', { 'qa-selected-row': qaSelected?.id === r.id }]"
            @click="qaSelectRecord(r)">
            <td>{{ r.workout_date ? r.workout_date.slice(0,10) : '—' }}</td>
            <td>{{ r.workout_name ?? '—' }}</td>
            <td><span :class="['qa-badge', `qa-class-${(r.content_class??'').toLowerCase()}`]">{{ r.content_class ?? '—' }}</span></td>
            <td><span :class="['qa-badge', `qa-status-${(r.parse_status??'').toLowerCase()}`]">{{ r.parse_status ?? '—' }}</span></td>
            <td>
              {{ r.parsed_json ? (JSON.parse(r.parsed_json).wods?.length ?? 0) : 0 }}
              <span v-if="qaWodMismatch(r)" class="qa-wod-warn-badge">
                ⚠ {{ qaWodMismatch(r)!.jsonCount }} WODs / {{ qaWodMismatch(r)!.mdCount }} in markdown
              </span>
            </td>
            <td class="muted">{{ r.llm_model ?? '—' }}</td>
            <td class="muted">{{ r.parsed_at ? r.parsed_at.slice(0,16).replace('T',' ') : '—' }}</td>
            <td><span v-if="r.parse_duration_s != null" class="qa-timing-chip">{{ r.parse_duration_s.toFixed(1) }}s</span></td>
          </tr>
        </tbody>
      </table>
      <div v-if="!qaLoading && !qaRecords.length" class="muted">No records for this filter.</div>

      <!-- Three-column detail panel -->
      <div v-if="qaSelected" class="qa-detail">
        <div class="qa-detail-header">
          <strong>{{ qaSelected.workout_name ?? 'Workout' }}</strong>
          <span class="muted" style="margin-left:8px;font-size:0.83rem">{{ qaSelected.workout_date?.slice(0,10) }}</span>
          <span :class="['qa-badge', `qa-status-${(qaSelected.parse_status??'').toLowerCase()}`]" style="margin-left:10px">{{ qaSelected.parse_status ?? '—' }}</span>
          <span :class="['qa-badge', `qa-class-${(qaSelected.content_class??'').toLowerCase()}`]" style="margin-left:6px">{{ qaSelected.content_class ?? '—' }}</span>
          <span v-if="qaWodMismatch(qaSelected)" class="qa-wod-warn-badge qa-wod-warn-badge--prominent" style="margin-left:10px">
            ⚠ {{ qaWodMismatch(qaSelected)!.jsonCount }} WODs / {{ qaWodMismatch(qaSelected)!.mdCount }} in markdown
          </span>
          <button class="qa-close-btn" @click="qaSelected = null">✕</button>
        </div>
        <div v-if="qaSelected.parse_duration_s != null" class="qa-timing-row">
          Wall: {{ qaSelected.parse_duration_s.toFixed(1) }}s
          <span v-if="qaSelected.llm_inference_s != null"> · Infer: {{ qaSelected.llm_inference_s.toFixed(1) }}s</span>
          <span v-if="qaSelected.llm_tokens_prompt != null"> · Prompt: {{ qaSelected.llm_tokens_prompt }} tok</span>
          <span v-if="qaSelected.llm_tokens_generated != null"> · Generated: {{ qaSelected.llm_tokens_generated }} tok</span>
        </div>

        <div class="qa-three-col">

          <!-- Column 1: Raw notes (read-only) -->
          <div class="qa-col">
            <div class="qa-col-label">Raw Notes <span class="muted">(original)</span></div>
            <pre class="qa-raw">{{ qaSelected.raw_notes ?? '—' }}</pre>
          </div>

          <!-- Column 2: Structured WOD view -->
          <div class="qa-col">
            <div class="qa-col-label">Structured WOD View <span class="muted">(model output)</span></div>
            <div v-if="qaParsedWods.length === 0" class="muted">No WODs extracted.</div>
            <div v-for="(wod, wi) in qaParsedWods" :key="wi" class="qa-wod-card">
              <div class="qa-wod-name">
                {{ wod.name }}
                <span v-if="wod.alt_name" class="qa-alt-name">/ {{ wod.alt_name }}</span>
                <span v-if="wod.name_source" class="qa-source-badge">{{ wod.name_source }}</span>
              </div>
              <div class="qa-wod-meta">
                <span v-if="wod.regime" class="qa-meta-chip">{{ wod.regime }}</span>
                <span v-if="wod.score_type" class="qa-meta-chip">Score: {{ wod.score_type }}</span>
                <span v-if="wod.rpe" class="qa-meta-chip">RPE {{ wod.rpe }}</span>
              </div>
              <div v-if="wod.intended_stimulus" class="qa-stimulus">{{ wod.intended_stimulus }}</div>
              <template v-for="tier in ['rx','intermediate','foundations']" :key="tier">
                <template v-if="(wod.scaling_tiers as any)?.[tier]?.length">
                  <div class="qa-tier-label">{{ tier.toUpperCase() }}</div>
                  <div v-for="(mv, mi) in (wod.scaling_tiers as any)[tier]" :key="mi" class="qa-movement">
                    <span class="qa-mv-name">{{ mv.movement }}</span>
                    <span v-if="mv.sets" class="qa-mv-detail">{{ mv.sets }} sets</span>
                    <span v-if="mv.reps" class="qa-mv-detail">× {{ mv.reps }}</span>
                    <span v-if="mv.weight_lbs" class="qa-mv-detail">@ {{ mv.weight_lbs }}#</span>
                    <span v-if="mv.notes" class="qa-mv-note">{{ mv.notes }}</span>
                  </div>
                </template>
              </template>
            </div>
            <div v-if="qaPerformanceNotes" class="qa-perf-notes">
              <div class="qa-col-label" style="margin-top:12px">Performance Notes</div>
              <p class="qa-perf-text">{{ qaPerformanceNotes }}</p>
            </div>
            <div v-if="qaSelected.error_message" class="err-msg" style="margin-top:8px">{{ qaSelected.error_message }}</div>
          </div>

          <!-- Column 3: Editable Markdown -->
          <div class="qa-col">
            <div class="qa-col-label">Markdown Source <span class="muted">(edit before approving)</span></div>
            <textarea v-model="qaEditMarkdown" class="qa-md-editor" placeholder="No markdown generated" />
          </div>

          <div class="qa-col">
            <div class="qa-col-label">Rendered Preview <span class="muted">(live)</span></div>
            <div class="qa-md-preview" v-html="qaMarkdownHtml" />
          </div>

        </div>

        <!-- Action row -->
        <div class="qa-actions">
          <button class="btn-primary" :disabled="qaActionBusy" @click="qaApprove">Approve</button>
          <button class="btn-secondary" :disabled="qaActionBusy" @click="qaReparse">Re-parse</button>
          <button class="btn-danger" :disabled="qaActionBusy" @click="qaReject">Reject</button>
          <span v-if="qaActionMsg" :class="qaActionOk ? 'qa-ok-msg' : 'err-msg'">{{ qaActionMsg }}</span>
        </div>
      </div>
    </div>

    <!-- ── Tab 8: Review ───────────────────────────────────────── -->
    <div v-if="activeTab === 'review'" class="tab-content">
      <ReviewQueue />
    </div>

    <!-- ── Tab 9: Settings ─────────────────────────────────────── -->
    <div v-if="activeTab === 'settings'" class="tab-content settings-panel">
      <div v-if="settingsLoading" class="muted">Loading config...</div>
      <template v-else>
        <h3 class="settings-section-title">Actalog Connection</h3>
        <div class="field-row">
          <label>Base URL</label>
          <input v-model="settingsForm.url" class="input-sm" placeholder="https://al.example.com" />
        </div>
        <div class="field-row">
          <label>Email</label>
          <input v-model="settingsForm.email" class="input-sm" type="email" />
        </div>
        <div class="field-row">
          <label>Password</label>
          <input
            v-model="settingsForm.password"
            class="input-sm"
            :type="settingsShowPw ? 'text' : 'password'"
            placeholder="Leave blank to keep existing"
          />
          <button class="link-btn" @click="settingsShowPw = !settingsShowPw">{{ settingsShowPw ? 'Hide' : 'Show' }}</button>
        </div>
        <div class="field-row">
          <label>Sync Enabled</label>
          <input v-model="settingsForm.sync_enabled" type="checkbox" />
        </div>
        <div class="action-row" style="margin-bottom: 4px">
          <button class="btn-secondary" @click="testSettingsConnection">Test Connection</button>
        </div>

        <h3 class="settings-section-title" style="margin-top: 24px">Parser</h3>
        <div class="field-row">
          <label>Ollama URL</label>
          <input v-model="settingsForm.ollama_url" class="input-sm" placeholder="http://localhost:11434" />
        </div>
        <div class="field-row">
          <label>Model</label>
          <input v-model="settingsForm.model" class="input-sm" placeholder="qwen2.5:7b" />
        </div>
        <div class="field-row">
          <label>Min Note Length</label>
          <input v-model.number="settingsForm.min_note_length" class="input-sm" type="number" min="1" style="min-width:80px;max-width:120px" />
          <span class="muted" style="font-size:0.78rem">chars -- shorter notes are skipped</span>
        </div>
        <div class="field-row prompt-row">
          <label style="align-self:flex-start;padding-top:4px">System Prompt</label>
          <textarea v-model="settingsForm.system_prompt" class="prompt-textarea" rows="10" spellcheck="false" />
        </div>

        <div class="action-row" style="margin-top: 16px">
          <button class="btn-primary" @click="saveSettingsConfig">Save Config</button>
          <button class="btn-secondary" :disabled="settingsParserRunning" @click="settingsRunParser">
            {{ settingsParserRunning ? 'Running...' : 'Run Parser Now' }}
          </button>
          <button class="btn-danger" :disabled="settingsParserRunning" @click="settingsReparseAll">
            {{ settingsParserRunning ? 'Running...' : 'Reparse All Non-Approved' }}
          </button>
        </div>
        <div v-if="settingsMsg" :class="['status-msg', settingsMsgOk ? 'ok' : 'err']" style="margin-top: 8px">{{ settingsMsg }}</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { font-size: 1.4rem; font-weight: 700; color: var(--text); }

.tab-bar { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.tab-btn { padding: 8px 14px; font-size: 0.82rem; font-weight: 500; color: var(--muted); background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; transition: color 0.12s, border-color 0.12s; }
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

.muted { color: var(--muted); font-size: 0.85rem; padding: 24px 0; }
.section-label { font-size: 0.75rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }

.data-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.data-table th { text-align: left; padding: 6px 10px; color: var(--muted); font-weight: 600; font-size: 0.75rem; border-bottom: 1px solid var(--border); }
.data-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text); }
.workout-row:hover { background: var(--bg); }

.type-badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 0.75rem; font-weight: 600; }

.expand-row td { padding: 0; }
.expand-body { padding: 12px 16px; background: var(--bg); border-bottom: 1px solid var(--border); }
.inner-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.inner-table th, .inner-table td { padding: 4px 8px; border-bottom: 1px solid var(--border); }

.notes-text { font-size: 0.82rem; color: var(--muted); margin-top: 8px; font-style: italic; }
.link-btn { background: none; border: none; color: var(--accent); font-size: 0.82rem; cursor: pointer; padding: 2px 4px; }

.split-layout { display: flex; gap: 20px; }
.split-sidebar { width: 200px; flex-shrink: 0; }
.split-main { flex: 1; min-width: 0; }
.movement-list { display: flex; flex-direction: column; gap: 2px; max-height: 400px; overflow-y: auto; }
.movement-item { text-align: left; padding: 6px 10px; border-radius: 6px; font-size: 0.82rem; color: var(--text); background: none; border: none; cursor: pointer; }
.movement-item:hover { background: var(--bg); }
.movement-item.active { background: var(--accent-light); color: var(--accent); font-weight: 600; }

.wod-meta { font-size: 0.83rem; color: var(--muted); margin-bottom: 8px; }
.wod-regime { color: var(--muted); font-size: 0.78rem; }

.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; font-size: 0.83rem; color: var(--muted); }
.select-sm { padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); font-size: 0.82rem; color: var(--text); background: var(--surface); }

.cal-nav { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.cal-title { font-size: 1rem; font-weight: 600; color: var(--text); }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-header { font-size: 0.72rem; font-weight: 600; color: var(--muted); text-align: center; padding: 4px; }
.cal-cell { min-height: 60px; border-radius: 8px; border: 1px solid var(--border); padding: 6px; background: var(--surface); }
.cal-cell.empty { border: none; background: none; }
.cal-cell.has-workout { cursor: pointer; }
.cal-cell.has-workout:hover { background: var(--bg); }
.cal-cell.active { border-color: var(--accent); background: var(--accent-light); }
.cal-day-num { font-size: 0.8rem; color: var(--muted); }
.cal-dots { display: flex; gap: 3px; margin-top: 4px; }
.cal-dot { width: 7px; height: 7px; border-radius: 50%; }

.vitals-panel { margin-top: 24px; padding: 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
.vitals-panel h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 8px; }
.vitals-meta { display: flex; gap: 20px; font-size: 0.83rem; color: var(--muted); margin-bottom: 12px; }
.vitals-none { font-style: italic; margin-top: 12px; }
.err-msg { color: #EF4444; font-size: 0.83rem; padding: 8px 0; }

/* QA Review tab */
.qa-filter-bar { display: flex; gap: 6px; align-items: center; margin-bottom: 16px; }
.qa-filter-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; font-size: 0.83rem; }
.qa-filter-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.qa-list td, .qa-list th { font-size: 0.83rem; }
.qa-selected-row { background: var(--accent-light) !important; }
.qa-badge { padding: 2px 7px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.qa-class-workout   { background: #dcfce7; color: #166534; }
.qa-class-mixed     { background: #fef9c3; color: #854d0e; }
.qa-class-performance_only { background: #dbeafe; color: #1e40af; }
.qa-class-skip      { background: var(--surface); color: var(--muted); }
.qa-status-pending  { background: #fef9c3; color: #854d0e; }
.qa-status-approved { background: #dcfce7; color: #166534; }
.qa-status-rejected { background: #fee2e2; color: #991b1b; }
.qa-status-skipped  { background: var(--surface); color: var(--muted); }

.qa-detail { margin-top: 20px; border: 1px solid var(--border); border-radius: 12px; padding: 16px; background: var(--surface); }
.qa-detail-header { display: flex; align-items: center; margin-bottom: 14px; font-size: 1rem; }
.qa-close-btn { margin-left: auto; background: none; border: none; cursor: pointer; color: var(--muted); font-size: 1rem; }

.qa-three-col { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px; align-items: start; }
.qa-col { display: flex; flex-direction: column; gap: 8px; }
.qa-col-label { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
.qa-raw { font-size: 0.78rem; white-space: pre-wrap; word-break: break-word; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px; max-height: 480px; overflow-y: auto; color: var(--text); font-family: monospace; }

.qa-wod-card { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.qa-wod-name { font-weight: 700; font-size: 0.95rem; color: var(--text); margin-bottom: 6px; }
.qa-alt-name { font-weight: 400; color: var(--muted); font-size: 0.85rem; }
.qa-source-badge { margin-left: 6px; font-size: 0.7rem; padding: 1px 5px; border-radius: 4px; background: var(--accent-light); color: var(--accent); font-weight: 600; }
.qa-wod-meta { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.qa-meta-chip { font-size: 0.75rem; padding: 2px 7px; border-radius: 4px; background: var(--surface); border: 1px solid var(--border); color: var(--text); }
.qa-stimulus { font-size: 0.78rem; color: var(--muted); font-style: italic; margin-bottom: 6px; }
.qa-tier-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: var(--accent); margin: 6px 0 3px; }
.qa-movement { display: flex; gap: 6px; align-items: baseline; font-size: 0.82rem; padding: 2px 0; }
.qa-mv-name { color: var(--text); font-weight: 500; }
.qa-mv-detail { color: var(--muted); }
.qa-mv-note { font-style: italic; color: var(--muted); font-size: 0.78rem; }
.qa-perf-text { font-size: 0.83rem; color: var(--text); background: var(--bg); border-left: 3px solid var(--accent); padding: 6px 10px; border-radius: 0 6px 6px 0; }

.qa-md-editor { width: 100%; min-height: 420px; font-family: monospace; font-size: 0.82rem; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 10px; resize: vertical; line-height: 1.5; }

.qa-actions { display: flex; gap: 10px; align-items: center; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border); }
.btn-primary { padding: 7px 18px; background: var(--accent); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { padding: 7px 18px; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger { padding: 7px 18px; background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; border-radius: 6px; cursor: pointer; font-weight: 600; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.qa-ok-msg { color: #166534; font-size: 0.83rem; }
.qa-timing-chip { font-size: 0.72rem; padding: 1px 6px; border-radius: 4px; background: var(--surface); border: 1px solid var(--border); color: var(--muted); white-space: nowrap; }
.qa-timing-row { font-size: 0.78rem; color: var(--muted); margin-bottom: 10px; }
.qa-wod-warn-badge { display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; background: #fef9c3; color: #854d0e; border: 1px solid #fde68a; white-space: nowrap; vertical-align: middle; margin-left: 6px; }
.qa-wod-warn-badge--prominent { font-size: 0.82rem; padding: 3px 10px; }

/* Rendered markdown preview panel */
.qa-md-preview {
  font-size: 0.83rem;
  line-height: 1.65;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  max-height: 480px;
  overflow-y: auto;
  color: var(--text);
}
.qa-md-preview h1 { font-size: 1.1rem; font-weight: 700; margin: 0 0 6px; color: var(--text); }
.qa-md-preview h2 { font-size: 0.97rem; font-weight: 700; margin: 10px 0 4px; }
.qa-md-preview h3 { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--accent); margin: 10px 0 4px; }
.qa-md-preview p  { margin: 4px 0; }
.qa-md-preview ul { padding-left: 18px; margin: 4px 0; }
.qa-md-preview li { margin: 2px 0; }
.qa-md-preview strong { font-weight: 700; }
.qa-md-preview em   { font-style: italic; color: var(--muted); }
.qa-md-preview hr   { border: none; border-top: 1px solid var(--border); margin: 10px 0; }
.qa-md-preview code { font-family: monospace; font-size: 0.82rem; background: var(--surface); padding: 1px 4px; border-radius: 3px; }
.qa-md-empty { color: var(--muted); font-style: italic; }

/* Tab badge for pending count */
.tab-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 99px; background: #f59e0b; color: #fff; font-size: 0.68rem; font-weight: 700; margin-left: 5px; vertical-align: middle; }

/* Settings tab */
.settings-panel { max-width: 700px; }
.settings-section-title { font-size: 0.95rem; font-weight: 700; color: var(--text); margin-bottom: 12px; }
.field-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 0.83rem; }
.field-row label { min-width: 120px; color: var(--muted); font-weight: 600; font-size: 0.82rem; }
.input-sm { padding: 5px 10px; border-radius: 6px; border: 1px solid var(--border); font-size: 0.83rem; color: var(--text); background: var(--surface); flex: 1; min-width: 200px; }
.prompt-row { align-items: flex-start; }
.prompt-textarea { flex: 1; min-height: 180px; font-family: monospace; font-size: 0.82rem; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 10px; resize: vertical; line-height: 1.5; }
.action-row { display: flex; gap: 10px; align-items: center; margin-top: 12px; }
.status-msg { font-size: 0.83rem; padding: 4px 0; }
.status-msg.ok { color: #166534; }
.status-msg.err { color: #EF4444; }
</style>
