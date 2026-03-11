<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Athlete Profile</h1>
        <p class="page-sub">Physical profile, calculated limits, and personalized HR zones</p>
      </div>
      <button v-if="dirty" class="save-btn" :disabled="saving" @click="saveProfile">
        {{ saving ? "Saving…" : "Save Changes" }}
      </button>
    </header>

    <div v-if="loading" class="loading"><div class="spinner"></div><span>Loading profile…</span></div>
    <div v-else class="content">

      <!-- Snapshot stat cards -->
      <div class="stat-grid" v-if="metrics">
        <MetricCard
          label="Age" :value="metrics.age" unit="yrs" color="#6366F1"
          source="From birth date in profile"
        />
        <MetricCard
          label="Max HR" :value="metrics.max_hr" unit="bpm" color="#EF4444"
          :source="maxHrSourceLabel"
          link-to="/cardio"
        />
        <MetricCard
          label="Resting HR" :value="metrics.resting_hr" unit="bpm" color="#8B5CF6"
          source="Manual entry in profile"
          link-to="/cardio"
        />
        <MetricCard
          label="BMR" :value="metrics.bmr" unit="kcal/day" color="#F59E0B"
          source="Mifflin-St Jeor formula"
          link-to="/calories"
        />
        <MetricCard
          label="VO₂max (est.)" :value="metrics.vo2max_estimate" unit="ml/kg/min" color="#10B981"
          :source="vo2maxSourceLabel"
          link-to="/trends"
        />
        <MetricCard
          label="Fitness Age" :value="metrics.fitness_age" unit="yrs" color="#3B82F6"
          source="Cooper Institute norms"
          link-to="/trends"
        />
      </div>

      <div class="two-col">
        <!-- Profile form -->
        <div class="card">
          <h2 class="card-title">Profile</h2>
          <p class="card-desc">Used to compute HR zones, BMR, and VO₂max. Resting HR and weight are auto-populated from your latest recorded data.</p>
          <div class="field-list">
            <div class="field-row">
              <label>Name</label>
              <input v-model="form.name" @input="dirty = true" placeholder="Your name" />
            </div>
            <div class="field-row">
              <label>Birth Date</label>
              <input type="date" v-model="form.birth_date" @input="dirty = true" />
            </div>
            <div class="field-row">
              <label>Sex</label>
              <select v-model="form.sex" @change="dirty = true">
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
            <div class="field-row">
              <label>Height</label>
              <div class="input-unit">
                <input type="number" v-model.number="form.height_cm" @input="dirty = true" step="0.1" />
                <span class="unit">cm</span>
              </div>
            </div>
            <div class="field-row">
              <label>Weight</label>
              <div class="input-unit">
                <input type="number" v-model.number="form.weight_kg" @input="dirty = true" step="0.1" />
                <span class="unit">kg</span>
              </div>
            </div>
            <div class="field-row">
              <label>Resting HR</label>
              <div class="input-unit">
                <input type="number" v-model.number="form.resting_hr" @input="dirty = true" />
                <span class="unit">bpm</span>
              </div>
            </div>
            <div class="field-row">
              <label>Max HR Override</label>
              <div class="input-unit">
                <input type="number" v-model.number="form.max_hr_override" @input="dirty = true" placeholder="Auto (Tanaka)" />
                <span class="unit">bpm</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Training guidance -->
        <div class="card" v-if="metrics">
          <h2 class="card-title">Training Guidance</h2>
          <p class="card-desc">Evidence-based targets derived from your current metrics.</p>
          <div class="guidance-list">
            <div class="guidance-item">
              <div class="guidance-label">Aerobic Base Zone</div>
              <div class="guidance-val" v-if="z2">{{ z2.min_bpm }}–{{ z2.max_bpm }} bpm</div>
              <div class="guidance-note">80% of training volume should stay in Z1–Z2. Builds mitochondrial density and fat oxidation without accumulating fatigue.</div>
            </div>
            <div class="guidance-item">
              <div class="guidance-label">Threshold Zone</div>
              <div class="guidance-val" v-if="z4">{{ z4.min_bpm }}–{{ z4.max_bpm }} bpm</div>
              <div class="guidance-note">20% of volume in Z3–Z4 raises lactate threshold and race pace.</div>
            </div>
            <div class="guidance-item">
              <div class="guidance-label">WHO Weekly Target</div>
              <div class="guidance-val">≥150 min/wk</div>
              <div class="guidance-note">Vigorous-equivalent minutes. See Intensity Minutes dashboard.</div>
            </div>
            <div class="guidance-item">
              <div class="guidance-label">Estimated TDEE</div>
              <div class="guidance-val">{{ tdee?.toLocaleString() }} kcal/day</div>
              <div class="guidance-note">BMR × 1.55 (moderately active). Compare to Calories dashboard.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Multi-method comparison tables ─── -->

      <!-- Max HR -->
      <div class="card" v-if="metrics?.max_hr_methods?.length">
        <h2 class="card-title">Max Heart Rate — Method Comparison</h2>
        <p class="card-desc">
          Age-predicted formulas differ by up to 15 bpm. The recommended value (★) is used for your HR zone calculations.
          If you have achieved a true maximum effort with a heart rate monitor, set a <strong>Manual Override</strong> in the profile above — that will always take precedence.
        </p>
        <div class="window-note" v-if="metrics.data_windows">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Measured HR values use data from the <strong>last {{ Math.round(metrics.data_windows.max_hr_days / 30) }} months</strong> only —
          HRmax declines ~0.7 bpm/year with age, so historical peaks would overestimate your current ceiling.
          <span v-if="metrics.data_windows.measured_mon_hr">
            Peak wrist HR in that window: {{ metrics.data_windows.measured_mon_hr }} bpm.
          </span>
        </div>
        <div class="method-table">
          <div
            v-for="m in metrics.max_hr_methods"
            :key="m.method"
            class="method-row"
            :class="{ recommended: m.recommended }"
          >
            <div class="method-rec">{{ m.recommended ? '★' : '' }}</div>
            <div class="method-label">{{ m.label }}</div>
            <div class="method-value">{{ m.value != null ? m.value + ' bpm' : '—' }}</div>
            <div class="method-note">{{ m.note }}</div>
          </div>
        </div>
      </div>

      <!-- VO2max -->
      <div class="card" v-if="metrics?.vo2max_methods?.length">
        <h2 class="card-title">VO₂max — Method Comparison</h2>
        <p class="card-desc">
          VO₂max (maximum oxygen uptake) is the gold standard for aerobic fitness. Lab testing (cycle ergometer or treadmill to exhaustion) is most accurate.
          The estimates below are field-based approximations. The primary estimate used in this dashboard is the average of all valid method estimates.
        </p>
        <div class="window-note" v-if="metrics.data_windows">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          <span>
            <span v-if="metrics.data_windows.garmin_vo2max">
              Garmin's estimate ({{ metrics.data_windows.garmin_vo2max }} ml/kg/min, {{ metrics.data_windows.garmin_vo2max_date }}) comes from the licensed FirstBeat algorithm and is generally the most accurate single source.
              Our field estimates use data from the <strong>last {{ metrics.data_windows.vo2max_run_days / 30 | 0 }} months</strong>.
            </span>
            <span v-else class="warn">
              No Garmin VO₂max found in the last 12 months — field estimates only.
            </span>
            <span v-if="metrics.data_windows.best_run_date"> Running-based estimate from {{ metrics.data_windows.best_run_date }}.</span>
            <span v-else-if="!metrics.data_windows.garmin_vo2max"> No qualifying run found — running-based estimate unavailable.</span>
          </span>
        </div>
        <div class="method-table">
          <div
            v-for="m in metrics.vo2max_methods"
            :key="m.method"
            class="method-row"
            :class="{ recommended: m.recommended, norm: m.method === 'age_norm', garmin: m.method === 'garmin' }"
          >
            <div class="method-rec">{{ m.recommended ? '★' : '' }}</div>
            <div class="method-label">{{ m.label }}</div>
            <div class="method-value">{{ m.value != null ? m.value + ' ml/kg/min' : '—' }}</div>
            <div class="method-note">{{ m.note }}</div>
          </div>
        </div>
      </div>

      <!-- Fitness Age -->
      <div class="card" v-if="metrics?.fitness_age_methods?.length">
        <h2 class="card-title">Fitness Age — Method Comparison</h2>
        <p class="card-desc">
          Fitness age represents the age of a person with the same VO₂max in the general population.
          A fitness age <strong>below chronological age</strong> indicates above-average cardiovascular fitness.
          Your chronological age is <strong>{{ metrics.age }}</strong>.
        </p>
        <div class="method-table">
          <div
            v-for="m in metrics.fitness_age_methods"
            :key="m.method"
            class="method-row"
            :class="{ recommended: m.recommended, garmin: m.method === 'garmin_cooper', norm: m.method === 'percentile' }"
          >
            <div class="method-rec">{{ m.recommended ? '★' : '' }}</div>
            <div class="method-label">{{ m.label }}</div>
            <div class="method-value">
              <template v-if="m.value != null">
                <span :class="fitnessAgeClass(m.value)">{{ m.value }} yrs</span>
                <span class="delta" v-if="metrics.age">
                  ({{ m.value < metrics.age ? '−' : '+' }}{{ Math.abs(Math.round(m.value - metrics.age)) }} vs chronological)
                </span>
              </template>
              <template v-else>—</template>
            </div>
            <div class="method-note">{{ m.note }}</div>
          </div>
        </div>
      </div>

      <!-- HR Zones -->
      <div class="card" v-if="metrics?.hr_zones?.length">
        <h2 class="card-title">Heart Rate Zones</h2>
        <p class="card-desc">
          Calculated using the
          <strong>{{ metrics.hr_zones_method === 'karvonen' ? 'Karvonen (Heart Rate Reserve)' : '% Max HR' }}</strong> method
          with a max HR of {{ metrics.max_hr }} bpm
          <span v-if="metrics.resting_hr"> and resting HR of {{ metrics.resting_hr }} bpm</span>.
          <span v-if="metrics.hr_zones_method === 'karvonen'">
            Karvonen accounts for your resting HR, widening zones for trained athletes with low resting HR.
          </span>
          <span v-else> Set a resting HR in your profile to enable the more personalised Karvonen method.</span>
        </p>
        <div class="zones-table">
          <div v-for="z in metrics.hr_zones" :key="z.zone" class="zone-card" :style="{ '--zone-color': zoneColor(z.zone) }">
            <div class="zone-header">
              <span class="zone-num">Z{{ z.zone }}</span>
              <span class="zone-name">{{ z.name }}</span>
              <span class="zone-range">{{ z.min_bpm }}–{{ z.max_bpm }} <span class="bpm-unit">bpm</span></span>
            </div>
            <div class="zone-bar-outer">
              <div class="zone-bar-inner" :style="{ width: zoneBarPct(z) + '%', background: zoneColor(z.zone) }"></div>
            </div>
            <div class="zone-desc">{{ z.description }}</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import MetricCard from "@/components/ui/MetricCard.vue"
import { api } from "@/api/client"

interface MethodValue {
  method: string
  label: string
  value: number | null
  recommended: boolean
  note: string
}

interface HRZone {
  zone: number
  name: string
  min_bpm: number
  max_bpm: number
  description: string
}

interface DataWindows {
  max_hr_days: number
  vo2max_run_days: number
  best_run_date: string | null
  measured_mon_hr: number | null
  measured_act_hr: number | null
  garmin_vo2max: number | null
  garmin_vo2max_date: string | null
}

interface AthleteMetrics {
  age: number
  sex: string
  max_hr: number
  max_hr_source: string
  max_hr_methods: MethodValue[]
  resting_hr: number | null
  weight_kg: number | null
  height_cm: number | null
  bmr: number | null
  vo2max_estimate: number | null
  vo2max_methods: MethodValue[]
  fitness_age: number | null
  fitness_age_methods: MethodValue[]
  hr_zones: HRZone[]
  hr_zones_method: string
  data_windows?: DataWindows
}

interface ProfileForm {
  name: string
  birth_date: string
  sex: string
  height_cm: number | null
  weight_kg: number | null
  resting_hr: number | null
  max_hr_override: number | null
}

const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
const metrics = ref<AthleteMetrics | null>(null)
const form = ref<ProfileForm>({
  name: "", birth_date: "", sex: "male",
  height_cm: null, weight_kg: null, resting_hr: null, max_hr_override: null,
})

async function loadAll() {
  loading.value = true
  try {
    const [profileResp, metricsResp] = await Promise.all([
      api.get("/admin/profile"),
      api.get("/admin/athlete-metrics"),
    ])
    const p = profileResp.data
    form.value = {
      name: p.name ?? "",
      birth_date: p.birth_date ?? "",
      sex: p.sex ?? "male",
      height_cm: p.height_cm ?? null,
      weight_kg: p.weight_kg ?? null,
      resting_hr: p.resting_hr ?? null,
      max_hr_override: p.max_hr_override ?? null,
    }
    metrics.value = metricsResp.data
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const params: Record<string, any> = {}
    if (form.value.name)       params.name = form.value.name
    if (form.value.birth_date) params.birth_date = form.value.birth_date
    if (form.value.sex)        params.sex = form.value.sex
    if (form.value.height_cm)  params.height_cm = form.value.height_cm
    if (form.value.weight_kg)  params.weight_kg = form.value.weight_kg
    if (form.value.resting_hr) params.resting_hr = form.value.resting_hr
    params.max_hr_override = form.value.max_hr_override ?? 0
    await api.put("/admin/profile", null, { params })
    const metricsResp = await api.get("/admin/athlete-metrics")
    metrics.value = metricsResp.data
    dirty.value = false
  } finally {
    saving.value = false
  }
}

onMounted(loadAll)

const z2  = computed(() => metrics.value?.hr_zones.find(z => z.zone === 2) ?? null)
const z4  = computed(() => metrics.value?.hr_zones.find(z => z.zone === 4) ?? null)
const tdee = computed(() => metrics.value?.bmr ? Math.round(metrics.value.bmr * 1.55) : null)

const MAX_HR_SOURCE_LABELS: Record<string, string> = {
  override: "Manual override",
  measured_monitoring: "Measured (wrist sensor, last 12 mo)",
  measured_activities: "Measured (activity HR, last 12 mo)",
  tanaka: "Tanaka formula (208 − 0.7 × age)",
  fox: "Fox formula (220 − age)",
}
const maxHrSourceLabel = computed(() =>
  MAX_HR_SOURCE_LABELS[metrics.value?.max_hr_source ?? ""] ?? metrics.value?.max_hr_source ?? ""
)

const vo2maxSourceLabel = computed(() => {
  if (!metrics.value) return ""
  const dw = metrics.value.data_windows
  const methods = metrics.value.vo2max_methods ?? []
  const validMethods = methods.filter(m => m.method !== 'age_norm' && m.value != null)
  if (!validMethods.length) return "No estimate available"
  const names = validMethods.map(m => {
    if (m.method === 'garmin') return 'Garmin'
    if (m.method === 'uth') return 'Uth'
    if (m.method === 'running') return 'Running'
    if (m.method === 'scharhag') return 'Scharhag'
    return m.method
  })
  return `Avg of: ${names.join(', ')}`
})

const ZONE_COLORS = ["#60A5FA", "#34D399", "#FBBF24", "#F97316", "#EF4444"]
function zoneColor(zone: number) { return ZONE_COLORS[(zone - 1) % 5] }
function zoneBarPct(z: HRZone): number {
  return Math.round((z.max_bpm / (metrics.value?.max_hr ?? 200)) * 100)
}

function fitnessAgeClass(fitnessAge: number): string {
  if (!metrics.value) return ""
  return fitnessAge < metrics.value.age - 5 ? "age-great"
       : fitnessAge < metrics.value.age     ? "age-good"
       : "age-neutral"
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 24px; max-width: 1100px; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; }
.page-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; color: var(--text); }
.page-sub { margin-top: 4px; font-size: 0.83rem; color: var(--muted); }

.save-btn {
  padding: 8px 20px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; font-size: 0.85rem; font-weight: 600;
  cursor: pointer; transition: background 0.15s;
}
.save-btn:hover:not(:disabled) { background: #2563eb; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.content { display: flex; flex-direction: column; gap: 24px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .two-col { grid-template-columns: 1fr; } }

.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; }
.card-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin: 0 0 4px; }
.card-desc { font-size: 0.78rem; color: var(--muted); margin: 0 0 16px; line-height: 1.5; }

/* Profile form */
.field-list { display: flex; flex-direction: column; gap: 10px; }
.field-row { display: flex; align-items: center; gap: 12px; }
.field-row label { font-size: 0.8rem; color: var(--muted); font-weight: 500; width: 130px; flex-shrink: 0; }
.field-row input, .field-row select {
  flex: 1; font-size: 0.83rem; padding: 5px 8px;
  border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg); color: var(--text); outline: none;
}
.field-row input:focus, .field-row select:focus { border-color: var(--accent); }
.input-unit { display: flex; align-items: center; gap: 6px; flex: 1; }
.input-unit input { flex: 1; }
.unit { font-size: 0.75rem; color: var(--muted); white-space: nowrap; }

/* Training guidance */
.guidance-list { display: flex; flex-direction: column; gap: 12px; }
.guidance-item { padding: 10px 12px; background: var(--bg); border-radius: 8px; border: 1px solid var(--border); }
.guidance-label { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 3px; }
.guidance-val { font-size: 1.15rem; font-weight: 800; color: var(--text); margin-bottom: 4px; }
.guidance-note { font-size: 0.73rem; color: var(--muted); line-height: 1.4; }

/* Data window provenance note */
.window-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 0.76rem;
  color: var(--muted);
  background: color-mix(in srgb, var(--accent) 5%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 15%, transparent);
  border-radius: 7px;
  padding: 8px 12px;
  margin-bottom: 14px;
  line-height: 1.5;
}
.window-note svg { width: 14px; height: 14px; flex-shrink: 0; margin-top: 1px; color: var(--accent); }
.window-note .warn { color: #D97706; }

/* Method comparison tables */
.method-table { display: flex; flex-direction: column; gap: 0; }
.method-row {
  display: grid;
  grid-template-columns: 18px 220px 140px 1fr;
  gap: 12px;
  align-items: start;
  padding: 10px 12px;
  border-radius: 6px;
  transition: background 0.1s;
}
.method-row:hover { background: var(--bg); }
.method-row.recommended {
  background: color-mix(in srgb, var(--accent) 6%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 20%, transparent);
  border-radius: 8px;
}
.method-row.norm { opacity: 0.65; }
.method-row.garmin {
  background: color-mix(in srgb, #16A34A 6%, transparent);
  border: 1px solid color-mix(in srgb, #16A34A 20%, transparent);
  border-radius: 8px;
}
.method-rec { font-size: 0.85rem; color: var(--accent); font-weight: 700; padding-top: 1px; }
.method-label { font-size: 0.82rem; font-weight: 600; color: var(--text); }
.method-value { font-size: 0.88rem; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
.method-note { font-size: 0.75rem; color: var(--muted); line-height: 1.45; }

/* Fitness age colouring */
.age-great { color: #10B981; font-weight: 700; }
.age-good  { color: #3B82F6; font-weight: 700; }
.age-neutral { color: var(--text); }
.delta { font-size: 0.75rem; font-weight: 400; color: var(--muted); margin-left: 6px; }

/* HR Zones */
.zones-table { display: flex; flex-direction: column; gap: 10px; }
.zone-card { border-left: 3px solid var(--zone-color); padding: 10px 14px; background: var(--bg); border-radius: 0 8px 8px 0; }
.zone-header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 6px; }
.zone-num { font-size: 0.72rem; font-weight: 800; color: var(--zone-color); text-transform: uppercase; letter-spacing: 0.05em; }
.zone-name { font-size: 0.88rem; font-weight: 600; color: var(--text); flex: 1; }
.zone-range { font-size: 0.95rem; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
.bpm-unit { font-size: 0.72rem; color: var(--muted); font-weight: 400; }
.zone-bar-outer { height: 4px; background: var(--border); border-radius: 2px; margin-bottom: 6px; }
.zone-bar-inner { height: 4px; border-radius: 2px; }
.zone-desc { font-size: 0.75rem; color: var(--muted); line-height: 1.4; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.875rem; padding: 40px 0; }
.spinner { width: 18px; height: 18px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
