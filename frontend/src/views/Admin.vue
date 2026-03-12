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
      <div v-if="activeTab === 'logs'" class="sync-panel">
        <div class="sync-controls">
          <h2 style="margin: 0;">Sync Log History</h2>
          <button class="sync-btn" :disabled="logsLoading" @click="loadLogs" style="margin-left: auto;">
            {{ logsLoading ? "Loading…" : "Refresh" }}
          </button>
        </div>
        <div class="log-box" ref="historyBox">
          <div v-if="logsLoading" class="log-empty">Loading…</div>
          <template v-else-if="logFileLines.length">
            <div v-for="(line, i) in logFileLines" :key="i" :class="['log-line', lineClass(line)]">{{ line }}</div>
          </template>
          <div v-else class="log-empty">No log file found yet. Run a sync first.</div>
        </div>
      </div>

      <!-- Uploads tab -->
      <div v-if="activeTab === 'uploads'" class="uploads-panel">
        <h2>Import Data</h2>
        <p class="uploads-desc">
          Upload a MyFitnessPal export ZIP to import nutrition, measurements, and exercise logs.
          Existing rows for the uploaded date range are replaced (upsert).
        </p>

        <div class="upload-form">
          <label class="file-label">
            <span>{{ uploadFile ? uploadFile.name : "Choose .zip file…" }}</span>
            <input type="file" accept=".zip" class="file-input" @change="onFileChange" />
          </label>
          <button
            class="upload-btn"
            :disabled="!uploadFile || uploading"
            @click="submitUpload"
          >
            {{ uploading ? "Importing…" : "Import" }}
          </button>
        </div>

        <div v-if="uploading" class="upload-spinner">
          <div class="spinner"></div><span>Processing ZIP…</span>
        </div>

        <div v-if="uploadResult" class="upload-result">
          <div class="result-grid">
            <div class="result-card">
              <div class="result-num">{{ uploadResult.nutrition_days }}</div>
              <div class="result-label">Nutrition days</div>
            </div>
            <div class="result-card">
              <div class="result-num">{{ uploadResult.food_diary_rows }}</div>
              <div class="result-label">Meal diary rows</div>
            </div>
            <div class="result-card">
              <div class="result-num">{{ uploadResult.measurements }}</div>
              <div class="result-label">Measurements</div>
            </div>
            <div class="result-card">
              <div class="result-num">{{ uploadResult.exercises }}</div>
              <div class="result-label">Exercise entries</div>
            </div>
          </div>

          <div v-if="uploadResult.errors.length" class="error-summary">
            <button class="toggle-errors" @click="showErrors = !showErrors">
              {{ uploadResult.errors.length }} rows skipped
              {{ showErrors ? "▲" : "▼" }}
            </button>
            <div v-if="showErrors" class="error-list">
              <div v-for="(e, i) in uploadResult.errors" :key="i" class="error-row">
                <span class="error-loc">{{ e.file }} row {{ e.row }}</span>
                <span class="error-msg">{{ e.message }}</span>
              </div>
            </div>
          </div>
          <div v-else class="no-errors">✓ No parse errors</div>
        </div>

        <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from "vue"
import { api } from "@/api/client"

const activeTab = ref("sync")
const tabs = [
  { id: "sync", label: "Sync" },
  { id: "schedules", label: "Schedules" },
  { id: "config", label: "Config" },
  { id: "logs", label: "Sync Logs" },
  { id: "uploads", label: "Uploads" },
]

// --- Sync ---
const syncRunning = ref(false)
const logLines = ref<{ type: string; text: string }[]>([])
const logBox = ref<HTMLElement | null>(null)
let sse: EventSource | null = null

function connectSSE() {
  if (sse) { sse.close(); sse = null }
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
  sse = new EventSource(`${base}/sync/stream`)

  sse.addEventListener("log", (e) => {
    const text = (e as MessageEvent).data
    // Suppress noisy GarminDB enum warnings that are not actionable errors
    if (text.includes("UnknownEnumValue")) return
    logLines.value.push({ type: "log", text })
    scrollLog()
  })
  sse.addEventListener("done", (e) => {
    logLines.value.push({ type: "done", text: (e as MessageEvent).data })
    syncRunning.value = false
    scrollLog()
  })
  sse.addEventListener("error", (e) => {
    const msg = (e as MessageEvent).data
    if (msg) {
      logLines.value.push({ type: "error", text: msg })
      syncRunning.value = false
      scrollLog()
    }
    // Reconnect after 3s on connection drop (not on error events with data)
    if (!msg && sse?.readyState === EventSource.CLOSED) {
      setTimeout(() => connectSSE(), 3000)
    }
  })
  sse.addEventListener("status", (e) => {
    const state = (e as MessageEvent).data
    if (state === "idle") syncRunning.value = false
  })
  sse.addEventListener("ping", () => { /* keep-alive, ignore */ })
}

function scrollLog() {
  nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  })
}

async function triggerSync() {
  logLines.value = []
  syncRunning.value = true
  try {
    await api.post("/sync/trigger")
  } catch (err: any) {
    const detail = err?.response?.data?.detail ?? String(err)
    logLines.value.push({ type: "error", text: `Failed to start sync: ${detail}` })
    syncRunning.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const r = await api.get("/sync/logs", { params: { lines: 500 } })
    logFileLines.value = r.data.lines ?? []
  } finally {
    logsLoading.value = false
    nextTick(() => {
      if (historyBox.value) historyBox.value.scrollTop = historyBox.value.scrollHeight
    })
  }
}

function lineClass(line: string): string {
  if (line.includes("[error]") || line.includes("ERROR") || line.includes("✗")) return "error"
  if (line.includes("[done]") || line.includes("✓")) return "done"
  if (line.includes("WARNING") || line.includes("⚠")) return "warn"
  return ""
}

onMounted(() => {
  connectSSE()
  api.get("/admin/schedules").then((r) => { schedules.value = r.data.schedules ?? []; schedulesLoading.value = false })
  api.get("/admin/config").then((r) => { config.value = r.data.config ?? []; configLoading.value = false })
})

onUnmounted(() => sse?.close())

watch(activeTab, (tab) => { if (tab === 'logs') loadLogs() })

// --- Other tabs ---
const schedules = ref<any[]>([])
const schedulesLoading = ref(true)
const config = ref<any[]>([])
const configLoading = ref(true)

// Log history tab
const logFileLines = ref<string[]>([])
const logsLoading = ref(false)
const historyBox = ref<HTMLElement | null>(null)

// --- Uploads ---
const uploadFile = ref<File | null>(null)
const uploading = ref(false)
const uploadResult = ref<{
  nutrition_days: number
  food_diary_rows: number
  measurements: number
  exercises: number
  errors: { file: string; row: number; message: string }[]
} | null>(null)
const uploadError = ref<string | null>(null)
const showErrors = ref(false)

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  uploadFile.value = input.files?.[0] ?? null
  uploadResult.value = null
  uploadError.value = null
}

async function submitUpload() {
  if (!uploadFile.value) return
  uploading.value = true
  uploadResult.value = null
  uploadError.value = null
  showErrors.value = false
  try {
    const form = new FormData()
    form.append("file", uploadFile.value)
    const resp = await api.post("/admin/upload/mfp", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    uploadResult.value = resp.data
  } catch (e: any) {
    uploadError.value = e.response?.data?.detail ?? e.message ?? "Upload failed"
  } finally {
    uploading.value = false
  }
}
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
.log-line.done  { color: #34d399; font-weight: 600; }
.log-line.error { color: #f87171; font-weight: 600; }
.log-line.warn  { color: #fbbf24; }

table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
.config-row { display: flex; gap: 16px; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }
.key { font-family: monospace; font-weight: 600; min-width: 200px; }

/* Uploads tab */
.uploads-panel { padding: 8px 0; }
.uploads-desc { font-size: 0.82rem; color: var(--muted); margin: 0 0 20px; line-height: 1.5; }
.upload-form { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.file-label {
  display: flex; align-items: center;
  padding: 7px 14px; border: 1px solid var(--border); border-radius: 8px;
  font-size: 0.83rem; color: var(--muted); cursor: pointer;
  background: var(--bg); transition: border-color 0.12s;
}
.file-label:hover { border-color: var(--accent); }
.file-input { display: none; }
.upload-btn {
  padding: 7px 20px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; font-size: 0.85rem; font-weight: 600;
  cursor: pointer; transition: background 0.15s;
}
.upload-btn:hover:not(:disabled) { background: #2563eb; }
.upload-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.upload-spinner { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 0.85rem; }
.spinner {
  width: 16px; height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.upload-result { margin-top: 16px; }
.result-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px; }
.result-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 14px; text-align: center;
}
.result-num { font-size: 1.6rem; font-weight: 800; color: var(--text); line-height: 1; }
.result-label { font-size: 0.72rem; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.error-summary { margin-top: 8px; }
.toggle-errors {
  background: none; border: none; color: var(--accent); font-size: 0.82rem;
  cursor: pointer; padding: 0; font-weight: 600;
}
.error-list { margin-top: 8px; max-height: 200px; overflow-y: auto; font-size: 0.78rem; }
.error-row { display: flex; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--border); }
.error-loc { color: var(--muted); flex-shrink: 0; }
.error-msg { color: #DC2626; }
.no-errors { font-size: 0.82rem; color: #16A34A; font-weight: 600; }
.upload-error { margin-top: 12px; padding: 10px 14px; background: #FEF2F2; border-radius: 8px; color: #DC2626; font-size: 0.83rem; }
</style>
