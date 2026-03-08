import { defineStore } from "pinia"
import { ref } from "vue"

export const useSyncStore = defineStore("sync", () => {
  const status = ref<"idle" | "running" | "error">("idle")
  const lastSync = ref<string | null>(null)
  const progress = ref("")

  function connectSSE() {
    const es = new EventSource("/sync/stream")
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      status.value = data.status
      progress.value = data.message ?? ""
    }
  }

  return { status, lastSync, progress, connectSSE }
})
