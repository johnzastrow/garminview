# GarminView — Project TODO

## Context

The garminview project is largely complete at the infrastructure level. The backend (FastAPI + SQLAlchemy + MariaDB), ingestion pipeline, analysis engine, and basic frontend scaffold all exist. Several gaps remain between scaffolded and working end-to-end.

---

## 1 — Data Pipeline Fixes (completed 2026-03-10)

- [x] Fixed `timestamp_16` resolution in `MonitoringFitAdapter`
- [x] Removed `--analyze` from GarminDB CLI in sync
- [x] Batch upserts (500-row batches)
- [x] Date-range filtering in `DailySummaryAdapter`, `ActivityFitAdapter`, `ActivityJsonAdapter`
- [x] Garmin `-1` sentinel → NULL in `DailySummaryAdapter`
- [x] Dialect-aware upserts (MySQL vs SQLite)
- [x] SSE reconnect + `triggerSync()` error handling in Admin.vue
- [x] Validation suite `compare.py` updated for MariaDB + expanded table map

---

## 2 — Open Bugs (completed 2026-03-10)

- [x] **2a** Null HR records polluting `monitoring_heart_rate` — skip all-None non-PK rows in `_upsert_adapter()`
- [x] **2b** Garmin `-1` sentinel applied to `sleep.py`, `rhr.py`
- [x] **2c** Monitoring HR timezone note in `compare.py`
- [x] **2d** Pandas date format warning in `compare.py`

---

## 3 — Frontend Dashboards (completed 2026-03-10)

- [x] SleepDashboard.vue — duration trend, stages chart, sleep score
- [x] CardiovascularDashboard.vue — RHR, body battery max/min, HR range
- [x] WeightBodyComp.vue — weight, body fat %, muscle mass
- [x] ActivitySummary.vue — activity list table, distance/HR charts
- [x] RecoveryStress.vue — stress trend, body battery bands
- [x] RunningDashboard.vue — pace trend, distance, HR per run

---

## 4 — Backend Gaps

### 4a. APScheduler integration
**Status:** `SyncSchedule` model and admin routes exist; APScheduler not wired up.
**File:** `backend/garminview/api/main.py`
**Fix:** In `create_app()`, start APScheduler, load `sync_schedule` rows, register jobs. Hot-reload on config update.

### 4b. CSV / JSON export
**Status:** Already implemented in `backend/garminview/api/routes/export.py`.

### 4c. Analysis engine not called after ingestion (completed 2026-03-10)
- [x] `AnalysisEngine(session).run_all()` called after `orch.run_incremental()` in `sync.py`

### 4d. API routes returning empty results for unstubbed endpoints
HRV, training readiness, VO2Max, race predictions — require API adapter runs via `python-garminconnect`. Low priority until API adapter configuration is verified.

---

## 5 — Max HR Aging Analysis (new 2026-03-10)

**Goal:** Quantify the change in maximum achievable heart rate over the full period of record (~2012–present) as a physiological aging signal.

**Background:** Max HR declines with age at roughly 1 bpm/year (Tanaka formula: `208 - 0.7 × age`). Tracking actual vs. age-predicted max HR over time provides a meaningful fitness longevity metric and can reveal whether training has preserved or accelerated the expected decline.

### 5a. Data extraction

**Source columns:** `activities.max_hr`, `activities.start_time`, `activities.sport`, `activities.type`

**Filter criteria for valid max-effort readings:**
- Exclude rest/walk/yoga/strength activities (these produce submaximal HR)
- Keep: running, cycling, trail running, swimming, HIIT, Nordic skiing
- Minimum duration: `elapsed_time_s > 600` (10 min — avoid warm-up-only sessions)
- Minimum HR threshold: only include sessions where `max_hr > 130` (discard sensor noise/resting artefacts)

### 5b. Metrics to compute

| Metric | Definition | Rationale |
|--------|-----------|-----------|
| `annual_peak_hr` | Max `max_hr` in a calendar year | Absolute ceiling; sensitive to single hard efforts |
| `annual_p95_hr` | 95th percentile of `max_hr` per year | More robust; ignores rare extreme efforts |
| `annual_p90_hr` | 90th percentile per year | Stable long-term trend line |
| `rolling_90d_peak` | Rolling 90-day peak `max_hr` | Shows current fitness vs. historical |
| `age_predicted_max` | `208 - 0.7 × age_at_date` (Tanaka) | Personalised benchmark |
| `hr_reserve` | `max_hr_in_period - avg_rhr_in_period` | Training range; combines both ends of the HR spectrum |
| `decline_rate_bpm_per_year` | Linear regression slope on `annual_p90_hr` vs year | Quantify actual vs. expected 1 bpm/year decline |
| `pct_age_predicted` | `annual_p90_hr / age_predicted_max × 100` | Normalised fitness score; values >100 = above-average preservation |

### 5c. Analysis engine implementation

**File:** `backend/garminview/analysis/max_hr_aging.py` (new)

Inputs needed:
- User date of birth from `user_profile` DB table (or `app_config` key `dob`)
- All aerobic activities with `max_hr` not null

Steps:
1. Load activities, apply sport/duration/HR filters
2. Group by year, compute `annual_peak`, `p95`, `p90`
3. Compute `age_predicted_max` per date using Tanaka formula
4. Fit linear regression on `p90` vs year → `decline_rate`
5. Compute `hr_reserve` per year (join with `resting_heart_rate` annual averages)
6. Write results to `max_hr_aging` table (new, one row per year)

**New model** `MaxHRAgingYear` in `backend/garminview/models/derived.py`:
```
year: int (PK)
annual_peak_hr: int | None
annual_p95_hr: float | None
annual_p90_hr: float | None
age_predicted_max: float | None
hr_reserve: float | None
pct_age_predicted: float | None
decline_rate_bpm_per_year: float | None   # same value each row (global fit)
```

**New API route** `GET /training/max-hr-aging` → returns the table.

### 5d. Frontend: MaxHRAgingDashboard.vue (new view)

**Charts:**
1. **Scatter + trend** — All individual workout `max_hr` values vs. date (grey dots), with Tanaka predicted line (red dashed) and rolling `p90` trend (blue line). Shows the "ceiling" converging toward the predicted line over decades.
2. **Annual box plot** — Per-year distribution of workout max HR (min/p25/median/p75/peak). Reveals how the whole distribution shifts, not just the peak.
3. **HR Reserve trend** — `max_hr - rhr` per year. A stable or rising reserve means RHR is dropping as fast as max HR, indicating good aerobic adaptation.
4. **% of Age-Predicted** — Bar or line chart of `pct_age_predicted` per year. Horizontal reference line at 100%. Years above 100 = measured above Tanaka prediction.

**Metric cards:** current `annual_p90`, age-predicted max, `pct_age_predicted`, `decline_rate_bpm_per_year`.

**Route:** Add to `frontend/src/router/index.ts` as `/training/max-hr-aging`.

### 5e. Scatter plot component

The scatter+trend chart requires a new chart component that doesn't exist yet:

**File:** `frontend/src/components/charts/ScatterTrendChart.vue`

Accepts:
```typescript
interface ScatterPoint { date: string; value: number; label?: string }
interface TrendLine { name: string; data: [string, number][]; color: string; dashed?: boolean }
props: { scatter: ScatterPoint[]; trends: TrendLine[]; yAxisLabel?: string }
```

Uses ECharts `ScatterChart` + `LineChart` on the same grid.

### 5f. Status: ✅ COMPLETE (2026-03-10)
All backend and frontend components built. Route registered at `/max-hr-aging`. Nav item added.

### 5g. Data requirement

Workout scatter data will only be complete after the historical monitoring re-ingestion (Section 6a below) is done. The `activities` table should already be fully populated from `ActivityFitAdapter` — no re-ingestion needed specifically for this analysis.

The user's DOB must be configured in `app_config` (`key = "dob"`, `value = "YYYY-MM-DD"`) for the Tanaka formula to work. Add a config field in the Admin UI config tab.

---

## 6 — Infrastructure

### 6a. Re-run monitoring ingestion for historical data (2012–2023)
**Command:** `uv run python tests/validation/run_garminview.py --start 2012-01-01 --end 2023-12-31`
The `timestamp_16` fix means all historical monitoring data was stored with NULL hr. This re-ingestion will backfill ~11 years of data.

### 6b. Run full validation suite after backfill
**Command:** `uv run python tests/validation/compare.py`

### 6c. pytest suite health check
**Command:** `uv run pytest`

### 6d. CLAUDE.md update
- MariaDB connection details
- `uv run python tests/validation/compare.py` as the QA command
- The `timestamp_16` resolution pattern for future FIT adapter work

---

## 7 — Polish

- [x] Filter GarminDB `UnknownEnumValue_13` log lines from Admin sync log display
- Admin.vue: split into sub-tabs (already done — Sync/Schedules/Config/Logs tabs exist)
- Add `GARMINVIEW_LOG_LEVEL=WARNING` for garmindb_cli subprocess output (reduce noise)
- Lower-priority dashboards: LongTermTrends.vue, CorrelationExplorer.vue, AssessmentsGoals.vue, DataQuality.vue

---

## 8 — MyFitnessPal Import & Correlation

**Goal:** Ingest historical MFP data exports, fill gaps in Garmin nutrition/weight data, and run cross-source correlations between nutrition and Garmin health/performance metrics.

MFP is already planned in `REQUIREMENTS.md` as a data source. This section covers the full implementation path from export file parsing through to correlation dashboards.

### 8a. MFP Export Format

MyFitnessPal provides data exports via **Settings → Export Data** (sends a ZIP by email). The ZIP contains CSV files:

| File | Contents |
|------|----------|
| `Nutrition Summary.csv` | Daily totals: date, calories, carbs_g, fat_g, protein_g, sodium_mg, sugar_g, fiber_g, cholesterol_mg |
| `Food Diary.csv` | Per-meal entries: date, meal (Breakfast/Lunch/Dinner/Snacks), food name, calories, macros |
| `Exercise Entries.csv` | Manual cardio/strength log: date, exercise name, calories_burned, duration_min |
| `Measurements.csv` | Body measurements: date, measurement_name (Weight, Body Fat, etc.), value, unit |

The `Nutrition Summary.csv` is the primary import target; the others are secondary enrichment.

MFP date format is `YYYY-MM-DD`. Calories column header varies slightly across export versions — the adapter must handle both `"Calories"` and `"Calories Consumed"`.

### 8b. New DB Models

**File:** `backend/garminview/models/nutrition.py` (new)

```
MFPDailyNutrition        — one row per calendar date
  date: Date (PK)
  calories_in: int | None
  carbs_g: float | None
  fat_g: float | None
  protein_g: float | None
  sodium_mg: float | None
  sugar_g: float | None
  fiber_g: float | None
  cholesterol_mg: float | None
  logged_meals: int | None     # count of distinct meal slots logged (0–4)
  source: str                  # "mfp_export"

MFPFoodDiaryEntry        — one row per food item logged
  id: int (PK, autoincrement)
  date: Date (index)
  meal: str                    # Breakfast / Lunch / Dinner / Snacks
  food_name: str
  calories: int | None
  carbs_g: float | None
  fat_g: float | None
  protein_g: float | None

MFPMeasurement           — body measurements from MFP (weight, body fat, etc.)
  date: Date (index)
  name: str                    # "Weight", "Body Fat", "Neck", "Waist", ...
  value: float
  unit: str
  -- composite PK: (date, name)
```

Add to `backend/garminview/models/__init__.py`.

### 8c. File Adapters

**File:** `backend/garminview/ingestion/file_adapters/mfp_nutrition.py` (new)

```python
class MFPNutritionAdapter(BaseAdapter):
    """Parses MFP Nutrition Summary.csv export → mfp_daily_nutrition."""
    target_table() → "mfp_daily_nutrition"

class MFPFoodDiaryAdapter(BaseAdapter):
    """Parses MFP Food Diary.csv export → mfp_food_diary."""
    target_table() → "mfp_food_diary"

class MFPMeasurementAdapter(BaseAdapter):
    """Parses MFP Measurements.csv export → mfp_measurements."""
    target_table() → "mfp_measurements"
```

Key parsing notes:
- Strip commas from numeric fields (MFP formats `1,234` calories with locale separators)
- `logged_meals` = count of distinct meal values in the food diary for that date (indicates completeness)
- MFP weight unit may be lbs — convert to kg on import (`× 0.453592`)
- Handle missing/blank rows (days with no logging are absent, not zero-calorie rows)

**Registration:** Add all three adapters to `IngestionOrchestrator._run_file_adapters()` gated behind a config flag `mfp_data_dir` being set (so the adapters are skipped if MFP data is not configured).

### 8d. Config & Admin UI

Add to `app_config` table (admin-editable):
- `mfp_data_dir` — path to the directory containing unzipped MFP export files

Add MFP import status card to the Admin sync panel showing:
- Date range of imported nutrition data
- Total days with complete logging vs. partial vs. missing

### 8e. Gap Filling Logic

**File:** `backend/garminview/analysis/mfp_gap_fill.py` (new)

Rules for merging MFP data into Garmin tables:

| Gap type | Garmin source | MFP source | Merge rule |
|----------|--------------|------------|------------|
| Weight missing in `weight` table | `weight.weight_kg` is NULL for date | `mfp_measurements` where `name = "Weight"` | Insert MFP value with `source = "mfp"` |
| Body fat missing in `body_composition` | `body_composition.fat_pct` is NULL | `mfp_measurements` where `name = "Body Fat"` | Insert with `source = "mfp"` |
| Calories burned | `daily_summary.calories_total` (Garmin, authoritative) | `mfp_exercise.calories_burned` (less accurate) | Prefer Garmin; log discrepancy if >200 kcal |

Gap fill is non-destructive: never overwrites existing Garmin values. Results recorded in `data_provenance` table with `source = "mfp_gap_fill"`.

### 8f. Derived Metrics

**File:** `backend/garminview/analysis/energy_balance.py` (new)

Add to `daily_derived` table (new columns or separate table `mfp_daily_derived`):

| Column | Formula |
|--------|---------|
| `calories_in` | From `mfp_daily_nutrition.calories_in` |
| `calories_out` | From `daily_summary.calories_total` (Garmin active + BMR) |
| `energy_balance` | `calories_in - calories_out` (negative = deficit) |
| `protein_per_kg` | `mfp.protein_g / user_weight_kg` — adequacy ratio |
| `carb_load_index` | `mfp.carbs_g / 300` — normalised (300g = reference carb day) |

Rolling windows (7-day, 30-day):
- `rolling_7d_avg_calories_in`
- `rolling_7d_avg_energy_balance`
- `cumulative_energy_balance_7d` — predictive of weight change (3500 kcal ≈ 0.45 kg fat)

### 8g. Correlation Analysis

**File:** `backend/garminview/analysis/nutrition_correlations.py` (new)

Cross-source correlations to compute and store in `correlation_results` table:

| Correlation | MFP signal | Garmin signal | Lag | Hypothesis |
|-------------|-----------|--------------|-----|------------|
| Protein → recovery | `protein_per_kg` (day N) | `body_battery_max` (day N+1) | +1d | Higher protein → better next-day recovery |
| Carb load → training HR | `carbs_g` (day N) | `avg_hr` in activities on day N+1 | +1d | More carbs → lower HR at same effort (better fuelled) |
| Caloric deficit → resting HR | `energy_balance` 7d avg | `resting_heart_rate.rhr` | 0d | Large deficit → elevated RHR (physiological stress) |
| Sodium → sleep | `sodium_mg` (day N) | `sleep.score` (night of day N) | 0d | High sodium → worse sleep quality |
| Energy balance → weight delta | `cumulative_energy_balance_7d` | `weight_kg` change over same 7d | 0d | 3500 kcal deficit ≈ 0.45 kg loss |
| Fiber → sleep | `fiber_g` | `sleep.total_sleep_min` | +1d | Dietary fiber → improved sleep duration |

Use Pearson r for linear correlations; compute p-value and store both. Flag correlations with `|r| > 0.3` and `p < 0.05` as notable.

### 8h. API Routes

**File:** `backend/garminview/api/routes/nutrition.py` (new), registered at `/nutrition`

```
GET /nutrition/daily          → list[MFPDailyNutritionResponse]   (date range)
GET /nutrition/energy-balance → list[EnergyBalanceResponse]       (daily in/out/balance)
GET /nutrition/correlations   → list[NutritionCorrelationResponse] (notable correlations)
GET /nutrition/completeness   → summary of logging coverage       (% days logged)
```

### 8i. Frontend: NutritionDashboard.vue (new view)

**Route:** `/nutrition`

**Metric cards:**
- Today's calories in / out / balance
- 7-day average protein (g and per-kg)
- % of days fully logged (logging completeness)

**Charts:**
1. **Energy balance** — Dual-axis: calories in (bar, blue) and calories out (line, orange) per day. Area fill below shows deficit/surplus clearly.
2. **Macro breakdown** — Stacked bar: protein / carbs / fat per day as % of calories. Reference lines at 30/40/30 split.
3. **Weight vs. cumulative energy balance** — Dual-axis scatter: 30-day rolling energy balance (left) vs. weight (right). Visualises whether caloric math matches actual weight change.
4. **Nutrition → Recovery correlation** — Scatter: protein_per_kg (x) vs. next-day body battery max (y). Correlation coefficient displayed.

**Import panel** (in Admin.vue or as a section of NutritionDashboard):
- Shows: last import date, days of data, logging completeness %
- Button: "Re-import MFP Data" → triggers adapter run via existing sync infrastructure

### 8j. Data Quality & Completeness Reporting

Track and surface MFP logging completeness alongside Garmin data quality:
- Days with no MFP log at all (no entry) vs. partial log (some meals) vs. complete log (all 4 meals)
- Weeks where caloric balance predicts weight change but weight data is missing → flag as "unverifiable balance window"
- `data_quality_flags` table: flag days where `energy_balance > 1000` or `< -1500` as physiologically implausible (likely logging error)

### 8j. Status: ✅ COMPLETE (2026-03-10)
Models, adapters, energy balance API, and NutritionDashboard built. Route registered at `/nutrition`.

### 8k. New Alembic Migration

New tables require a migration: `mfp_daily_nutrition`, `mfp_food_diary`, `mfp_measurements`, and new columns on `daily_derived`.

**Command:** `uv run alembic revision --autogenerate -m "add mfp nutrition tables"`

---

## 9 — Actalog API Integration

**Goal:** Pull workout session data from a self-hosted or remote Actalog instance via its API, use it to fill activity gaps where Garmin was not worn or recording, and enrich existing Garmin activities with exercise-level detail (sets, reps, loads) that Garmin FIT files do not capture.

Actalog is already in `REQUIREMENTS.md` as a Phase 2 data source (REQ-MS-020 through REQ-MS-023). This section designs the full implementation.

### 9a. What Actalog provides that Garmin does not

| Data type | Garmin captures | Actalog adds |
|-----------|----------------|-------------|
| Workout sessions | HR, GPS, elapsed time | Session title, notes, RPE (1–10) |
| Strength exercises | Nothing (FIT has no set/rep fields) | Exercise name, sets × reps × weight_kg |
| Progressive overload | Not tracked | Historical load per exercise (e.g., squat 1RM progression) |
| Training plans | Not tracked | Planned vs. actual session, compliance % |
| Sessions without device | Missing from Garmin entirely | Gap-fills unrecorded workouts |

### 9b. API Client

**File:** `backend/garminview/ingestion/api_adapters/actalog_client.py` (new)

Config keys (in `app_config` table):
- `actalog_base_url` — e.g. `https://actalog.yourdomain.com`
- `actalog_api_key` — bearer token or API key
- `actalog_last_sync` — ISO timestamp of last successful pull (auto-updated)

The client should:
- Authenticate via `Authorization: Bearer <api_key>` header
- Use incremental sync: fetch sessions modified since `actalog_last_sync`
- Handle pagination (`?page=N&per_page=100` or cursor-based — inspect actual API)
- Use `tenacity` with exponential backoff on 429/503 (same pattern as Garmin client)
- On first run: fetch all historical sessions back to `actalog_start_date` config key

Assumed endpoint structure (verify against actual Actalog API):
```
GET /api/sessions?since=<iso>&page=<n>    → list of workout sessions
GET /api/sessions/<id>/exercises          → exercises within a session
GET /api/exercises                        → exercise catalogue (name → category)
```

### 9c. New DB Models

**File:** `backend/garminview/models/actalog.py` (new)

```
ActalogSession          — one row per workout session
  session_id: str (PK, Actalog's UUID)
  started_at: DateTime (UTC, index)
  ended_at: DateTime | None
  title: str | None
  notes: str | None
  rpe: int | None            # 1–10 perceived exertion
  session_type: str | None   # "strength" / "cardio" / "mobility" / etc.
  garmin_activity_id: int | None   # FK → activities.activity_id if matched
  source: str = "actalog"

ActalogSet              — one row per set within a session
  id: int (PK, autoincrement)
  session_id: str (FK → actalog_sessions)
  exercise_name: str
  exercise_category: str | None   # "compound" / "isolation" / "cardio" / etc.
  set_index: int
  reps: int | None
  weight_kg: float | None
  duration_s: int | None          # for timed sets (planks, etc.)
  rpe_set: int | None             # per-set RPE if tracked
```

Add to `backend/garminview/models/__init__.py`.

### 9d. API Adapter

**File:** `backend/garminview/ingestion/api_adapters/actalog_adapter.py` (new)

```python
class ActalogAdapter:
    """Pulls sessions + sets from Actalog API → actalog_sessions + actalog_sets."""

    def run_incremental(self, session: Session) -> int:
        """Fetch sessions since last sync, upsert, return record count."""
```

This adapter is API-based (not file-based), so it does not inherit `BaseAdapter`. Register it in `IngestionOrchestrator._run_api_adapters()`, gated on `actalog_base_url` being configured.

After fetching, call `_match_garmin_activities()` to attempt deduplication (see 9e).

### 9e. Deduplication with Garmin

**File:** `backend/garminview/analysis/actalog_dedup.py` (new)

Matching strategy:
1. **Exact time match**: if `actalog_session.started_at` is within ±5 minutes of `activity.start_time` → high-confidence match; set `garmin_activity_id`
2. **Same-day + type match**: if same calendar date and both are `session_type = "running"` / `sport = "running"` → medium confidence; flag for review
3. **No match**: session exists only in Actalog (Garmin watch was not worn or recording failed) → treat as a gap-fill activity; insert a synthetic row into the `activities` table with `source = "actalog"` and all fields populated from Actalog session data

Deduplication results are stored in `data_provenance` with:
- `source_a = "garmin"`, `source_b = "actalog"`, `match_confidence = "high" | "medium" | "none"`

### 9f. Strength-Specific Derived Metrics

**File:** `backend/garminview/analysis/strength_metrics.py` (new)

Per-session metrics computed from `actalog_sets`:

| Metric | Formula |
|--------|---------|
| `total_volume_kg` | Σ (reps × weight_kg) across all sets in session |
| `session_intensity` | weighted avg weight_kg (by reps) |
| `top_set_weight_kg` | max weight_kg in session per exercise |

Per-exercise longitudinal metrics (stored in `actalog_exercise_derived`):
| Metric | Formula |
|--------|---------|
| `estimated_1rm` | Epley formula: `weight × (1 + reps/30)` for top set |
| `volume_trend_4w` | 4-week rolling total volume per exercise |
| `frequency_per_week` | sessions containing this exercise per 7 days |

Weekly aggregate (written to `weekly_derived` or a new `weekly_strength` table):
- `total_weekly_volume_kg` — all exercises, all sessions
- `strength_sessions_count`
- `avg_session_rpe`

### 9g. Correlation Analysis

**File:** `backend/garminview/analysis/strength_correlations.py` (new)

Cross-source correlations between Actalog strength load and Garmin recovery signals:

| Correlation | Actalog signal | Garmin signal | Lag | Hypothesis |
|-------------|---------------|--------------|-----|------------|
| Volume → recovery | `total_volume_kg` on day N | `body_battery_max` day N+1 | +1d | High volume → depressed recovery |
| Volume → RHR | `weekly_volume_kg` | `rhr` next 3 days | +1–3d | Accumulated fatigue raises RHR |
| RPE → sleep | `avg_session_rpe` | `sleep.score` night of training | 0d | High-RPE sessions → worse sleep |
| Strength load → HRV | `total_volume_kg` | HRV 7-day avg (next day) | +1d | Heavy load → HRV suppression |
| Progressive overload → fitness | `estimated_1rm` trend | `ctl` (training load from PMC) | 0d | 1RM improvements correlate with CTL growth |

### 9h. API Routes

**File:** `backend/garminview/api/routes/strength.py` (new), registered at `/strength`

```
GET /strength/sessions         → list[ActalogSessionResponse]       (date range)
GET /strength/sessions/<id>    → ActalogSessionDetailResponse       (with sets)
GET /strength/volume           → list[WeeklyVolumeResponse]         (weekly tonnage)
GET /strength/exercises/<name> → ExerciseProgressionResponse        (1RM trend, volume trend)
GET /strength/correlations     → list[StrengthCorrelationResponse]  (notable correlations)
```

### 9i. Frontend: StrengthDashboard.vue (new view)

**Route:** `/strength`

**Metric cards:**
- Weekly volume this week (kg)
- Sessions this week
- Average session RPE this week
- Latest estimated 1RM for a configurable key lift (default: "Squat" or first compound lift found)

**Charts:**
1. **Weekly volume trend** — Bar chart of `total_weekly_volume_kg` over time. Color-code by session type (strength/cardio/mobility).
2. **Exercise progression (1RM)** — Multi-series line chart of `estimated_1rm` for top 3–5 exercises over the period of record. Requires a filter/selector component to choose exercises.
3. **Volume vs. Recovery** — Dual-axis: weekly volume (bar) vs. next-day body battery avg (line). Visualises recovery debt from heavy weeks.
4. **Session list** — Table of recent sessions: date, title, RPE, total volume, Garmin match status (matched / gap-fill / no device).

### 9j. Admin: Actalog Sync Status

Add to Admin.vue sync panel (alongside Garmin and MFP status):
- Last Actalog sync timestamp
- Sessions pulled in last sync
- Unmatched sessions count (gap-fills)
- Link to configure `actalog_base_url` in Config tab

### 9k. Migration

New tables: `actalog_sessions`, `actalog_sets`, `actalog_exercise_derived`.

**Command:** `uv run alembic revision --autogenerate -m "add actalog tables"`

---

## Critical Files

| File | Area |
|------|------|
| `backend/garminview/analysis/max_hr_aging.py` | New — max HR aging analysis engine |
| `backend/garminview/models/derived.py` | Add `MaxHRAgingYear` model |
| `backend/garminview/api/routes/training.py` | Add `/training/max-hr-aging` endpoint |
| `frontend/src/views/MaxHRAgingDashboard.vue` | New dashboard view |
| `frontend/src/components/charts/ScatterTrendChart.vue` | New scatter+trend chart |
| `frontend/src/router/index.ts` | Register new route |
| `backend/garminview/models/nutrition.py` | New — MFP nutrition models |
| `backend/garminview/ingestion/file_adapters/mfp_nutrition.py` | New — MFP CSV adapters |
| `backend/garminview/analysis/energy_balance.py` | New — caloric balance derived metrics |
| `backend/garminview/analysis/nutrition_correlations.py` | New — cross-source correlations |
| `backend/garminview/analysis/mfp_gap_fill.py` | New — weight/body fat gap fill logic |
| `backend/garminview/api/routes/nutrition.py` | New — nutrition API endpoints |
| `frontend/src/views/NutritionDashboard.vue` | New nutrition dashboard view |
| `backend/garminview/models/actalog.py` | New — Actalog session + set models |
| `backend/garminview/ingestion/api_adapters/actalog_client.py` | New — Actalog HTTP client |
| `backend/garminview/ingestion/api_adapters/actalog_adapter.py` | New — Actalog incremental sync |
| `backend/garminview/analysis/actalog_dedup.py` | New — Garmin↔Actalog deduplication |
| `backend/garminview/analysis/strength_metrics.py` | New — volume, 1RM, frequency derived metrics |
| `backend/garminview/analysis/strength_correlations.py` | New — strength load vs. recovery correlations |
| `backend/garminview/api/routes/strength.py` | New — strength API endpoints |
| `frontend/src/views/StrengthDashboard.vue` | New strength dashboard view |
| `backend/garminview/ingestion/orchestrator.py` | Register MFP + Actalog adapters (gated on config) |
| `backend/garminview/api/routes/sync.py` | Analysis engine trigger |
| `backend/tests/validation/compare.py` | Timezone fix, pandas warning |

---

## Verification

- **Max HR analysis:** `curl http://localhost:8000/training/max-hr-aging` → returns yearly rows with `annual_p90_hr`, `age_predicted_max`, `pct_age_predicted`
- **MFP import:** Place `Nutrition Summary.csv` in `mfp_data_dir`, run sync → `curl http://localhost:8000/nutrition/daily?start=2020-01-01&end=2020-01-31` returns rows
- **Energy balance:** `curl http://localhost:8000/nutrition/energy-balance?days=30` → daily in/out/balance
- **Correlation:** `curl http://localhost:8000/nutrition/correlations` → returns flagged notable correlations with r and p-value
- **Data pipeline:** `uv run python tests/validation/compare.py --days 30` → all PASS
- **Backend:** `uv run pytest` → all green
- **Frontend:** Open NutritionDashboard, verify energy balance chart renders with in/out bars and weight overlay
- **Actalog sync:** Configure `actalog_base_url` + `actalog_api_key`, trigger sync → `curl http://localhost:8000/strength/sessions` returns sessions
- **Dedup:** After sync, `actalog_sessions` rows with Garmin-matched activities have `garmin_activity_id` set; unmatched appear as gap-fills in `activities` with `source = "actalog"`
- **Strength metrics:** `curl http://localhost:8000/strength/volume` → weekly tonnage rows; `curl http://localhost:8000/strength/exercises/Squat` → 1RM progression
- **Frontend:** Open StrengthDashboard, verify volume trend and 1RM progression charts render
