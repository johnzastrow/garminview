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

        <h3 style="margin-top:24px;margin-bottom:12px;font-size:0.95rem;font-weight:700">Garmin Connect Credentials</h3>
        <div class="field-row">
          <label>Email</label>
          <input v-model="cfgDraft['garmin_email']" class="input-sm" type="email" placeholder="user@example.com" />
          <button class="btn-primary" @click="saveConfig('garmin_email')">Save</button>
        </div>
        <div class="field-row" style="margin-top:8px">
          <label>Password</label>
          <input v-model="cfgDraft['garmin_password']" class="input-sm" type="password" placeholder="••••••••" />
          <button class="btn-primary" @click="saveConfig('garmin_password')">Save</button>
        </div>
        <div v-if="cfgMsg" :class="['status-msg', cfgMsgOk ? 'ok' : 'err']" style="margin-top:8px">{{ cfgMsg }}</div>
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

      <!-- Actalog Integration tab -->
      <div v-if="activeTab === 'actalog'" class="actalog-panel">
        <h2>Actalog Integration</h2>
        <div v-if="actalogLoading" class="muted">Loading config…</div>
        <template v-else>
          <div class="field-row">
            <label>Base URL</label>
            <input v-model="actalogForm.url" class="input-sm" placeholder="https://al.example.com" />
          </div>
          <div class="field-row">
            <label>Email</label>
            <input v-model="actalogForm.email" class="input-sm" type="email" />
          </div>
          <div class="field-row">
            <label>Password</label>
            <input v-model="actalogForm.password" class="input-sm" :type="showPw ? 'text' : 'password'" />
            <button class="link-btn" @click="showPw = !showPw">{{ showPw ? 'Hide' : 'Show' }}</button>
          </div>
          <div class="field-row">
            <label>Weight Unit</label>
            <select v-model="actalogForm.weight_unit" class="select-sm">
              <option value="kg">kg</option>
              <option value="lbs">lbs</option>
            </select>
          </div>
          <div class="field-row">
            <label>Sync Interval (hours)</label>
            <input v-model.number="actalogForm.sync_interval_hours" class="input-sm" type="number" min="1" max="168" />
          </div>
          <div class="field-row">
            <label>Sync Enabled</label>
            <input v-model="actalogForm.sync_enabled" type="checkbox" />
          </div>
          <div class="action-row">
            <button class="btn-primary" @click="saveActalog">Save</button>
            <button class="btn-secondary" @click="testActalogConnection">Test Connection</button>
            <button class="btn-secondary" @click="syncActalog" :disabled="actalogSyncing">
              {{ actalogSyncing ? 'Syncing…' : 'Sync Now' }}
            </button>
          </div>
          <div v-if="actalogMsg" :class="['status-msg', actalogMsgOk ? 'ok' : 'err']">{{ actalogMsg }}</div>
          <div v-if="actalogConfig?.last_sync" class="muted" style="font-size:0.78rem;margin-top:4px">
            Last sync: {{ actalogConfig.last_sync?.slice(0, 19).replace('T', ' ') }}
          </div>
        </template>
      </div>

      <!-- Parser Config tab -->
      <div v-if="activeTab === 'parser'" class="parser-panel">
        <h2>Notes Parser</h2>
        <div v-if="parserLoading" class="muted">Loading config…</div>
        <template v-else>
          <div class="field-row">
            <label>Ollama URL</label>
            <input v-model="parserForm.ollama_url" class="input-sm" placeholder="http://localhost:11434" />
          </div>
          <div class="field-row">
            <label>Model</label>
            <input v-model="parserForm.model" class="input-sm" placeholder="qwen2.5:7b" />
          </div>
          <div class="field-row">
            <label>Min Note Length</label>
            <input v-model.number="parserForm.min_note_length" class="input-sm" type="number" min="1" style="min-width:80px;max-width:120px" />
            <span class="muted" style="font-size:0.78rem">chars — shorter notes are skipped</span>
          </div>
          <div class="field-row prompt-row">
            <label style="align-self:flex-start;padding-top:4px">System Prompt</label>
            <textarea v-model="parserForm.system_prompt" class="prompt-textarea" rows="14" spellcheck="false" />
          </div>
          <div class="action-row">
            <button class="btn-primary" @click="saveParserConfig">Save Config</button>
            <button class="btn-secondary" :disabled="parserRunning" @click="runParser">
              {{ parserRunning ? 'Running…' : 'Run Parser Now' }}
            </button>
            <button class="btn-danger" :disabled="parserRunning" @click="reparseAll">
              {{ parserRunning ? 'Running…' : 'Reparse All Non-Approved' }}
            </button>
          </div>
          <div v-if="parserMsg" :class="['status-msg', parserMsgOk ? 'ok' : 'err']">{{ parserMsg }}</div>

          <!-- Live status bar — always visible -->
          <div class="parser-status-bar">
            <span :class="['status-dot', parserRunning ? 'dot-running' : 'dot-idle']"></span>
            <span class="status-label">{{ parserRunning ? 'Running' : 'Idle' }}</span>
            <span v-if="parserStatusDetail" class="status-detail">{{ parserStatusDetail }}</span>
          </div>

          <!-- Timing metrics -->
          <div v-if="parserMetrics" class="metrics-panel">
            <div class="metrics-header">
              <span class="metrics-title">Parse Metrics</span>
              <span class="muted" style="font-size:0.75rem">{{ parserMetrics.total }} records total · {{ Object.entries(parserMetrics.by_status).map(([k,v]) => `${v} ${k}`).join(' · ') }}</span>
            </div>
            <table class="metrics-table" v-if="parserMetrics.by_model.length">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>N</th>
                  <th>Avg wall (s)</th>
                  <th>Avg infer (s)</th>
                  <th>Min / Max wall (s)</th>
                  <th>Avg prompt tok</th>
                  <th>Avg gen tok</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in parserMetrics.by_model" :key="m.model">
                  <td class="model-cell">{{ m.model ?? '—' }}</td>
                  <td>{{ m.n }}</td>
                  <td>{{ m.avg_wall_s ?? '—' }}</td>
                  <td>{{ m.avg_inference_s ?? '—' }}</td>
                  <td>{{ m.min_wall_s ?? '—' }} / {{ m.max_wall_s ?? '—' }}</td>
                  <td>{{ m.avg_tokens_prompt ?? '—' }}</td>
                  <td>{{ m.avg_tokens_generated ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="muted" style="font-size:0.8rem">No timing data yet — run the parser first.</div>
          </div>
        </template>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue"
import { api } from "@/api/client"
import { useActalogStore } from "@/stores/actalog"

const activeTab = ref("sync")
const tabs = [
  { id: "sync", label: "Sync" },
  { id: "schedules", label: "Schedules" },
  { id: "config", label: "Config" },
  { id: "logs", label: "Sync Logs" },
  { id: "uploads", label: "Uploads" },
  { id: "actalog", label: "Actalog" },
  { id: "parser", label: "Parser" },
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
  api.get("/admin/config").then((r) => {
    config.value = r.data.config ?? []
    config.value.forEach((row: any) => { cfgDraft.value[row.key] = row.value ?? "" })
    configLoading.value = false
  })
  _loadActalogConfig()
  _loadParserConfig()
  // Re-attach polling if a parser run was already in progress
  api.get("/admin/actalog/parser/status").then(r => {
    if (r.data.running) { parserRunning.value = true; _startPolling() }
  }).catch(() => {})
})

onUnmounted(() => {
  sse?.close()
  if (_parserPollTimer) { clearInterval(_parserPollTimer); _parserPollTimer = null }
})

watch(activeTab, (tab, prev) => {
  if (tab === 'logs') loadLogs()
  if (tab === 'parser') { _pollStatus(); _startPolling() }
  if (prev === 'parser' && !parserRunning.value) {
    clearInterval(_parserPollTimer!); _parserPollTimer = null
  }
})

// --- Other tabs ---
const schedules = ref<any[]>([])
const schedulesLoading = ref(true)
const config = ref<any[]>([])
const configLoading = ref(true)
const cfgDraft = ref<Record<string, string>>({})
const cfgMsg = ref("")
const cfgMsgOk = ref(true)

async function saveConfig(key: string) {
  cfgMsg.value = ""
  try {
    await api.put(`/admin/config/${key}`, { value: cfgDraft.value[key] ?? "" })
    cfgMsg.value = `Saved ${key}.`
    cfgMsgOk.value = true
  } catch (e: any) {
    cfgMsg.value = `Save failed: ${e.response?.data?.detail ?? e.message}`
    cfgMsgOk.value = false
  }
}

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

// --- Actalog ---
const actalogStore = useActalogStore()
const actalogLoading = ref(true)
const actalogConfig = computed(() => actalogStore.config)
const actalogForm = ref({
  url: "", email: "", password: "", weight_unit: "kg",
  sync_interval_hours: 24, sync_enabled: false,
})
const showPw = ref(false)
const actalogSyncing = ref(false)
const actalogMsg = ref("")
const actalogMsgOk = ref(true)

async function _loadActalogConfig() {
  try {
    await actalogStore.fetchConfig()
    if (actalogStore.config) {
      actalogForm.value.url = actalogStore.config.url ?? ""
      actalogForm.value.email = actalogStore.config.email ?? ""
      actalogForm.value.weight_unit = actalogStore.config.weight_unit ?? "kg"
      actalogForm.value.sync_interval_hours = actalogStore.config.sync_interval_hours ?? 24
      actalogForm.value.sync_enabled = actalogStore.config.sync_enabled
    }
  } catch {
    // backend unreachable — show form with defaults so user can still configure
  } finally {
    actalogLoading.value = false
  }
}

async function saveActalog() {
  actalogMsg.value = ""
  try {
    await actalogStore.saveConfig(actalogForm.value)
    actalogMsg.value = "Saved."
    actalogMsgOk.value = true
  } catch (e: any) {
    actalogMsg.value = `Save failed: ${e.response?.data?.detail ?? e.message}`
    actalogMsgOk.value = false
  }
}

async function testActalogConnection() {
  actalogMsg.value = ""
  try {
    await api.post("/admin/actalog/test-connection", null, {
      params: {
        url: actalogForm.value.url,
        email: actalogForm.value.email,
        password: actalogForm.value.password,
      },
    })
    actalogMsg.value = "Connection successful."
    actalogMsgOk.value = true
  } catch (e: any) {
    actalogMsg.value = `Connection failed: ${e.response?.data?.detail ?? e.message}`
    actalogMsgOk.value = false
  }
}

async function syncActalog() {
  actalogSyncing.value = true
  actalogMsg.value = ""
  try {
    const counts = await actalogStore.triggerSync()
    actalogMsg.value = `Sync complete: ${counts.workouts} workouts, ${counts.prs} PRs.`
    actalogMsgOk.value = true
    await actalogStore.fetchConfig()
  } catch (e: any) {
    actalogMsg.value = `Sync failed: ${e.response?.data?.detail ?? e.message}`
    actalogMsgOk.value = false
  } finally {
    actalogSyncing.value = false
  }
}

// --- Parser ---
const parserLoading = ref(true)
const parserForm = ref({ ollama_url: "", model: "", min_note_length: 20, system_prompt: "" })
const parserRunning = ref(false)
const parserStagedCount = ref<number | null>(null)
const parserStatusDetail = ref<string | null>(null)
const parserMsg = ref("")
const parserMsgOk = ref(true)
const parserMetrics = ref<any | null>(null)
let _parserPollTimer: ReturnType<typeof setInterval> | null = null

async function _pollStatus() {
  try {
    const r = await api.get("/admin/actalog/parser/status")
    const { running, total_staged } = r.data
    parserStagedCount.value = total_staged
    parserStatusDetail.value = `${total_staged} records staged`
    if (running && !parserRunning.value) {
      parserRunning.value = true
    }
    if (!running && parserRunning.value) {
      parserRunning.value = false
      parserMsg.value = "Run complete."
      parserMsgOk.value = true
      clearInterval(_parserPollTimer!)
      _parserPollTimer = null
      await _loadParserMetrics()
    }
  } catch { /* ignore */ }
}

function _startPolling() {
  if (_parserPollTimer) return
  _parserPollTimer = setInterval(_pollStatus, 4000)
}

async function _loadParserConfig() {
  try {
    const [cfgR, statsR] = await Promise.all([
      api.get("/admin/actalog/parser/config"),
      api.get("/admin/actalog/parser/stats"),
      _pollStatus(),
    ])
    const c = cfgR.data
    parserForm.value.ollama_url = c.ollama_url ?? ""
    parserForm.value.model = c.model ?? ""
    parserForm.value.min_note_length = c.min_note_length ?? 20
    parserForm.value.system_prompt = c.system_prompt ?? ""
    parserMetrics.value = statsR.data
  } catch {
    // backend unreachable — form stays at defaults
  } finally {
    parserLoading.value = false
  }
}

async function _loadParserMetrics() {
  try {
    const r = await api.get("/admin/actalog/parser/stats")
    parserMetrics.value = r.data
  } catch { /* ignore */ }
}

async function saveParserConfig() {
  parserMsg.value = ""
  try {
    await api.post("/admin/actalog/parser/config", parserForm.value)
    parserMsg.value = "Config saved."
    parserMsgOk.value = true
  } catch (e: any) {
    parserMsg.value = `Save failed: ${e.response?.data?.detail ?? e.message}`
    parserMsgOk.value = false
  }
}

async function reparseAll() {
  if (!confirm("Delete all non-approved parse records and reparse everything? Approved notes are not affected.")) return
  parserMsg.value = ""
  try {
    await api.post("/admin/actalog/parser/reparse-all")
    parserRunning.value = true
    _startPolling()
  } catch (e: any) {
    parserMsg.value = `Reparse failed: ${e.response?.data?.detail ?? e.message}`
    parserMsgOk.value = false
  }
}

async function runParser() {
  parserMsg.value = ""
  try {
    await api.post("/admin/actalog/parser/run")
    parserRunning.value = true
    _startPolling()
  } catch (e: any) {
    parserMsg.value = `Parser run failed: ${e.response?.data?.detail ?? e.message}`
    parserMsgOk.value = false
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

/* Actalog tab */
.actalog-panel { padding: 8px 0; display: flex; flex-direction: column; gap: 10px; }
.field-row { display: flex; align-items: center; gap: 12px; }
.field-row label { min-width: 160px; font-size: 0.85rem; font-weight: 600; color: var(--text); }
.input-sm { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.85rem; background: var(--bg); color: var(--text); min-width: 260px; font-family: inherit; }
.input-sm:focus { outline: none; border-color: var(--accent); }
.select-sm { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.85rem; background: var(--bg); color: var(--text); font-family: inherit; }
.link-btn { background: none; border: none; color: var(--accent); font-size: 0.8rem; cursor: pointer; padding: 0 4px; font-family: inherit; }
.link-btn:hover { text-decoration: underline; }
.action-row { display: flex; gap: 10px; margin-top: 6px; }
.btn-primary { padding: 7px 20px; background: var(--accent); color: #fff; border: none; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: background 0.15s; font-family: inherit; }
.btn-primary:hover { opacity: 0.9; }
.btn-secondary { padding: 7px 16px; background: transparent; color: var(--text); border: 1px solid var(--border); border-radius: 6px; font-size: 0.85rem; cursor: pointer; transition: border-color 0.15s; font-family: inherit; }
.btn-secondary:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.status-msg { margin-top: 6px; font-size: 0.83rem; padding: 6px 10px; border-radius: 6px; }
.status-msg.ok { background: #F0FDF4; color: #16A34A; }
.status-msg.err { background: #FEF2F2; color: #DC2626; }
.muted { color: var(--muted); }

/* Parser tab */
.parser-panel { padding: 8px 0; display: flex; flex-direction: column; gap: 10px; }
.prompt-row { align-items: flex-start; }
.prompt-textarea {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.8rem;
  font-family: monospace;
  background: var(--bg);
  color: var(--text);
  resize: vertical;
  min-height: 200px;
  line-height: 1.5;
}
.prompt-textarea:focus { outline: none; border-color: var(--accent); }
.parser-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.stat-chip {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  background: #F0FDF4;
  color: #16A34A;
}
.stat-chip.pending { background: #FEF9C3; color: #854D0E; }
.stat-chip.skipped { background: #F3F4F6; color: #6B7280; }
.stat-chip.error   { background: #FEF2F2; color: #DC2626; }
.btn-danger { padding: 7px 16px; background: #DC2626; color: #fff; border: none; border-radius: 6px; font-size: 0.85rem; cursor: pointer; font-family: inherit; }
.btn-danger:hover:not(:disabled) { background: #b91c1c; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.parser-status-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: 6px;
  background: var(--bg); border: 1px solid var(--border);
  font-size: 0.82rem;
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.dot-idle { background: #6b7280; }
.dot-running { background: #f59e0b; animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.status-label { font-weight: 600; color: var(--text); }
.status-detail { color: var(--muted); }
.metrics-panel { margin-top: 16px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.metrics-header { display: flex; align-items: baseline; gap: 12px; padding: 8px 14px; background: var(--bg); border-bottom: 1px solid var(--border); }
.metrics-title { font-size: 0.85rem; font-weight: 700; color: var(--text); }
.metrics-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.metrics-table th { padding: 6px 12px; text-align: right; font-weight: 600; color: var(--muted); background: var(--bg); border-bottom: 1px solid var(--border); white-space: nowrap; }
.metrics-table th:first-child { text-align: left; }
.metrics-table td { padding: 7px 12px; text-align: right; border-bottom: 1px solid var(--border); }
.metrics-table td:first-child { text-align: left; }
.metrics-table tr:last-child td { border-bottom: none; }
.model-cell { font-family: monospace; font-size: 0.78rem; color: var(--text); }
</style>
