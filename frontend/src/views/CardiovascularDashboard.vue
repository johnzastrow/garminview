<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Cardiovascular</h1>
        <p class="page-sub">Resting HR, Body Battery, intraday HR, and HR zone distribution</p>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading data…</span>
    </div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <MetricCard
          label="Resting HR"
          :value="latest?.hr_resting"
          unit="bpm"
          :spark-data="series('hr_resting')"
          color="#E5341D"
        />
        <MetricCard
          label="Body Battery"
          :value="latest?.body_battery_max"
          :spark-data="series('body_battery_max')"
          color="#16A34A"
        />
        <MetricCard
          label="HR Min"
          :value="latest?.hr_min"
          unit="bpm"
          :spark-data="series('hr_min')"
          color="#7C3AED"
        />
        <MetricCard
          label="HR Max"
          :value="latest?.hr_max"
          unit="bpm"
          :spark-data="series('hr_max')"
          color="#DC2626"
        />
      </div>

      <div class="range-row">
        <span class="range-label">Showing</span>
        <DateRangePicker />
      </div>

      <div class="charts">
        <div class="chart-block">
          <h2 class="chart-title">Resting Heart Rate</h2>
          <p class="chart-desc">Resting heart rate (RHR) measured each morning before activity. Lower RHR generally indicates better cardiovascular fitness. A sudden increase of 5+ bpm can signal illness, overtraining, or poor recovery — worth monitoring alongside HRV.</p>
          <TimeSeriesChart
            v-if="rhrSeries.length"
            :series="rhrSeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No resting HR data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Body Battery</h2>
          <p class="chart-desc">Garmin's estimate of energy reserves (0–100), computed from sleep quality, HRV, and stress levels. Values above 75 indicate readiness for hard training; below 25 suggests prioritizing recovery. Daily minimum (trough) is often more telling than the maximum.</p>
          <TimeSeriesChart
            v-if="batterySeries.length"
            :series="batterySeries"
          />
          <p v-else class="empty">No body battery data in range.</p>
        </div>

        <div class="chart-block">
          <h2 class="chart-title">Daily HR Range</h2>
          <p class="chart-desc">Daily minimum and maximum heart rate. A wide spread between resting and active HR indicates good cardiovascular flexibility. A persistently elevated minimum HR is an early stress or illness indicator.</p>
          <TimeSeriesChart
            v-if="hrRangeSeries.length"
            :series="hrRangeSeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No HR range data in range.</p>
        </div>

        <!-- HR Zones -->
        <div class="chart-block">
          <h2 class="chart-title">HR Zone Distribution</h2>
          <p class="chart-desc">Time spent in each of the five Garmin HR zones across all activities in the selected period. Zone 1–2 (easy aerobic) builds base fitness without accumulating fatigue. Zone 3 is "moderate" — physiologically useful but harder to recover from than zones 1–2. Zone 4–5 develops speed and VO₂max but requires more recovery time. A balanced training program typically has 80% of volume in zones 1–2 and 20% in zones 3–5.</p>
          <div v-if="zonesLoading" class="loading" style="padding: 16px 0;"><div class="spinner"></div><span>Loading zone data…</span></div>
          <div v-else-if="hrZoneRows?.length" class="zones-layout">
            <div class="zone-bars">
              <div v-for="z in hrZoneRows" :key="z.zone" class="zone-row">
                <div class="zone-label" :style="{ color: zoneColor(z.zone) }">Z{{ z.zone }}</div>
                <div class="zone-meta">
                  <div class="zone-name-text">{{ zoneName(z.zone) }}</div>
                  <div class="zone-bpm" v-if="zoneBpmLabel(z.zone)">{{ zoneBpmLabel(z.zone) }}</div>
                </div>
                <div class="zone-bar-wrap">
                  <div class="zone-bar" :style="{ width: zoneBarWidth(z.total_s) + '%', background: zoneColor(z.zone) }"></div>
                </div>
                <div class="zone-time">{{ fmtHM(z.total_s) }}</div>
                <div class="zone-pct">{{ zonePct(z.total_s) }}%</div>
              </div>
            </div>
            <div class="zones-method-note" v-if="athleteZones.length">
              Zone boundaries via Karvonen method —
              <RouterLink to="/profile" class="profile-link">edit in Athlete Profile</RouterLink>
            </div>
          </div>
          <p v-else class="empty">No HR zone data in range. HR zone data requires activities with HR recorded.</p>
        </div>

        <!-- Intraday HR -->
        <div class="chart-block">
          <h2 class="chart-title">Intraday Heart Rate</h2>
          <p class="chart-desc">Minute-by-minute HR throughout a single day (5-min averages). Resting periods show your true baseline; spikes indicate exercise or stress. Use the date picker below to navigate to any day. A healthy daily pattern shows a low overnight baseline, sharp rise during exercise, and return to baseline within 30–60 minutes post-workout.</p>
          <div class="intraday-controls">
            <label class="intraday-label">Day</label>
            <input type="date" v-model="intradayDate" class="date-input" :max="today" />
          </div>
          <div v-if="intradayLoading" class="loading" style="padding: 16px 0;"><div class="spinner"></div><span>Loading HR data…</span></div>
          <TimeSeriesChart
            v-else-if="intradaySeries.length"
            :series="intradaySeries"
            y-axis-label="BPM"
          />
          <p v-else class="empty">No intraday HR data for this day.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { RouterLink } from "vue-router"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import TimeSeriesChart from "@/components/charts/TimeSeriesChart.vue"
import { useMetricData } from "@/composables/useMetricData"
import { api } from "@/api/client"

interface DailySummary {
  date: string
  hr_min: number | null
  hr_max: number | null
  hr_resting: number | null
  body_battery_max: number | null
  body_battery_min: number | null
}

interface HRZoneRow {
  zone: number
  total_s: number
}

interface IntradayHRRow {
  timestamp: string
  hr: number
}

interface AthleteZone {
  zone: number
  name: string
  min_bpm: number
  max_bpm: number
}

const { data, loading, error } = useMetricData<DailySummary[]>("/health/daily")
const { data: hrZoneRows, loading: zonesLoading } = useMetricData<HRZoneRow[]>("/activities/hr-zones")

const athleteZones = ref<AthleteZone[]>([])
api.get("/admin/athlete-metrics").then(r => { athleteZones.value = r.data.hr_zones ?? [] }).catch(() => {})

function zoneBpmLabel(zone: number): string {
  const z = athleteZones.value.find(z => z.zone === zone)
  return z ? `${z.min_bpm}–${z.max_bpm} bpm` : ""
}
function zoneName(zone: number): string {
  const z = athleteZones.value.find(z => z.zone === zone)
  return z ? z.name : `Zone ${zone}`
}

const latest = computed(() => data.value?.[data.value.length - 1] ?? null)
const today = new Date().toISOString().slice(0, 10)
const intradayDate = ref(today)
const intradayLoading = ref(false)
const intradayData = ref<IntradayHRRow[]>([])

async function fetchIntraday(date: string) {
  intradayLoading.value = true
  try {
    const resp = await api.get("/health/intraday-hr", { params: { date } })
    intradayData.value = resp.data
  } catch {
    intradayData.value = []
  } finally {
    intradayLoading.value = false
  }
}

watch(intradayDate, fetchIntraday, { immediate: true })

function series(key: keyof DailySummary) {
  return data.value?.map((d) => d[key] as number | null) ?? []
}

const rhrSeries = computed(() => {
  if (!data.value) return []
  return [{ name: "Resting HR", data: data.value.map((d) => [d.date, d.hr_resting] as [string, number | null]), color: "#E5341D", smooth: true }]
})

const batterySeries = computed(() => {
  if (!data.value) return []
  return [
    { name: "Battery Max", data: data.value.map((d) => [d.date, d.body_battery_max] as [string, number | null]), color: "#16A34A", smooth: true },
    { name: "Battery Min", data: data.value.map((d) => [d.date, d.body_battery_min] as [string, number | null]), color: "#86EFAC", smooth: true },
  ]
})

const hrRangeSeries = computed(() => {
  if (!data.value) return []
  return [
    { name: "HR Max", data: data.value.map((d) => [d.date, d.hr_max] as [string, number | null]), color: "#DC2626", smooth: true },
    { name: "HR Min", data: data.value.map((d) => [d.date, d.hr_min] as [string, number | null]), color: "#7C3AED", smooth: true },
  ]
})

const intradaySeries = computed(() => {
  if (!intradayData.value.length) return []
  return [{
    name: "Heart Rate",
    data: intradayData.value.map(r => [r.timestamp, r.hr] as [string, number]),
    color: "#E5341D",
    smooth: true,
  }]
})

// HR Zones helpers
const ZONE_COLORS = ["#60A5FA", "#34D399", "#FBBF24", "#F97316", "#EF4444"]
const ZONE_NAMES = ["Zone 1 — Recovery", "Zone 2 — Aerobic Base", "Zone 3 — Tempo", "Zone 4 — Threshold", "Zone 5 — VO₂max"]

function zoneColor(zone: number) { return ZONE_COLORS[(zone - 1) % 5] }
const totalZoneSeconds = computed(() => (hrZoneRows.value ?? []).reduce((s, z) => s + z.total_s, 0))
function zoneBarWidth(s: number) {
  const total = totalZoneSeconds.value
  return total ? Math.round((s / total) * 100) : 0
}
function zonePct(s: number) {
  const total = totalZoneSeconds.value
  return total ? Math.round((s / total) * 100) : 0
}
function fmtHM(secs: number): string {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); font-weight: 400; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }
.charts { display: flex; flex-direction: column; gap: 16px; }
.chart-block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 20px 8px; }
.chart-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 4px; }
.chart-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 12px; line-height: 1.5; }

/* HR Zones */
.zones-layout { padding: 8px 0 16px; }
.zone-bars { display: flex; flex-direction: column; gap: 10px; }
.zone-row { display: flex; align-items: center; gap: 10px; }
.zone-label { font-size: 0.75rem; font-weight: 800; width: 22px; flex-shrink: 0; }
.zone-meta { width: 140px; flex-shrink: 0; }
.zone-name-text { font-size: 0.75rem; font-weight: 600; color: var(--text); }
.zone-bpm { font-size: 0.68rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.zone-bar-wrap { flex: 1; height: 16px; background: var(--bg); border-radius: 4px; overflow: hidden; }
.zone-bar { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
.zone-time { font-size: 0.78rem; color: var(--text); width: 54px; text-align: right; font-variant-numeric: tabular-nums; }
.zone-pct { font-size: 0.72rem; color: var(--muted); width: 34px; text-align: right; }
.zones-method-note { font-size: 0.72rem; color: var(--muted); margin-top: 8px; }
.profile-link { color: var(--accent); text-decoration: none; }
.profile-link:hover { text-decoration: underline; }

/* Intraday */
.intraday-controls { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.intraday-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; }
.date-input {
  font-size: 0.82rem;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text);
  outline: none;
  cursor: pointer;
}
.date-input:focus { border-color: var(--accent); }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
.empty { font-size: 0.85rem; color: var(--muted); padding: 20px 0; }
</style>
