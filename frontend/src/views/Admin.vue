<template>
  <div class="admin">
    <h1>Admin</h1>
    <nav class="tabs">
      <button v-for="tab in tabs" :key="tab.id" :class="['tab-btn', { active: activeTab === tab.id }]" @click="activeTab = tab.id">{{ tab.label }}</button>
    </nav>
    <div class="tab-content">

      <!-- Sync tab -->
      <div v-if="activeTab === 'sync'" class="sync-panel">
        <h2>Data Sync</h2>
        <div class="sync-controls">
          <button class="sync-btn" :class="{ running: syncRunning }" :disabled="syncRunning" @click="triggerSync">
            {{ syncRunning ? "Syncing…" : "Run Sync" }}
          </button>
          <span class="sync-status" :class="syncRunning ? 'status-running' : 'status-idle'">
            {{ syncRunning ? "Running" : "Idle" }}
          </span>
        </div>
        <div class="log-box" ref="logBox">
          <div v-for="(line, i) in logLines" :key="i" :class="['log-line', line.type]">{{ line.text }}</div>
          <div v-if="logLines.length === 0" class="log-empty">No sync output yet. Press Run Sync to start.</div>
        </div>
      </div>

      <!-- Schedules tab -->
      <div v-if="activeTab === 'schedules'">
        <h2>Sync Schedules</h2>
        <div v-if="schedulesLoading">Loading...</div>
        <table v-else>
          <thead><tr><th>Source</th><th>Cron</th><th>Enabled</th><th>Last Run</th></tr></thead>
          <tbody>
            <tr v-for="s in schedules" :key="s.id">
              <td>{{ s.source }}</td><td>{{ s.cron }}</td>
              <td>{{ s.enabled ? "Yes" : "No" }}</td><td>{{ s.last_run ?? "Never" }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Config tab -->
      <div v-if="activeTab === 'config'">
        <h2>App Config</h2>
        <div v-if="configLoading">Loading...</div>
        <div v-for="item in config" :key="item.key" class="config-row">
          <span class="key">{{ item.key }}</span>
          <span>{{ item.value }}</span>
        </div>
      </div>

      <!-- Logs tab -->
      <div v-if="activeTab === 'logs'">
        <h2>Sync Logs</h2>
        <div v-if="logsLoading">Loading...</div>
        <table v-else>
          <thead><tr><th>Source</th><th>Status</th><th>Records</th><th>Started</th></tr></thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td>{{ l.source }}</td><td>{{ l.status }}</td>
              <td>{{ l.records_upserted }}</td><td>{{ l.started_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from "vue"
import { api } from "@/api/client"

const activeTab = ref("sync")
const tabs = [
  { id: "sync", label: "Sync" },
  { id: "schedules", label: "Schedules" },
  { id: "config", label: "Config" },
  { id: "logs", label: "Sync Logs" },
]

// --- Sync ---
const syncRunning = ref(false)
const logLines = ref<{ type: string; text: string }[]>([])
const logBox = ref<HTMLElement | null>(null)
let sse: EventSource | null = null

function connectSSE() {
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
  sse = new EventSource(`${base}/sync/stream`)

  sse.addEventListener("log", (e) => {
    logLines.value.push({ type: "log", text: (e as MessageEvent).data })
    scrollLog()
  })
  sse.addEventListener("done", (e) => {
    logLines.value.push({ type: "done", text: (e as MessageEvent).data })
    syncRunning.value = false
    scrollLog()
  })
  sse.addEventListener("error", (e) => {
    logLines.value.push({ type: "error", text: (e as MessageEvent).data ?? "Connection error" })
    syncRunning.value = false
    scrollLog()
  })
  sse.addEventListener("status", () => {
    syncRunning.value = false
  })
}

function scrollLog() {
  nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  })
}

async function triggerSync() {
  logLines.value = []
  syncRunning.value = true
  await api.post("/sync/trigger")
}

onMounted(() => {
  connectSSE()

  // Other tabs data
  api.get("/admin/schedules").then((r) => { schedules.value = r.data.schedules ?? []; schedulesLoading.value = false })
  api.get("/admin/config").then((r) => { config.value = r.data.config ?? []; configLoading.value = false })
  api.get("/admin/sync-logs").then((r) => { logs.value = r.data.logs ?? []; logsLoading.value = false })
})

onUnmounted(() => sse?.close())

// --- Other tabs ---
const schedules = ref<any[]>([])
const schedulesLoading = ref(true)
const config = ref<any[]>([])
const configLoading = ref(true)
const logs = ref<any[]>([])
const logsLoading = ref(true)
</script>

<style scoped>
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab-btn { padding: 6px 16px; border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer; background: transparent; }
.tab-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }

.sync-panel { display: flex; flex-direction: column; gap: 16px; }
.sync-controls { display: flex; align-items: center; gap: 12px; }

.sync-btn {
  padding: 8px 20px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: background 0.15s;
}
.sync-btn:hover:not(:disabled) { background: #2563eb; }
.sync-btn:disabled, .sync-btn.running { background: #93c5fd; cursor: not-allowed; }

.sync-status { font-size: 0.85rem; font-weight: 600; padding: 3px 10px; border-radius: 999px; }
.status-idle { background: #f3f4f6; color: #6b7280; }
.status-running { background: #fef3c7; color: #d97706; }

.log-box {
  background: #111827;
  color: #d1fae5;
  font-family: monospace;
  font-size: 0.8rem;
  padding: 12px 16px;
  border-radius: 8px;
  height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.log-empty { color: #6b7280; font-style: italic; }
.log-line.done { color: #34d399; font-weight: 600; }
.log-line.error { color: #f87171; font-weight: 600; }

table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
.config-row { display: flex; gap: 16px; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }
.key { font-family: monospace; font-weight: 600; min-width: 200px; }
</style>
