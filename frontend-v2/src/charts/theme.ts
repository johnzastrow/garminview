import { use, registerTheme } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { BarChart, LineChart } from "echarts/charts"
import {
  GridComponent,
  TooltipComponent,
  MarkAreaComponent,
  MarkLineComponent,
  DataZoomInsideComponent,
} from "echarts/components"

// Canvas cannot read CSS variables, so the chart theme copies the token values.
// Keep in sync with src/styles/tokens.css.
export const T = {
  canvas: "#11151a",
  panel: "#181d23",
  raised: "#1f252c",
  border: "#2a323b",
  borderStrong: "#3b4652",
  text: "#e6eaef",
  muted: "#9aa6b2",
  faint: "#66717d",
  accent: "#d4e4f5",
  sleep: "#8e90ec",
  deep: "#6366d9",
  light: "#a9abf2",
  rem: "#c77ddb",
  awake: "#66717d",
  num: '"JetBrains Mono", ui-monospace, Menlo, monospace',
  ui: '"Archivo", "Helvetica Neue", Arial, sans-serif',
}

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent, DataZoomInsideComponent])

const axis = {
  axisLine: { lineStyle: { color: T.borderStrong } },
  axisTick: { show: false },
  axisLabel: { color: T.muted, fontFamily: T.num, fontSize: 10.5 },
  splitLine: { lineStyle: { color: T.border, width: 1 } },
}

registerTheme("instrument", {
  backgroundColor: "transparent",
  textStyle: { fontFamily: T.ui, color: T.muted },
  animation: false, // no animated entrances (decision 2026-11-23)
  categoryAxis: { ...axis, splitLine: { show: false } },
  valueAxis: { ...axis, axisLine: { show: false } },
  timeAxis: { ...axis, splitLine: { show: false } },
  tooltip: {
    backgroundColor: T.raised,
    borderColor: T.borderStrong,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: { color: T.text, fontFamily: T.num, fontSize: 12 },
    extraCssText: "border-radius:3px;box-shadow:none;",
  },
})

/** Escape text before it goes into an ECharts HTML tooltip (tooltips are rendered as HTML). */
export function esc(s: string | number): string {
  return String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}
