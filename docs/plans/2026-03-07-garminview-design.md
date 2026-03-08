# GarminView — System Design

> **Version**: 1.0 — 2026-03-07
> **Status**: Approved
> **Requirements**: `docs/REQUIREMENTS.md`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Model & Schema](#2-data-model--schema)
3. [Ingestion Pipeline](#3-ingestion-pipeline)
4. [Analysis Engine](#4-analysis-engine)
5. [FastAPI Layer & Vue.js Frontend](#5-fastapi-layer--vuejs-frontend)
6. [Marimo Notebooks](#6-marimo-notebooks)
7. [Export](#7-export)
8. [Scheduling & Automation](#8-scheduling--automation)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Build Phases](#10-build-phases)

---

## 1. Architecture Overview

### 1.1 Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI |
| Frontend | Vue.js 3.x (Composition API), Apache ECharts via vue-echarts |
| Database | SQLite (dev/single-user) or MariaDB (production) — selectable via config |
| ORM | SQLAlchemy 2.x + Alembic migrations |
| Scheduling | APScheduler (in-process), cron/systemd (external alternative) |
| Notebooks | Marimo |
| State management | Pinia |

### 1.2 Project Structure

```
garminview/
├── backend/
│   ├── garminview/
│   │   ├── core/               # Config, DB engine factory, logging
│   │   ├── models/             # SQLAlchemy models (all tables)
│   │   ├── ingestion/          # Data source adapters + orchestrator
│   │   │   ├── garmindb/       # GarminDB download pipeline wrapper
│   │   │   ├── garminconnect/  # python-garminconnect supplemental adapters
│   │   │   ├── base.py         # Abstract adapter interface
│   │   │   ├── orchestrator.py
│   │   │   └── rate_limiter.py
│   │   ├── analysis/           # Derived metrics + assessments
│   │   │   ├── metrics/
│   │   │   ├── assessments/
│   │   │   ├── correlations/
│   │   │   └── engine.py
│   │   ├── api/                # FastAPI routers + Pydantic schemas
│   │   │   ├── routes/
│   │   │   └── schemas/
│   │   └── scheduler/          # APScheduler integration
│   ├── notebooks/              # Marimo notebooks + shared utilities
│   ├── tests/
│   │   ├── unit/
│   │   └── validation/         # GarminDB comparison suite
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── views/              # One file per dashboard
│   │   ├── components/
│   │   │   ├── charts/
│   │   │   ├── ui/
│   │   │   └── admin/
│   │   ├── stores/             # Pinia stores
│   │   └── composables/
│   └── package.json
└── docker-compose.yml
```

### 1.3 Two-Database Strategy

GarminDB owns its 5 SQLite databases as a **staging/parse cache only**. garminview owns a single runtime database (SQLite in dev, MariaDB in production).

```
Raw files on disk (FIT/JSON)     ← permanent archive, never deleted
         ↓  GarminDB download.py
GarminDB SQLite files            ← temporary parse cache, disposable
         ↓  garminview ingestion layer
garminview DB (SQLite or MariaDB) ← single runtime source of truth
```

In MariaDB (production) mode: no SQLite is ever queried at runtime. GarminDB SQLite files are ephemeral intermediaries that can be deleted and rebuilt at any time from the raw files on disk via `garmindb_cli.py --rebuild_db`.

GarminDB is used:
- As a **download pipeline** — authenticates with Garth, fetches FIT/JSON files to disk
- As a **FIT parser library** — `fitparse` used directly by garminview's import layer
- As a **validation reference** — GarminDB pipeline output vs garminview DB output compared in the test suite

### 1.4 Dual Database Support

```python
# core/database.py
def create_engine_from_config(config: Config) -> Engine:
    if config.db_backend == "mariadb":
        return create_engine(f"mysql+pymysql://{config.db_url}", ...)
    return create_engine(f"sqlite:///{config.db_path}", ...)
```

One config switch. All SQLAlchemy models and Alembic migrations work against both backends unchanged.

---

## 2. Data Model & Schema

All tables live in garminview's database. GarminDB tables are read transiently during ingestion only.

### Group 1 — Daily Health

| Table | Key Fields | Source |
|---|---|---|
| `daily_summary` | date PK, steps, floors, distance, calories_total/bmr/active, hr_avg/min/max/resting, stress_avg, body_battery_max/min, spo2_avg, respiration_avg, hydration_intake/goal, intensity_mod/vig, sleep_score | GarminDB DailySummary |
| `sleep` | date PK, start, end, total_sleep_min, deep/light/rem/awake_min, score, qualifier, avg_spo2, avg_respiration, avg_stress | GarminDB Sleep |
| `sleep_events` | id PK, date, event_type, start, duration_min | GarminDB SleepEvents |
| `weight` | date PK, weight_kg | GarminDB Weight |
| `stress` | timestamp PK, stress_level | GarminDB Stress |
| `resting_heart_rate` | date PK, resting_hr | GarminDB RestingHeartRate |

### Group 2 — Minute-Level Monitoring

| Table | Key Fields |
|---|---|
| `monitoring_heart_rate` | timestamp PK, hr |
| `monitoring_intensity` | timestamp PK, moderate_time_s, vigorous_time_s |
| `monitoring_steps` | timestamp PK, steps, activity_type |
| `monitoring_respiration` | timestamp PK, rr |
| `monitoring_pulse_ox` | timestamp PK, spo2 |
| `monitoring_climb` | timestamp PK, ascent_m, descent_m, cum_ascent_m, cum_descent_m |

### Group 3 — Activities

| Table | Key Fields |
|---|---|
| `activities` | activity_id PK, name, type, sport, sub_sport, start_time, elapsed_time_s, moving_time_s, distance_m, calories, avg_hr, max_hr, avg_cadence, avg_speed, ascent_m, descent_m, training_load, aerobic_effect, anaerobic_effect, source |
| `activity_laps` | activity_id + lap_index PK, all timing/HR/cadence/speed/elevation fields |
| `activity_records` | activity_id + record_index PK, timestamp, lat, lon, distance_m, hr, cadence, altitude_m, speed, power |
| `activity_splits` | activity_id + split_index PK, type, distance_m, duration_s, avg_hr, avg_speed |
| `steps_activities` | activity_id PK, pace_avg/moving/max, steps_per_min, step_length_m, vertical_oscillation_mm, vertical_ratio_pct, gct_ms, stance_pct, vo2max |
| `activity_hr_zones` | activity_id + zone PK, time_in_zone_s |

### Group 4 — Supplemental Garmin API Data

Metrics not captured by GarminDB — fetched via python-garminconnect:

| Table | Key Fields |
|---|---|
| `hrv_data` | date PK, hrv_rmssd, hrv_5min_high, hrv_5min_low, baseline_low, baseline_high, status |
| `training_readiness` | date PK, score, sleep_score, recovery_score, training_load_score, hrv_score, status |
| `training_status` | date PK, status, load_ratio |
| `body_battery_events` | id PK, date, start, end, value, event_type (drain/charge), activity_id |
| `vo2max` | date PK, vo2max_running, vo2max_cycling, fitness_age |
| `race_predictions` | date PK, pred_5k_s, pred_10k_s, pred_half_s, pred_full_s |
| `lactate_threshold` | date PK, lt_speed, lt_hr, lt_power |
| `hill_score` | date PK, score |
| `endurance_score` | date PK, score |
| `personal_records` | id PK, activity_type, metric, value, achieved_date |
| `body_composition` | date PK, weight_kg, fat_pct, muscle_mass_kg, bone_mass_kg, hydration_pct, bmi, bmr, metabolic_age, visceral_fat, physique_rating |
| `blood_pressure` | id PK, timestamp, systolic, diastolic, pulse |
| `gear` | gear_uuid PK, name, type, status, date_begin, date_end |
| `gear_stats` | gear_uuid PK, total_distance_m, total_activities |

### Group 5 — Derived Metrics

| Table | Key Fields |
|---|---|
| `daily_derived` | date PK, trimp, atl, ctl, tsb, acwr, monotony, strain, sleep_efficiency_pct, sleep_debt_min, sleep_sri, social_jet_lag_h, lbm_kg, ffmi, body_recomp_index, weight_velocity, readiness_composite, wellness_score, overtraining_risk (0-3), injury_risk |
| `weekly_derived` | week_start PK, atl_avg, ctl_avg, tsb_avg, weekly_load, polarized_z1_pct, z2_pct, z3_pct, intensity_min_mod, intensity_min_vig |
| `activity_derived` | activity_id PK, efficiency_factor, pace_decoupling_pct, cardiac_drift_pct, hr_recovery_1min, hr_recovery_2min |

### Group 6 — Assessments & Goals

| Table | Key Fields |
|---|---|
| `goals` | id PK, metric, target_value, target_date, created_at, status (on_track/behind/ahead/achieved/abandoned) |
| `assessments` | id PK, period_type (weekly/monthly), period_start, category, severity (info/caution/warning), summary_text, supporting_metrics JSON |
| `trend_classifications` | id PK, date, metric, direction (improving/stable/declining/insufficient_data), lookback_days, slope, r_squared, p_value |
| `correlation_results` | id PK, computed_at, metric_a, metric_b, lag_days, r_pearson, r_spearman, p_value, n_samples |
| `data_quality_flags` | id PK, date, metric, flag_type (missing/implausible/duplicate/gap), value, message |

### Group 7 — Sync & Provenance

| Table | Key Fields |
|---|---|
| `sync_log` | id PK, started_at, finished_at, source, mode (full/incremental/analysis_only), date_start, date_end, records_upserted, status (success/partial/failed), error_message |
| `data_provenance` | table_name, record_id, source, imported_at |

### Group 8 — Configuration

| Table | Key Fields |
|---|---|
| `user_profile` | id PK, name, birth_date, sex, height_cm, units (metric/imperial) |
| `app_config` | key PK, value, data_type, category, description, updated_at |
| `sync_schedule` | id PK, source, mode, cron_expression, enabled, last_run, next_run |
| `goal_benchmarks` | id PK, metric, target_value, source (user/acsm/who/nsf), updated_at |
| `notification_config` | id PK, event_type, channel (email/desktop), enabled, config_json |

### Group 9 — Schema Versioning

| Table | Key Fields |
|---|---|
| `schema_version` | id PK, version, description, applied_at, applied_by |

On startup, garminview checks the DB schema version against the codebase's expected version. If mismatched, it warns and refuses to start until `alembic upgrade head` is run. Alembic's own `alembic_version` table manages migration state; `schema_version` is a human-readable audit log.

---

## 3. Ingestion Pipeline

### 3.1 Pipeline Phases

```
Phase 1: DOWNLOAD
  GarminDB download.py → raw FIT/JSON files to ~/HealthData/  (disk)
  python-garminconnect → supplemental API data               (API)

Phase 2: PARSE & IMPORT
  garminview file adapters → read raw files → upsert to DB

Phase 3: SUPPLEMENTAL
  garminview API adapters → HRV, readiness, race predictions → upsert to DB

Phase 4: DERIVED METRICS
  analysis engine → reads DB → calculates all derived metrics → upsert daily_derived

Phase 5: ASSESSMENTS
  assessment engine → trend classifications, correlations, flags → upsert assessments
```

### 3.2 Adapter Interface

```python
# ingestion/base.py
class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]: ...

    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    def target_table(self) -> str: ...
```

All imports use upsert semantics (`insert().on_conflict_do_update()`). Re-running any adapter is always safe.

### 3.3 Adapters

**File adapters** (read raw files from disk):

| Adapter | Source Files | Target Tables |
|---|---|---|
| `DailySummaryAdapter` | `~/HealthData/monitoring/*.json` | `daily_summary` |
| `SleepAdapter` | `~/HealthData/sleep/*.json` | `sleep`, `sleep_events` |
| `WeightAdapter` | `~/HealthData/weight/*.json` | `weight` |
| `RHRAdapter` | `~/HealthData/rhr/*.json` | `resting_heart_rate` |
| `MonitoringFitAdapter` | `~/HealthData/monitoring/*.fit` | `monitoring_*` tables |
| `ActivityJsonAdapter` | `~/HealthData/activities/*.json` | `activities` |
| `ActivityFitAdapter` | `~/HealthData/activities/*.fit` | `activity_records`, `activity_laps`, `activity_splits`, `steps_activities` |

FIT parsing uses `fitparse` directly (already a GarminDB dependency).

**API adapters** (python-garminconnect):

| Adapter | API Method | Target Table |
|---|---|---|
| `HRVAdapter` | `get_hrv_data` | `hrv_data` |
| `TrainingReadinessAdapter` | `get_training_readiness` | `training_readiness` |
| `TrainingStatusAdapter` | `get_training_status` | `training_status` |
| `BodyBatteryAdapter` | `get_body_battery_events` | `body_battery_events` |
| `VO2MaxAdapter` | `get_max_metrics`, `get_fitnessage_data` | `vo2max` |
| `BodyCompositionAdapter` | `get_body_composition` | `body_composition` |
| `RacePredictionsAdapter` | `get_race_predictions` | `race_predictions` |
| `LactateThresholdAdapter` | `get_lactate_threshold` | `lactate_threshold` |
| `HillScoreAdapter` | `get_hill_score` | `hill_score` |
| `EnduranceScoreAdapter` | `get_endurance_score` | `endurance_score` |
| `PersonalRecordsAdapter` | `get_personal_records` | `personal_records` |
| `BloodPressureAdapter` | `get_blood_pressure` | `blood_pressure` |
| `GearAdapter` | `get_gear`, `get_gear_stats` | `gear`, `gear_stats` |

### 3.4 Orchestrator

```python
# ingestion/orchestrator.py
class IngestionOrchestrator:
    def run_full(self, start_date: date, end_date: date): ...
    def run_incremental(self): ...       # since MAX(date) per table
    def run_analysis_only(self): ...     # re-run derived metrics + assessments
```

Incremental runs use `MAX(date)` per target table as the backfill cursor.

### 3.5 Rate Limiting & Error Handling

- All API adapters use `tenacity` retry with exponential backoff on `GarminConnectTooManyRequestsError` (429): 30s → 60s → 120s → 300s, max 5 attempts
- Date ranges >28 days auto-chunked into 28-day batches
- Failed adapters log to `sync_log` and are skipped — they don't abort the run
- Every run writes a `sync_log` row with record counts and status

### 3.6 Validation Suite

```
tests/validation/
├── run_garmindb_pipeline.py   # runs GarminDB against reference raw files → SQLite
├── run_garminview_pipeline.py # runs garminview against same files → test DB
└── compare_outputs.py         # diffs table by table, field by field, asserts match
```

Used once to validate garminview's parsers match GarminDB's reference output. After validation, GarminDB is no longer a runtime dependency.

---

## 4. Analysis Engine

The analysis engine is **purely computational** — reads from DB, calculates, writes back. Never calls APIs or touches raw files. Re-runnable at any time.

### 4.1 Structure

```
analysis/
├── metrics/
│   ├── training_load.py      # TRIMP, ATL, CTL, TSB, ACWR, monotony, strain
│   ├── sleep_science.py      # efficiency, SRI, debt, social jet lag, deep adequacy
│   ├── cardiovascular.py     # HRV CV%, autonomic score, HRR, RHR z-score, cardiac drift
│   ├── body_composition.py   # LBM, FFMI, recomp index, weight velocity, TDEE
│   ├── performance.py        # efficiency factor, pace decoupling, running economy
│   └── composite_scores.py   # wellness score, readiness composite, overtraining risk
├── assessments/
│   ├── trend_classifier.py   # OLS linear regression → improving/stable/declining
│   ├── benchmarks.py         # population norms (RHR, VO2Max, body fat, BMI, etc.)
│   └── goal_tracker.py       # progress %, projected date, status classification
├── correlations/
│   ├── correlation_engine.py # Pearson/Spearman + p-value + lagged correlations
│   └── pattern_detector.py   # day-of-week, seasonal, habit streaks, anomaly clusters
└── engine.py                 # AnalysisEngine — top-level orchestrator
```

### 4.2 Training Load Metrics

All EWMA metrics computed forward from earliest date with data:

| Metric | Formula |
|---|---|
| TRIMP | `duration_min × (avg_hr/max_hr) × exp(1.92 × avg_hr/max_hr)` (Banister 1991) |
| ATL | EWMA τ=7: `ATL_t = ATL_(t-1) + (TRIMP − ATL_(t-1)) / 7` |
| CTL | EWMA τ=42 |
| TSB | `CTL − ATL` |
| ACWR | `ATL / CTL` |
| Monotony | `mean(7d_load) / std(7d_load)` |
| Strain | `weekly_load × monotony` |

Full series recalculated from day 0 on each run (EWMA is history-dependent).

### 4.3 Sleep Science Metrics

| Metric | Formula |
|---|---|
| Sleep Efficiency | `(total_sleep − awake) / time_in_bed × 100` |
| Sleep Debt | `Σ(target_hours − actual_hours)` over rolling N days (configurable target, default 8h) |
| Sleep Regularity Index | Probability of same sleep/wake state at same clock time across consecutive day pairs |
| Social Jet Lag | `\|weekend_sleep_midpoint − weekday_sleep_midpoint\|` in hours |
| Deep Sleep Adequacy | `deep_min / total_sleep_min` vs age-adjusted target (15–20%) |
| REM Rebound | Flag nights with >30% REM following ≥2 nights below 15% REM |

### 4.4 Composite Scores

**Readiness Composite** (0–100):
```
score = 0.30 × normalize(hrv_rmssd, baseline)
      + 0.25 × normalize(resting_hr, 30d_mean, inverted=True)
      + 0.20 × normalize(sleep_score, 0, 100)
      + 0.15 × normalize(body_battery_max, 0, 100)
      + 0.10 × normalize(stress_avg, 0, 100, inverted=True)
```

**Overtraining Risk** (0–3 composite flag):
```
+1 if RHR > (30d_mean + 2×SD)
+1 if HRV < (7d_baseline − 1×SD)
+1 if ACWR > 1.5 or monotony > 2.0
```

### 4.5 Trend Classifier

For each tracked metric, OLS linear regression over configurable lookback windows (7, 14, 30, 90 days). All four stored per metric per run date. Insufficient data (<7 samples or p > 0.05) → `direction="insufficient_data"`.

### 4.6 Benchmarks

Static reference tables embedded in code (ACSM, AHA, WHO, NSF). `classify_metric(metric, value, age, sex)` returns classification + reference label used by assessment narrative generator.

### 4.7 Correlation Engine

Pearson + Spearman correlations with p-value for all metric pairs in `CORRELATION_PAIRS` config. Lagged correlations (lag_days 0–7) computed to detect next-day predictive relationships. Monthly scheduled run; significant results (p < 0.05) surfaced in Correlation Explorer.

---

## 5. FastAPI Layer & Vue.js Frontend

### 5.1 API Routes

```
GET/POST  /health/*           — daily summary, sleep, HR, stress, body battery
GET       /activities/*       — list, detail, splits, laps, records
GET       /training/*         — ATL/CTL/TSB, readiness, training status
GET       /body/*             — weight, body composition trends
GET       /correlations/*     — correlation matrix, scatter data
GET       /assessments/*      — weekly/monthly narratives, trend classifications
CRUD      /goals/*            — goal management + progress
GET       /export/*           — CSV, JSON, PDF, PNG, ZIP, static HTML
GET/POST  /sync/*             — trigger, status stream (SSE), logs
GET       /data-quality/*     — completeness, flags, freshness
CRUD      /admin/*            — all config, schedules, profile, schema version
```

All list endpoints support: `?start=YYYY-MM-DD&end=YYYY-MM-DD&page=1&limit=100`

SSE endpoint at `/sync/stream` pushes live sync progress to the frontend.

### 5.2 Admin API

```
GET/PUT  /admin/profile
GET/PUT  /admin/config               — all app_config, grouped by category
GET/PUT  /admin/config/{key}         — single config key
GET/PUT  /admin/schedules            — sync schedule list
PUT      /admin/schedules/{id}       — update cron, enable/disable
POST     /admin/schedules/{id}/run   — manual trigger
GET/PUT  /admin/benchmarks
GET/PUT  /admin/notifications
GET      /admin/schema-version       — migration audit log
```

### 5.3 Frontend Views

| View | Route |
|---|---|
| Daily Overview | `/` |
| Sleep Dashboard | `/sleep` |
| Weight & Body Comp | `/body` |
| Cardiovascular | `/cardio` |
| Training Load | `/training` |
| Activity Summary | `/activities` |
| Running | `/running` |
| Recovery & Stress | `/recovery` |
| Long-Term Trends | `/trends` |
| Correlation Explorer | `/correlations` |
| Assessments & Goals | `/assessments` |
| Data Quality | `/data-quality` |
| Admin | `/admin` |

### 5.4 Admin UI Tabs

| Tab | Content |
|---|---|
| Profile | Name, birth date, sex, height, units |
| Sync Schedules | Cron expression editor, enable/disable, last/next run, manual trigger |
| App Config | Grouped key-value editor — Analysis, Sleep, Training, UI categories |
| Benchmarks | Per-metric target overrides (personal vs. population defaults) |
| Notifications | Sync failure alerts, channel config |
| Schema & Migrations | Read-only migration history (version, description, applied_at) |
| Data Sources | Adapter status — last sync, record count, freshness per source |

### 5.5 Chart Components

All charts use **Apache ECharts via vue-echarts**.

| Component | Used For |
|---|---|
| `TimeSeriesChart.vue` | All trend lines with configurable rolling averages |
| `StackedBarChart.vue` | Sleep stages, activity types, HR zones |
| `CalendarHeatmap.vue` | Training calendar, day-of-week patterns |
| `ScatterPlot.vue` | Correlation explorer |
| `PMCChart.vue` | ATL/CTL/TSB performance management chart |
| `Hypnogram.vue` | Per-night sleep stage timeline |
| `Sparkline.vue` | Compact metric trend in MetricCard |

### 5.6 Shared Composables

| Composable | Purpose |
|---|---|
| `useMetricData.ts` | Generic data fetching with date range reactive params |
| `useChartOptions.ts` | Shared ECharts config, dark/light mode aware |
| `useSyncStatus.ts` | SSE subscription for live sync progress |

---

## 6. Marimo Notebooks

```
backend/notebooks/
├── health_explorer.py       # sleep, weight, HR, HRV, stress — interactive widgets
├── activity_explorer.py     # filter by type/date/distance, pace/HR/elevation
├── correlation_explorer.py  # any two metrics, scatter + regression + stats
├── training_load.py         # interactive PMC chart, adjustable τ, ACWR
└── shared/
    ├── db.py                # DB connection from app_config
    ├── queries.py           # parameterized queries reused across notebooks
    ├── metrics.py           # symlinked/installed from analysis/metrics/ — same code
    └── charts.py            # shared chart builders (ECharts/Plotly)
```

`notebooks/shared/metrics.py` is the same module as `analysis/metrics/` — notebooks and the web backend share one implementation. No metric calculation divergence possible.

Each notebook runs standalone via `marimo run <notebook>.py` with no web server dependency.

---

## 7. Export

| Format | Implementation | Endpoint |
|---|---|---|
| CSV | Python `csv` stdlib, streamed | `GET /export/csv?metrics=...&start=...&end=...` |
| JSON | FastAPI `StreamingResponse` | `GET /export/json?...` |
| PNG/SVG | `pyecharts` server-side render | `GET /export/chart?dashboard=sleep&format=png` |
| PDF | `WeasyPrint` renders HTML report template | `GET /export/pdf?report=weekly&period=2026-03-01` |
| ZIP | `zipfile` stdlib, bundles all formats | `GET /export/zip?start=...&end=...` |
| Static HTML | Jinja2 template + embedded chart data | `GET /export/html?report=monthly&period=2026-02` |

---

## 8. Scheduling & Automation

APScheduler runs inside the FastAPI process. Schedules are loaded from `sync_schedule` table on startup. Hot-reload on `PUT /admin/schedules/{id}` — no restart needed.

**Default schedules** (stored in DB, user-editable via admin UI):

| Job | Default Cron | Mode |
|---|---|---|
| Garmin incremental sync | `0 6 * * *` | incremental |
| Analysis re-run | `30 6 * * *` | analysis_only |
| Correlation computation | `0 3 * * 0` | correlations |
| Weekly assessment | `0 7 * * 1` | assessments |

---

## 9. Non-Functional Requirements

| Concern | Approach |
|---|---|
| Performance | Materialized `daily_derived` table — dashboards query pre-computed values. Indexed on `date`. Target: <2s for 5yr datasets. |
| Security | JWT in `httpOnly` cookie. Auth dependency on all FastAPI routes. No sensitive data in URLs. Garmin OAuth token in `~/.garminconnect` (Garth), not in DB. |
| Graceful degradation | Every metric is nullable — missing HRV device, no scale, no blood pressure → shows "no data" without breaking other charts. |
| Idempotency | All imports use `insert().on_conflict_do_update()`. Re-running any pipeline phase is safe. |
| Logging | `structlog` structured JSON logging. Verbosity via `app_config` key `logging.level`. Sync logs written to both `sync_log` table and log files. |
| Units | All values stored in metric internally. Converted to imperial at API response time based on `user_profile.units`. |
| Migrations | Alembic manages schema. `schema_version` table provides human-readable audit log. On startup, version mismatch → warn + refuse to start. |
| Testing | pytest + in-memory SQLite for unit tests. `tests/validation/` runs GarminDB vs garminview diff suite. |
| Extensibility | New source = new adapter. New metric = new function in `analysis/metrics/`. New dashboard = new view + route. Core layers untouched. |

---

## 10. Build Phases

| Phase | Deliverable |
|---|---|
| 1 — Foundation | Project scaffold, SQLAlchemy models, Alembic migrations, DB engine factory (SQLite + MariaDB), `schema_version` tracking |
| 2 — Ingestion | All file adapters (JSON + FIT), all API adapters, orchestrator, `sync_log`, rate limiting, validation suite |
| 3 — Analysis Engine | Training load, sleep science, cardiovascular, composite scores, trend classifier, benchmarks, correlation engine |
| 4 — FastAPI | All route handlers, Pydantic schemas, SSE sync stream, admin config endpoints, OpenAPI docs |
| 5 — Vue.js | App scaffold, Pinia stores, chart components, all 13 dashboard views, admin section |
| 6 — Notebooks | 4 Marimo notebooks + shared utility module |
| 7 — Export & Polish | PDF/CSV/JSON/ZIP export, static HTML reports, notification config |
| 8 — Validation | GarminDB comparison suite, performance benchmarks, end-to-end tests |
