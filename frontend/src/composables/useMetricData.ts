import { ref, watch } from "vue"
import { api } from "@/api/client"
import { useDateRangeStore } from "@/stores/dateRange"

export function useMetricData<T>(endpoint: string) {
  const store = useDateRangeStore()
  const data = ref<T | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetch() {
    loading.value = true
    error.value = null
    try {
      const res = await api.get(endpoint, {
        params: { start: store.startDate, end: store.endDate },
      })
      data.value = res.data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  watch([() => store.startDate, () => store.endDate], fetch, { immediate: true })
  return { data, loading, error, fetch }
}
