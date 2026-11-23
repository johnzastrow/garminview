import { ref, watch, type Ref } from "vue"
import { api } from "@/api/client"
import { useRangeStore } from "@/stores/range"

/**
 * Fetches `endpoint` for the shared date range and refetches when the range changes.
 * Errors are reduced to a short, user-facing message; details go to the console.
 */
export function useRangeData<T>(endpoint: string): {
  data: Ref<T | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  reload: () => Promise<void>
} {
  const range = useRangeStore()
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref<string | null>(null)
  let seq = 0

  async function reload() {
    const mine = ++seq
    loading.value = true
    error.value = null
    try {
      const res = await api.get<T>(endpoint, { params: { start: range.start, end: range.end } })
      if (mine === seq) data.value = res.data // ignore responses from superseded requests
    } catch (e) {
      if (mine !== seq) return
      console.error(`GET ${endpoint} failed`, e)
      error.value = "Could not load data from the server. Check that the backend is running, then reload."
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  watch(() => [range.start, range.end], reload, { immediate: true })
  return { data, loading, error, reload }
}
