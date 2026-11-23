<template>
  <div class="page">
    <PageHeader section="Body" title="Sleep" :summary="headline">
      <span class="label">Range</span>
      <RangeToggle />
    </PageHeader>

    <StatusLine v-if="error" kind="error">{{ error }}</StatusLine>
    <StatusLine v-else-if="!loading && data && !recorded.length" kind="info">
      No recorded nights in this range. Pick a longer range.
    </StatusLine>

    <template v-if="recorded.length">
      <div class="tiles">
        <KpiTile
          label="Last night"
          :value="fmtHMShort(last?.total)"
          unit="h"
          color="var(--d-sleep)"
          :foot="`Avg ${fmtHM(avg.total)} over ${recorded.length} nights`"
          :scale="{ min: 4, max: 10, value: last?.total != null ? last.total / 60 : null, band: [7, 9], divisions: 12 }"
        />
        <KpiTile
          label="Sleep score"
          :value="last?.score != null ? String(last.score) : '--'"
          unit="/ 100"
          color="var(--text)"
          :foot="`${cap(scoreBand(last?.score ?? null) ?? 'no score')}. Avg ${fmt0(avg.score)}`"
          :scale="{ min: 40, max: 100, value: last?.score ?? null, band: [80, 100], divisions: 12 }"
        />
        <KpiTile
          label="Deep sleep"
          :value="fmt0(lastShare.deep)"
          unit="%"
          color="var(--d-deep)"
          :foot="`${fmtHM(last?.deep)}. Avg ${fmt0(avg.deepShare)}%, target 15-25%`"
          :scale="{ min: 0, max: 40, value: lastShare.deep, band: [15, 25], divisions: 8 }"
        />
        <KpiTile
          label="REM sleep"
          :value="fmt0(lastShare.rem)"
          unit="%"
          color="var(--d-rem)"
          :foot="`${fmtHM(last?.rem)}. Avg ${fmt0(avg.remShare)}%, target 20-25%`"
          :scale="{ min: 0, max: 40, value: lastShare.rem, band: [20, 25], divisions: 8 }"
        />
      </div>

      <Panel title="Nightly duration">
        <template #extra>
          <span class="key"><i class="sw" style="background: var(--d-sleep)"></i>Night</span>
          <span class="key"><i class="ln"></i>7-night average</span>
          <span class="key"><i class="sw band"></i>7-9 h target</span>
          <span v-if="missingCount" class="num">{{ missingCount }} not recorded</span>
        </template>
        <EChart :option="durationOption" :height="250" />
      </Panel>

      <div class="two">
        <Panel title="Stages, share of the night">
          <template #extra>
            <span v-for="s in STAGES" :key="s.key" class="key"><i class="sw" :style="{ background: s.css }"></i>{{ s.name }}</span>
          </template>
          <EChart :option="stageOption" :height="230" />
        </Panel>
        <Panel title="Sleep score">
          <template #extra><span>Bands: 60 fair, 80 good, 90 excellent</span></template>
          <EChart :option="scoreOption" :height="230" />
        </Panel>
      </div>

      <Panel title="Recent nights" flush>
        <div class="tablewrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Night of</th>
                <th scope="col" class="r">Duration</th>
                <th scope="col" class="r">Score</th>
                <th scope="col" class="r">Deep</th>
                <th scope="col" class="r">Light</th>
                <th scope="col" class="r">REM</th>
                <th scope="col" class="r">Awake</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="n in recent" :key="n.date">
                <td>{{ fmtDay(n.date) }}</td>
                <template v-if="n.total != null">
                  <td class="r num">{{ fmtHM(n.total) }}</td>
                  <td class="r num">
                    {{ n.score ?? "--" }} <span class="band-word">{{ scoreBand(n.score) ?? "" }}</span>
                  </td>
                  <td class="r num">{{ fmtHM(n.deep) }}</td>
                  <td class="r num">{{ fmtHM(n.light) }}</td>
                  <td class="r num">{{ fmtHM(n.rem) }}</td>
                  <td class="r num">{{ fmtHM(n.awake) }}</td>
                </template>
                <td v-else colspan="6" class="r none">Not recorded</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </template>

    <p v-else-if="loading" class="muted loading">Loading sleep data...</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import dayjs from "dayjs"
import PageHeader from "@/components/ui/PageHeader.vue"
import RangeToggle from "@/components/ui/RangeToggle.vue"
import KpiTile from "@/components/ui/KpiTile.vue"
import Panel from "@/components/ui/Panel.vue"
import StatusLine from "@/components/ui/StatusLine.vue"
import EChart from "@/components/charts/EChart.vue"
import { T, esc } from "@/charts/theme"
import { useRangeData } from "@/utils/useRangeData"
import {
  type SleepRow,
  normalizeNights,
  rollingMean,
  mean,
  stageShare,
  fmtHM,
  scoreBand,
  lastRecorded,
} from "@/utils/sleep"

const { data, loading, error } = useRangeData<SleepRow[]>("/health/sleep")

const nights = computed(() => normalizeNights(data.value ?? []))
const recorded = computed(() => nights.value.filter((n) => n.total != null))
const missingCount = computed(() => nights.value.length - recorded.value.length)
const last = computed(() => lastRecorded(nights.value))
const recent = computed(() => nights.value.slice(-10).reverse())

const lastShare = computed(() => ({
  deep: stageShare(last.value?.deep ?? null, last.value?.total ?? null),
  rem: stageShare(last.value?.rem ?? null, last.value?.total ?? null),
}))
const avg = computed(() => ({
  total: mean(recorded.value.map((n) => n.total)),
  score: mean(recorded.value.map((n) => n.score)),
  deepShare: mean(recorded.value.map((n) => stageShare(n.deep, n.total))),
  remShare: mean(recorded.value.map((n) => stageShare(n.rem, n.total))),
}))

const fmt0 = (v: number | null | undefined) => (v == null ? "--" : Math.round(v).toString())
const fmtHMShort = (min: number | null | undefined) => {
  if (min == null) return "--"
  const m = Math.round(min)
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`
}
const fmtDay = (d: string) => dayjs(d).format("ddd D MMM")
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

const headline = computed(() => {
  const n = last.value
  if (!n) return "Duration, stages and score, night by night."
  const band = scoreBand(n.score)
  return `Last recorded night ${fmtDay(n.date)}: ${fmtHM(n.total)}, score ${n.score ?? "--"}${band ? ` (${band})` : ""}.`
})

// ---- Chart options -------------------------------------------------------------------

const xDates = computed(() => nights.value.map((n) => dayjs(n.date).format("D MMM")))
const baseGrid = { left: 44, right: 16, top: 14, bottom: 26 }
const xAxis = computed(() => ({
  type: "category",
  data: xDates.value,
  axisLabel: { hideOverlap: true },
}))

function tip(rows: [string, string, string][], title: string) {
  return (
    `<div style="margin-bottom:4px;color:${T.muted}">${esc(title)}</div>` +
    rows
      .map(
        ([color, name, val]) =>
          `<div style="display:flex;gap:10px;justify-content:space-between"><span><i style="display:inline-block;width:8px;height:8px;margin-right:6px;background:${color}"></i>${esc(name)}</span><span>${esc(val)}</span></div>`,
      )
      .join("")
  )
}

const durationOption = computed(() => {
  const hours = nights.value.map((n) => (n.total == null ? null : +(n.total / 60).toFixed(2)))
  const roll = rollingMean(hours).map((v) => (v == null ? null : +v.toFixed(2)))
  return {
    grid: baseGrid,
    xAxis: xAxis.value,
    yAxis: { type: "value", min: 0, max: 11, interval: 2, axisLabel: { formatter: "{value} h" } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(212,228,245,0.05)" } },
      formatter: (p: { dataIndex: number }[]) => {
        const i = p[0]?.dataIndex ?? 0
        const n = nights.value[i]!
        return tip(
          [
            [T.sleep, "Night", n.total == null ? "not recorded" : fmtHM(n.total)],
            [T.text, "7-night avg", roll[i] == null ? "--" : fmtHM(roll[i]! * 60)],
          ],
          fmtDay(n.date),
        )
      },
    },
    series: [
      {
        name: "Night",
        type: "bar",
        data: hours,
        barMaxWidth: 10,
        itemStyle: { color: T.sleep, opacity: 0.85 },
        markArea: {
          silent: true,
          itemStyle: { color: "rgba(212,228,245,0.06)" },
          data: [[{ yAxis: 7 }, { yAxis: 9 }]],
        },
      },
      {
        name: "7-night average",
        type: "line",
        data: roll,
        symbol: "none",
        connectNulls: false,
        lineStyle: { color: T.text, width: 1.5 },
        z: 3,
      },
    ],
  }
})

const STAGES = [
  { key: "deep", name: "Deep", color: T.deep, css: "var(--d-deep)" },
  { key: "light", name: "Light", color: T.light, css: "var(--d-light)" },
  { key: "rem", name: "REM", color: T.rem, css: "var(--d-rem)" },
  { key: "awake", name: "Awake", color: T.awake, css: "var(--d-awake)" },
] as const

const stageOption = computed(() => {
  // Shares of time in bed (stages plus awake), so each bar sums to 100%.
  const shares = nights.value.map((n) => {
    if (n.total == null) return null
    const bed = (n.deep ?? 0) + (n.light ?? 0) + (n.rem ?? 0) + (n.awake ?? 0)
    return bed ? { deep: n.deep! / bed, light: n.light! / bed, rem: n.rem! / bed, awake: (n.awake ?? 0) / bed } : null
  })
  return {
    grid: baseGrid,
    xAxis: xAxis.value,
    yAxis: { type: "value", min: 0, max: 100, interval: 25, axisLabel: { formatter: "{value}%" } },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(212,228,245,0.05)" } },
      formatter: (p: { dataIndex: number }[]) => {
        const i = p[0]?.dataIndex ?? 0
        const n = nights.value[i]!
        if (n.total == null) return tip([], `${fmtDay(n.date)}: not recorded`)
        return tip(
          STAGES.map((s) => [s.color, s.name, `${fmtHM(n[s.key])}  ${Math.round((shares[i]?.[s.key] ?? 0) * 100)}%`]),
          fmtDay(n.date),
        )
      },
    },
    series: STAGES.map((s) => ({
      name: s.name,
      type: "bar",
      stack: "night",
      barMaxWidth: 10,
      data: shares.map((x) => (x == null ? null : +(x[s.key] * 100).toFixed(1))),
      itemStyle: { color: s.color },
    })),
  }
})

const scoreOption = computed(() => {
  const scores = nights.value.map((n) => n.score)
  const bandLine = (y: number, label: string) => ({
    yAxis: y,
    label: { formatter: label, position: "insideEndTop", color: T.faint, fontFamily: T.num, fontSize: 10 },
  })
  return {
    grid: { ...baseGrid, right: 16 },
    xAxis: xAxis.value,
    yAxis: { type: "value", min: 0, max: 100, interval: 20 },
    tooltip: {
      trigger: "axis",
      formatter: (p: { dataIndex: number }[]) => {
        const i = p[0]?.dataIndex ?? 0
        const n = nights.value[i]!
        return tip([[T.text, "Score", n.score == null ? "not recorded" : `${n.score} ${scoreBand(n.score)}`]], fmtDay(n.date))
      },
    },
    series: [
      {
        name: "Score",
        type: "line",
        data: scores,
        connectNulls: false,
        symbol: "circle",
        symbolSize: 3,
        showSymbol: nights.value.length <= 45,
        lineStyle: { color: T.text, width: 1.25 },
        itemStyle: { color: T.text },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: T.borderStrong, type: [3, 3], width: 1 },
          data: [bandLine(60, "fair"), bandLine(80, "good"), bandLine(90, "excellent")],
        },
      },
    ],
  }
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  max-width: 1180px;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--sp-3);
}
@media (max-width: 1100px) {
  .tiles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.two {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--sp-4);
}
@media (max-width: 1100px) {
  .two {
    grid-template-columns: minmax(0, 1fr);
  }
}
.key {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.sw {
  width: 10px;
  height: 10px;
  border-radius: 1px;
  display: inline-block;
}
.sw.band {
  background: rgba(212, 228, 245, 0.12);
  border: 1px solid var(--border-strong);
}
.ln {
  width: 14px;
  height: 0;
  border-top: 1.5px solid var(--text);
  display: inline-block;
}
.tablewrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-md);
}
th {
  text-align: left;
  font-weight: 500;
  font-size: var(--fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  padding: 8px var(--sp-4);
  border-bottom: 1px solid var(--border-strong);
}
td {
  padding: 7px var(--sp-4);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
tbody tr:last-child td {
  border-bottom: 0;
}
tbody tr:hover td {
  background: var(--raised);
}
.r {
  text-align: right;
}
.band-word {
  display: inline-block;
  min-width: 6.5em;
  text-align: left;
  color: var(--muted);
  font-family: var(--font-ui);
  font-size: var(--fs-sm);
  margin-left: 6px;
}
.none {
  color: var(--faint);
  font-style: italic;
}
.loading {
  padding: var(--sp-6) 0;
}
</style>
