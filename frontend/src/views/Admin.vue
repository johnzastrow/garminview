<template>
  <div class="admin">
    <h1>Admin</h1>
    <nav class="tabs">
      <button v-for="tab in tabs" :key="tab.id" :class="['tab-btn', { active: activeTab === tab.id }]" @click="activeTab = tab.id">{{ tab.label }}</button>
    </nav>
    <div class="tab-content">
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
      <div v-if="activeTab === 'config'">
        <h2>App Config</h2>
        <div v-if="configLoading">Loading...</div>
        <div v-for="item in config" :key="item.key" class="config-row">
          <span class="key">{{ item.key }}</span>
          <span>{{ item.value }}</span>
        </div>
      </div>
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
import { ref, onMounted } from "vue"
import { api } from "@/api/client"

const activeTab = ref("schedules")
const tabs = [{ id: "schedules", label: "Schedules" }, { id: "config", label: "Config" }, { id: "logs", label: "Sync Logs" }]

const schedules = ref<any[]>([])
const schedulesLoading = ref(false)
const config = ref<any[]>([])
const configLoading = ref(false)
const logs = ref<any[]>([])
const logsLoading = ref(false)

onMounted(async () => {
  schedulesLoading.value = true
  const s = await api.get("/admin/schedules")
  schedules.value = s.data.schedules ?? []
  schedulesLoading.value = false

  configLoading.value = true
  const c = await api.get("/admin/config")
  config.value = c.data.config ?? []
  configLoading.value = false

  logsLoading.value = true
  const l = await api.get("/admin/sync-logs")
  logs.value = l.data.logs ?? []
  logsLoading.value = false
})
</script>

<style scoped>
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab-btn { padding: 6px 16px; border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer; background: transparent; }
.tab-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
.config-row { display: flex; gap: 16px; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }
.key { font-family: monospace; font-weight: 600; min-width: 200px; }
</style>
