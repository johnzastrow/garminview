<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Assessments & Goals</h1>
        <p class="page-sub">AI-generated health insights and sync history</p>
      </div>
    </header>

    <div class="range-row">
      <span class="range-label">Showing</span>
      <DateRangePicker />
    </div>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading assessments…</span></div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else>
      <!-- Assessments -->
      <section>
        <h2 class="section-title">Health Assessments</h2>
        <p class="section-desc">AI-generated health insights computed by the analysis engine after each sync. Assessments are categorized by domain (sleep, cardiovascular, training, body composition) and severity. Review flagged items to guide training adjustments.</p>
        <div v-if="assessments.length === 0" class="empty-card">
          <p>No assessments found. Run a sync to generate AI health insights.</p>
        </div>
        <div v-else class="assessment-grid">
          <div v-for="a in assessments" :key="a.id" class="assessment-card" :class="a.severity">
            <div class="card-top">
              <span class="badge" :class="a.severity">{{ a.severity }}</span>
              <span class="category">{{ fmt(a.category) }}</span>
              <span class="period">{{ a.period_type }} · {{ a.period_start }}</span>
            </div>
            <p class="summary">{{ a.summary_text }}</p>
          </div>
        </div>
      </section>

      <!-- Sync History -->
      <section>
        <h2 class="section-title">Recent Syncs</h2>
        <p class="section-desc">History of data sync operations. Each sync downloads new activity files, parses FIT data, and updates all derived metrics. Sync duration and row counts help diagnose ingestion issues.</p>
        <div v-if="syncsLoading" class="loading-inline">Loading…</div>
        <div v-else-if="syncs.length === 0" class="empty-card"><p>No sync history yet.</p></div>
        <div v-else class="sync-list">
          <div v-for="s in syncs" :key="s.id" class="sync-row">
            <span class="sync-status-dot" :class="s.status"></span>
            <div class="sync-info">
              <span class="sync-source">{{ s.source ?? 'Full sync' }}</span>
              <span class="sync-time">{{ fmtDate(s.started_at) }}</span>
            </div>
            <span class="sync-badge" :class="s.status">{{ s.status }}</span>
            <span v-if="s.rows_upserted != null" class="sync-rows">{{ s.rows_upserted.toLocaleString() }} rows</span>
            <span v-if="s.duration_s != null" class="sync-dur">{{ s.duration_s }}s</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import { useMetricData } from "@/composables/useMetricData"
import { api } from "@/api/client"

interface Assessment { id: number; period_type: string; period_start: string; category: string; severity: string; summary_text: string }
interface SyncLog { id: number; source: string | null; status: string; started_at: string; rows_upserted: number | null; duration_s: number | null }

const { data: assessments, loading, error } = useMetricData<Assessment[]>("/assessments/")

const syncs = ref<SyncLog[]>([])
const syncsLoading = ref(true)

onMounted(async () => {
  try {
    const r = await api.get("/admin/sync-logs")
    syncs.value = r.data.logs ?? []
  } catch {
    // non-fatal
  } finally {
    syncsLoading.value = false
  }
})

function fmt(s: string) { return s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) }

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }
.range-row { display: flex; align-items: center; gap: 10px; }
.range-label { font-size: 0.78rem; color: var(--muted); font-weight: 500; white-space: nowrap; }

.section-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 12px; }
.section-desc { font-size: 0.78rem; color: var(--muted); margin: -6px 0 12px; line-height: 1.5; }

.assessment-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.assessment-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; border-left: 4px solid var(--border); }
.assessment-card.info    { border-left-color: #3B82F6; }
.assessment-card.warning { border-left-color: #D97706; }
.assessment-card.alert   { border-left-color: #DC2626; }
.assessment-card.good    { border-left-color: #16A34A; }

.card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.category { font-size: 0.8rem; font-weight: 600; color: var(--text); }
.period { margin-left: auto; font-size: 0.75rem; color: var(--muted); }
.summary { font-size: 0.87rem; color: var(--text); line-height: 1.5; }

.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.badge.info    { background: #DBEAFE; color: #1D4ED8; }
.badge.warning { background: #FEF3C7; color: #D97706; }
.badge.alert   { background: #FEE2E2; color: #DC2626; }
.badge.good    { background: #DCFCE7; color: #15803D; }

.sync-list { display: flex; flex-direction: column; gap: 4px; }
.sync-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); font-size: 0.84rem; }
.sync-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sync-status-dot.completed { background: #16A34A; }
.sync-status-dot.running   { background: #D97706; }
.sync-status-dot.failed    { background: #DC2626; }
.sync-info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.sync-source { font-weight: 600; color: var(--text); }
.sync-time { font-size: 0.75rem; color: var(--muted); }
.sync-badge { padding: 2px 8px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; }
.sync-badge.completed { background: #DCFCE7; color: #15803D; }
.sync-badge.running   { background: #FEF3C7; color: #D97706; }
.sync-badge.failed    { background: #FEE2E2; color: #DC2626; }
.sync-rows { font-family: monospace; font-size: 0.8rem; color: var(--muted); }
.sync-dur  { font-family: monospace; font-size: 0.8rem; color: var(--muted); }

.empty-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; text-align: center; }
.empty-card p { font-size: 0.875rem; color: var(--muted); }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.loading-inline { font-size: 0.85rem; color: var(--muted); }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #DC2626; padding: 16px; background: #FEF2F2; border-radius: var(--radius); font-size: 0.875rem; }
</style>
