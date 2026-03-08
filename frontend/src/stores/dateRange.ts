import { defineStore } from "pinia"
import { ref } from "vue"
import dayjs from "dayjs"

export const useDateRangeStore = defineStore("dateRange", () => {
  const endDate = ref(dayjs().format("YYYY-MM-DD"))
  const startDate = ref(dayjs().subtract(90, "day").format("YYYY-MM-DD"))
  const preset = ref<"7d" | "30d" | "90d" | "1y" | "custom">("90d")

  function setPreset(p: typeof preset.value) {
    preset.value = p
    endDate.value = dayjs().format("YYYY-MM-DD")
    const days: Record<string, number> = { "7d": 7, "30d": 30, "90d": 90, "1y": 365 }
    if (p !== "custom") startDate.value = dayjs().subtract(days[p], "day").format("YYYY-MM-DD")
  }

  return { startDate, endDate, preset, setPreset }
})
