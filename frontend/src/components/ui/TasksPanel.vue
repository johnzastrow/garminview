<!-- frontend/src/components/ui/TasksPanel.vue -->
<template>
  <div v-if="items.length" class="tasks-panel">
    <h2 class="tasks-title">System Activity</h2>
    <div class="tasks-list">
      <component
        :is="item.link ? 'router-link' : 'div'"
        v-for="item in items"
        :key="item.item_type + (item.action_key ?? item.timestamp ?? '')"
        :to="item.link ?? undefined"
        :class="['task-row', item.item_type === 'action' ? 'task-action' : 'task-sync']"
      >
        <span :class="['dot', dotClass(item)]" />
        <div class="task-body">
          <span class="task-title">{{ item.title }}</span>
          <span v-if="item.detail" class="task-detail">{{ item.detail }}</span>
        </div>
        <div v-if="item.item_type === 'sync'" class="task-meta">
          <span v-if="item.timestamp" class="task-time">{{ relativeTime(item.timestamp) }}</span>
          <span v-if="item.duration_s != null" class="task-dur">{{ formatDuration(item.duration_s) }}</span>
          <span v-if="item.records_upserted" class="task-records">{{ item.records_upserted.toLocaleString() }} records</span>
        </div>
      </component>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { api } from '@/api/client'

interface TaskItem {
  item_type: 'sync' | 'action'
  action_key: string | null
  title: string
  detail: string | null
  link: string | null
  count: number | null
  timestamp: string | null
  duration_s: number | null
  records_upserted: number | null
  status: string | null
}

const items = ref<TaskItem[]>([])

onMounted(async () => {
  try {
    const res = await api.get('/admin/tasks', { params: { limit: 10 } })
    items.value = res.data
  } catch {
    // Panel is supplementary — don't surface fetch errors to the user
  }
})

function dotClass(item: TaskItem): string {
  if (item.item_type === 'action') return 'dot-action'
  return `dot-${item.status ?? 'unknown'}`
}

function relativeTime(ts: string): string {
  const d = dayjs(ts)
  const diffH = dayjs().diff(d, 'hour')
  if (diffH < 1) return `${dayjs().diff(d, 'minute')}m ago`
  if (diffH < 24) return `${diffH}h ago`
  const diffD = dayjs().diff(d, 'day')
  if (diffD < 7) return `${diffD}d ago`
  return d.format('MMM D')
}

function formatDuration(s: number): string {
  if (s < 60) return `${Math.round(s)}s`
  return `${Math.round(s / 60)}m`
}
</script>

<style scoped>
.tasks-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
}

.tasks-title {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted);
  margin: 0 0 8px;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 0.82rem;
  text-decoration: none;
  color: inherit;
}

.task-action {
  border-left: 3px solid #D97706;
  background: #FFFBEB;
  cursor: pointer;
}

.task-action:hover { background: #FEF3C7; }

.task-sync { border-left: 3px solid transparent; }

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-success { background: #16A34A; }
.dot-error   { background: #DC2626; }
.dot-running { background: #D97706; }
.dot-unknown { background: #9A9690; }
.dot-action  { background: #D97706; }

.task-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.task-title { font-weight: 600; color: var(--text); }
.task-detail { font-size: 0.75rem; color: var(--muted); }

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--muted);
}
</style>
