<template>
  <div class="metric-card">
    <div class="card-header">
      <span class="label">{{ label }}</span>
      <span v-if="delta !== undefined" class="delta" :class="deltaClass">
        {{ delta > 0 ? '+' : '' }}{{ delta }}{{ unit ?? '' }}
      </span>
    </div>

    <div class="value-row">
      <span class="value">{{ formatted }}</span>
      <span v-if="unit" class="unit">{{ unit }}</span>
    </div>

    <div v-if="source || linkTo" class="card-footer">
      <span v-if="source" class="source-note">{{ source }}</span>
      <RouterLink v-if="linkTo" :to="linkTo" class="trend-link" title="View trend">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
      </RouterLink>
    </div>

    <div v-if="sparkData && sparkData.length > 1" class="sparkline-wrap">
      <svg viewBox="0 0 100 32" preserveAspectRatio="none" class="sparkline">
        <defs>
          <linearGradient :id="`grad-${uid}`" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="color" stop-opacity="0.18"/>
            <stop offset="100%" :stop-color="color" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path :d="areaPath" :fill="`url(#grad-${uid})`"/>
        <polyline :points="sparkPoints" fill="none" :stroke="color" stroke-width="1.8"
                  stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

const props = defineProps<{
  label: string
  value: number | string | null | undefined
  unit?: string
  color?: string
  sparkData?: (number | null)[]
  delta?: number
  trendDirection?: 'up' | 'down' | 'neutral'
  source?: string    // short method attribution shown below the value
  linkTo?: string    // router-link path for "view trend" arrow
}>()

const uid = Math.random().toString(36).slice(2, 8)

const formatted = computed(() => {
  if (props.value === null || props.value === undefined) return '—'
  if (typeof props.value === 'number') {
    return props.value >= 1000
      ? props.value.toLocaleString()
      : props.value % 1 === 0
        ? props.value.toString()
        : props.value.toFixed(1)
  }
  return props.value
})

const deltaClass = computed(() => {
  if (!props.trendDirection) return ''
  return props.trendDirection === 'up' ? 'delta-up'
       : props.trendDirection === 'down' ? 'delta-down'
       : 'delta-neutral'
})

const sparkPoints = computed(() => {
  if (!props.sparkData || props.sparkData.length < 2) return ''
  const vals = props.sparkData
  const clean = vals.filter((v): v is number => v !== null)
  if (!clean.length) return ''
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const range = max - min || 1
  const n = vals.length
  return vals
    .map((v, i) => {
      if (v === null) return null
      const x = (i / (n - 1)) * 100
      const y = 28 - ((v - min) / range) * 22
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .filter(Boolean)
    .join(' ')
})

const areaPath = computed(() => {
  if (!props.sparkData || props.sparkData.length < 2) return ''
  const vals = props.sparkData
  const clean = vals.filter((v): v is number => v !== null)
  if (!clean.length) return ''
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const range = max - min || 1
  const n = vals.length
  const pts = vals
    .map((v, i) => {
      if (v === null) return null
      const x = (i / (n - 1)) * 100
      const y = 28 - ((v - min) / range) * 22
      return [x, y] as [number, number]
    })
    .filter((p): p is [number, number] => p !== null)
  if (!pts.length) return ''
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1]
  const first = pts[0]
  return `${line} L${last[0].toFixed(1)},32 L${first[0].toFixed(1)},32 Z`
})
</script>

<style scoped>
.metric-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  transition: box-shadow 0.15s;
}
.metric-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.07);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted);
}

.delta {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 4px;
  background: #F0F0ED;
  color: var(--muted);
}
.delta-up   { background: #F0FDF4; color: #16A34A; }
.delta-down { background: #FEF2F2; color: #DC2626; }

.value-row {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.value {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--text);
  line-height: 1;
}

.unit {
  font-size: 0.85rem;
  font-weight: 400;
  color: var(--muted);
  margin-bottom: 1px;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 5px;
}
.source-note {
  font-size: 0.68rem;
  color: var(--muted);
  line-height: 1.3;
  flex: 1;
}
.trend-link {
  display: flex;
  align-items: center;
  color: var(--muted);
  transition: color 0.12s;
  flex-shrink: 0;
  padding: 2px;
}
.trend-link:hover { color: var(--accent); }
.trend-link svg { width: 13px; height: 13px; }

.sparkline-wrap {
  margin-top: 10px;
  height: 32px;
}
.sparkline {
  width: 100%;
  height: 32px;
  display: block;
  overflow: visible;
}
</style>
