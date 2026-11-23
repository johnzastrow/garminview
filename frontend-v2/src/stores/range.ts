import { defineStore } from "pinia"
import { computed, ref } from "vue"
import dayjs from "dayjs"

export const RANGE_PRESETS = [
  { id: "30d", label: "30D", days: 30 },
  { id: "90d", label: "90D", days: 90 },
  { id: "1y", label: "1Y", days: 365 },
] as const

export type RangeId = (typeof RANGE_PRESETS)[number]["id"]

/** Shared date range for all views. The range ends today and covers `days` days inclusive. */
export const useRangeStore = defineStore("range", () => {
  const preset = ref<RangeId>("90d")
  const days = computed(() => RANGE_PRESETS.find((p) => p.id === preset.value)!.days)
  const end = computed(() => dayjs().format("YYYY-MM-DD"))
  const start = computed(() =>
    dayjs()
      .subtract(days.value - 1, "day")
      .format("YYYY-MM-DD"),
  )
  return { preset, days, start, end }
})
