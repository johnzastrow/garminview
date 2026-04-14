<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue"
import { api } from "@/api/client"
import { marked } from "marked"

// ── Types ───────────────────────────────────────────────────────────
interface QueueItem {
  id: number
  workout_id: number | null
  workout_name: string | null
  workout_date: string | null
  content_class: string | null
  parse_status: string | null
  parsed_at: string | null
  reviewed_at: string | null
  error_message: string | null
  llm_model: string | null
  raw_notes: string | null
  formatted_markdown: string | null
  parsed_json: string | null
  parse_duration_s: number | null
  llm_tokens_prompt: number | null
  llm_tokens_generated: number | null
  llm_inference_s: number | null
  performance_notes: string | null
}

interface ParsedWod {
  name: string
  alt_name?: string | null
  regime?: string | null
  score_type?: string | null
}

// ── State ───────────────────────────────────────────────────────────
const items = ref<QueueItem[]>([])
const loading = ref(false)
const statusFilter = ref<"pending" | "approved" | "rejected" | "sent" | "skipped" | "dismissed" | "all">("pending")
const contentClassFilter = ref("")
const searchQuery = ref("")
const sortOrder = ref<"desc" | "asc">("desc")
const selectedItem = ref<QueueItem | null>(null)
const editMode = ref(false)
const editedMarkdown = ref("")
const pendingCount = ref(0)
const reparsingSkipped = ref(false)

let searchDebounce: ReturnType<typeof setTimeout> | null = null

// ── Fetching ────────────────────────────────────────────────────────
async function fetchQueue() {
  loading.value = true
  try {
    const params: Record<string, string> = { order: sortOrder.value }
    if (statusFilter.value !== "all") params.status = statusFilter.value
    if (contentClassFilter.value) params.content_class = contentClassFilter.value
    if (searchQuery.value.trim()) params.q = searchQuery.value.trim()
    const { data } = await api.get("/admin/actalog/parser/queue", { params })
    items.value = data.items ?? data
    // Update pending count
    fetchPendingCount()
  } catch (e: any) {
    console.error("Failed to load queue:", e)
  } finally {
    loading.value = false
  }
}

async function fetchPendingCount() {
  try {
    const { data } = await api.get("/admin/actalog/parser/status")
    pendingCount.value = data.total_staged ?? 0
  } catch { /* ignore */ }
}

// ── Selection ───────────────────────────────────────────────────────
function selectItem(item: QueueItem) {
  selectedItem.value = item
  editedMarkdown.value = item.formatted_markdown ?? ""
  editMode.value = false
}

// ── Actions ─────────────────────────────────────────────────────────
async function approve() {
  if (!selectedItem.value) return
  try {
    await api.post(`/admin/actalog/parser/approve/${selectedItem.value.id}`, {
      formatted_markdown: editedMarkdown.value || null,
      performance_notes: parsedData.value?.performance_notes ?? null,
    })
    const currentId = selectedItem.value.id
    await fetchQueue()
    nextPending(currentId)
  } catch (e: any) {
    alert(`Approve failed: ${e.response?.data?.detail ?? e.message}`)
  }
}

async function reject() {
  if (!selectedItem.value) return
  try {
    await api.post(`/admin/actalog/parser/reject/${selectedItem.value.id}`)
    const currentId = selectedItem.value.id
    await fetchQueue()
    nextPending(currentId)
  } catch (e: any) {
    alert(`Reject failed: ${e.response?.data?.detail ?? e.message}`)
  }
}

async function reparse() {
  if (!selectedItem.value?.workout_id) return
  if (!confirm("Re-queue this workout for parsing?")) return
  try {
    await api.post(`/admin/actalog/parser/reparse/${selectedItem.value.workout_id}`)
    await fetchQueue()
    selectedItem.value = null
  } catch (e: any) {
    alert(`Reparse failed: ${e.response?.data?.detail ?? e.message}`)
  }
}

async function push() {
  if (!selectedItem.value) return
  try {
    await api.post(`/admin/actalog/parser/push/${selectedItem.value.id}`)
    await fetchQueue()
  } catch (e: any) {
    alert(`Push failed: ${e.response?.data?.detail ?? e.message}`)
  }
}

async function dismiss() {
  if (!selectedItem.value) return
  try {
    await api.post(`/admin/actalog/parser/dismiss/${selectedItem.value.id}`)
    const currentId = selectedItem.value.id
    await fetchQueue()
    nextPending(currentId)
  } catch (e: any) {
    alert(`Dismiss failed: ${e.response?.data?.detail ?? e.message}`)
  }
}

async function reparseAllSkipped() {
  if (!confirm("Reparse all skipped workouts through the LLM? This may take several minutes.")) return
  reparsingSkipped.value = true
  try {
    await api.post("/admin/actalog/parser/reparse-skipped")
    // Poll until done
    const poll = setInterval(async () => {
      const { data } = await api.get("/admin/actalog/parser/status")
      if (!data.running) {
        clearInterval(poll)
        reparsingSkipped.value = false
        await fetchQueue()
      }
    }, 3000)
  } catch (e: any) {
    reparsingSkipped.value = false
    alert(`Reparse failed: ${e.response?.data?.detail ?? e.message}`)
  }
}

function saveEdits() {
  // Local save only — the approve call sends editedMarkdown
  editMode.value = false
}

function nextPending(afterId: number) {
  const idx = items.value.findIndex(i => i.id === afterId)
  const remaining = items.value.filter((i, j) => j > idx && i.parse_status === "pending")
  if (remaining.length > 0) {
    selectItem(remaining[0])
  } else {
    // Wrap around to first pending
    const first = items.value.find(i => i.parse_status === "pending")
    if (first) selectItem(first)
    else selectedItem.value = null
  }
}

// ── Computed ─────────────────────────────────────────────────────────
const renderedMarkdown = computed((): string => {
  const src = editedMarkdown.value.trim()
  if (!src) return '<p class="empty-md">No markdown content.</p>'
  return marked.parse(src) as string
})

const parsedData = computed(() => {
  if (!selectedItem.value?.parsed_json) return null
  try {
    return JSON.parse(selectedItem.value.parsed_json)
  } catch {
    return null
  }
})

// ── Keyboard shortcuts ──────────────────────────────────────────────
function onKeydown(e: KeyboardEvent) {
  // Skip if in a textarea or input
  const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
  if (tag === "textarea" || tag === "input" || tag === "select") return
  if (!selectedItem.value) return

  switch (e.key) {
    case "a":
      e.preventDefault()
      approve()
      break
    case "r":
      e.preventDefault()
      reject()
      break
    case "n":
      e.preventDefault()
      nextPending(selectedItem.value.id)
      break
    case "e":
      e.preventDefault()
      editMode.value = !editMode.value
      break
    case "d":
      e.preventDefault()
      dismiss()
      break
  }
}

// ── Watchers ────────────────────────────────────────────────────────
watch([statusFilter, contentClassFilter, sortOrder], () => fetchQueue())

watch(searchQuery, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(fetchQueue, 350)
})

// ── Lifecycle ───────────────────────────────────────────────────────
onMounted(() => {
  fetchQueue()
  document.addEventListener("keydown", onKeydown)
})

onUnmounted(() => {
  document.removeEventListener("keydown", onKeydown)
  if (searchDebounce) clearTimeout(searchDebounce)
})
</script>

<template>
  <div class="review-queue">
    <!-- Filter bar -->
    <div class="filter-bar">
      <select v-model="statusFilter" class="filter-select">
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="rejected">Rejected</option>
        <option value="sent">Sent</option>
        <option value="skipped">Skipped</option>
        <option value="dismissed">Dismissed</option>
        <option value="all">All</option>
      </select>

      <select v-model="contentClassFilter" class="filter-select">
        <option value="">All Classes</option>
        <option value="WORKOUT">WORKOUT</option>
        <option value="MIXED">MIXED</option>
        <option value="PERFORMANCE_ONLY">PERFORMANCE_ONLY</option>
        <option value="SKIP">SKIP</option>
      </select>

      <input
        v-model="searchQuery"
        type="text"
        class="filter-search"
        placeholder="Search by name or keyword..."
      />

      <button class="sort-btn" @click="sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'">
        {{ sortOrder === 'desc' ? '\u2193 Newest' : '\u2191 Oldest' }}
      </button>

      <span v-if="pendingCount > 0" class="pending-badge">{{ pendingCount }} pending</span>

      <button
        class="btn-secondary reparse-skipped-btn"
        :disabled="reparsingSkipped"
        @click="reparseAllSkipped"
      >
        {{ reparsingSkipped ? 'Reparsing...' : 'Reparse All Skipped' }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="muted">Loading...</div>

    <!-- List -->
    <table v-if="!loading && items.length" class="review-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Workout Name</th>
          <th>Content Class</th>
          <th>Status</th>
          <th>Model</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in items"
          :key="item.id"
          :class="['review-row', { selected: selectedItem?.id === item.id }]"
          @click="selectItem(item)"
        >
          <td>{{ item.workout_date?.slice(0, 10) ?? '--' }}</td>
          <td>{{ item.workout_name ?? '--' }}</td>
          <td>
            <span :class="['badge', `badge-class-${(item.content_class ?? '').toLowerCase()}`]">
              {{ item.content_class ?? '--' }}
            </span>
          </td>
          <td>
            <span :class="['badge', `badge-status-${(item.parse_status ?? '').toLowerCase()}`]">
              {{ item.parse_status ?? '--' }}
            </span>
          </td>
          <td class="muted-text">{{ item.llm_model ?? '--' }}</td>
        </tr>
      </tbody>
    </table>

    <!-- Empty state -->
    <div v-if="!loading && items.length === 0" class="empty">
      No {{ statusFilter === 'pending' ? 'pending reviews' : 'items' }} found
    </div>

    <!-- Detail panel -->
    <div v-if="selectedItem" class="detail-panel">
      <div class="detail-header">
        <strong>{{ selectedItem.workout_name ?? 'Workout' }}</strong>
        <span class="muted-text" style="margin-left: 8px">{{ selectedItem.workout_date?.slice(0, 10) }}</span>
        <span :class="['badge', `badge-status-${(selectedItem.parse_status ?? '').toLowerCase()}`]" style="margin-left: 10px">
          {{ selectedItem.parse_status ?? '--' }}
        </span>
        <button class="close-btn" @click="selectedItem = null">&#x2715;</button>
      </div>

      <div class="detail-split">
        <!-- Left: raw notes -->
        <div class="raw-notes">
          <h4>Original Notes</h4>
          <pre>{{ selectedItem.raw_notes ?? '(no notes)' }}</pre>
        </div>

        <!-- Right: edit/preview -->
        <div class="parsed-output">
          <div class="toggle-bar">
            <button class="toggle-btn" @click="editMode = !editMode">
              {{ editMode ? 'Preview' : 'Edit' }}
            </button>
          </div>
          <textarea
            v-if="editMode"
            v-model="editedMarkdown"
            class="md-editor"
          />
          <div v-else class="md-preview" v-html="renderedMarkdown" />
        </div>
      </div>

      <!-- Structured data preview -->
      <div v-if="parsedData?.wods?.length" class="wod-preview">
        <h4>Extracted WODs</h4>
        <div v-for="(wod, i) in (parsedData.wods as ParsedWod[])" :key="i" class="wod-chip">
          <span class="wod-name">{{ wod.name }}</span>
          <span v-if="wod.regime" :class="['badge', 'badge-regime']">{{ wod.regime }}</span>
          <span v-if="wod.score_type" class="muted-text">{{ wod.score_type }}</span>
        </div>
      </div>

      <!-- Sent notice -->
      <div v-if="selectedItem.parse_status === 'sent'" class="sent-notice">
        <strong>&#x2714; Sent to Actalog</strong>
        <span v-if="parsedData?._sent_at"> on {{ new Date(parsedData._sent_at).toLocaleString() }}</span>
        <p>The version on Actalog may include your edits that aren't reflected in the preview above.</p>
      </div>

      <!-- Error notice for failed push -->
      <div v-if="selectedItem.parse_status === 'approved' && selectedItem.error_message" class="error-notice">
        <strong>&#x26a0; Push failed:</strong> {{ selectedItem.error_message }}
      </div>

      <!-- Actions -->
      <div class="actions">
        <button v-if="selectedItem.parse_status === 'pending'" class="btn-success" @click="approve">Approve (a)</button>
        <button v-if="selectedItem.parse_status === 'pending'" class="btn-danger" @click="reject">Reject (r)</button>
        <button v-if="!['approved','sent','dismissed'].includes(selectedItem.parse_status ?? '')" class="btn-secondary" @click="reparse">Reparse</button>
        <button
          v-if="selectedItem.parse_status === 'approved'"
          class="btn-primary"
          @click="push"
        >
          Push to Actalog
        </button>
        <button
          v-if="selectedItem.parse_status !== 'sent' && selectedItem.parse_status !== 'dismissed'"
          class="btn-muted"
          @click="dismiss"
        >
          Dismiss (d)
        </button>
        <button v-if="selectedItem.parse_status === 'pending'" class="btn-secondary" @click="saveEdits" :disabled="!editMode">Save Edits</button>
      </div>

      <!-- Keyboard shortcuts hint -->
      <div v-if="selectedItem.parse_status === 'pending'" class="shortcuts">a=approve r=reject d=dismiss n=next e=edit</div>
    </div>
  </div>
</template>

<style scoped>
.review-queue { padding: 0; }

/* Filter bar */
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filter-select {
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 0.83rem;
  color: var(--text);
  background: var(--surface);
}
.filter-search {
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 0.83rem;
  color: var(--text);
  background: var(--surface);
  min-width: 200px;
  flex: 1;
  max-width: 300px;
}
.filter-search::placeholder { color: var(--muted); }
.sort-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 0.83rem;
}
.sort-btn:hover { border-color: var(--accent); }
.pending-badge {
  padding: 3px 10px;
  border-radius: 99px;
  background: #fef9c3;
  color: #854d0e;
  font-size: 0.78rem;
  font-weight: 600;
}

/* Table */
.review-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.83rem;
}
.review-table th {
  text-align: left;
  padding: 6px 10px;
  color: var(--muted);
  font-weight: 600;
  font-size: 0.75rem;
  border-bottom: 1px solid var(--border);
}
.review-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.review-row { cursor: pointer; }
.review-row:hover { background: var(--bg); }
.review-row.selected { background: var(--accent-light); }

/* Badges */
.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-status-pending   { background: #fef3c3; color: #f59e0b; }
.badge-status-approved  { background: #dcfce7; color: #22c55e; }
.badge-status-rejected  { background: #fee2e2; color: #ef4444; }
.badge-status-sent      { background: #dbeafe; color: #3b82f6; }
.badge-status-skipped   { background: #f3f4f6; color: #6b7280; }
.badge-status-dismissed { background: #e5e7eb; color: #9ca3af; }
.btn-muted { background: #e5e7eb; color: #6b7280; border: 1px solid #d1d5db; }
.badge-class-workout         { background: #dbeafe; color: #3b82f6; }
.badge-class-mixed           { background: #f3e8ff; color: #a855f7; }
.badge-class-performance_only { background: #ffedd5; color: #f97316; }
.badge-class-skip            { background: #f3f4f6; color: #9ca3af; }
.badge-regime { background: var(--accent-light); color: var(--accent); }

/* Detail panel */
.detail-panel {
  margin-top: 20px;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  background: var(--surface);
}
.detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
  font-size: 1rem;
}
.close-btn {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--muted);
  font-size: 1rem;
}

.detail-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}

/* Raw notes */
.raw-notes h4 {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 6px;
}
.raw-notes pre {
  font-family: monospace;
  font-size: 0.78rem;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f5f5f5;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  max-height: 400px;
  overflow-y: auto;
  color: var(--text);
}

/* Parsed output */
.parsed-output { display: flex; flex-direction: column; gap: 6px; }
.toggle-bar { display: flex; gap: 8px; }
.toggle-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 0.82rem;
}
.toggle-btn:hover { border-color: var(--accent); }

.md-editor {
  width: 100%;
  min-height: 300px;
  font-family: monospace;
  font-size: 0.82rem;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  resize: vertical;
  line-height: 1.5;
}

.md-preview {
  font-size: 0.83rem;
  line-height: 1.65;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  max-height: 400px;
  overflow-y: auto;
  color: var(--text);
}
.md-preview :deep(h1) { font-size: 1.1rem; font-weight: 700; margin: 0 0 6px; }
.md-preview :deep(h2) { font-size: 0.97rem; font-weight: 700; margin: 10px 0 4px; }
.md-preview :deep(h3) { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--accent); margin: 10px 0 4px; }
.md-preview :deep(p)  { margin: 4px 0; }
.md-preview :deep(ul) { padding-left: 18px; margin: 4px 0; }
.md-preview :deep(li) { margin: 2px 0; }
.empty-md { color: var(--muted); font-style: italic; }

/* WOD preview */
.wod-preview {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.wod-preview h4 {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 8px;
}
.wod-chip {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px 10px;
  margin: 0 6px 6px 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.82rem;
}
.wod-name { font-weight: 600; color: var(--text); }

/* Actions */
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.btn-success {
  padding: 7px 18px;
  background: #22c55e;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}
.btn-success:hover { background: #16a34a; }
.btn-danger {
  padding: 7px 18px;
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}
.btn-primary {
  padding: 7px 18px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}
.btn-secondary {
  padding: 7px 18px;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
}
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

/* Shortcuts hint */
.shortcuts {
  margin-top: 8px;
  font-size: 0.72rem;
  color: var(--muted);
  font-family: monospace;
}

/* Utility */
.muted { color: var(--muted); font-size: 0.85rem; padding: 24px 0; }
.muted-text { color: var(--muted); font-size: 0.83rem; }
.empty { color: var(--muted); font-size: 0.85rem; padding: 24px 0; text-align: center; }
/* Sent/error notices */
.sent-notice {
  background: #dbeafe;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  padding: 10px 14px;
  margin: 10px 0;
  color: #1e40af;
  font-size: 0.85rem;
}
.sent-notice p { margin: 4px 0 0; opacity: 0.8; }
.error-notice {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  padding: 10px 14px;
  margin: 10px 0;
  color: #991b1b;
  font-size: 0.85rem;
}
</style>
