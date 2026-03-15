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
import { api } from "@/api/client"

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent, CanvasRenderer])

const store = useActalogStore()
const dateRange = useDateRangeStore()

const activeTab = ref<"workouts" | "movements" | "wods" | "prs" | "cross" | "calendar">("workouts")

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

async function loadMovements() {
  const { data } = await api.get("/actalog/movements")
  movements.value = data
}

async function selectMovement(id: number) {
  selectedMovement.value = id
  const { data } = await api.get(`/actalog/movements/${id}/history`)
  movementHistory.value = data
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
  const { data } = await api.get("/actalog/wods")
  wods.value = data
}

async function selectWod(id: number) {
  selectedWod.value = id
  const { data } = await api.get(`/actalog/wods/${id}/history`)
  wodHistory.value = data
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

function calDays(): Array<{ date: string; day: number; workouts: WorkoutListItem[] } | null> {
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
}

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

// ── Lifecycle ────────────────────────────────────────────────────────
onMounted(async () => {
  await store.fetchWorkouts(dateRange.startDate, dateRange.endDate)
  await store.fetchPRs()
  await store.fetchCrossRef(dateRange.startDate, dateRange.endDate)
  await loadMovements()
  await loadWods()
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
      <button v-for="tab in ['workouts','movements','wods','prs','cross','calendar']" :key="tab"
        :class="['tab-btn', { active: activeTab === tab }]"
        @click="activeTab = tab as any">
        {{ ({ workouts: 'Workouts', movements: 'Movements', wods: 'WODs', prs: 'Personal Records', cross: 'Cross-Reference', calendar: 'Calendar' } as Record<string,string>)[tab] }}
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
          v-for="(cell, i) in calDays()"
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
        <h3>{{ selectedDay }} — {{ store.sessionVitals.workout.workout_name }}</h3>
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
</style>
