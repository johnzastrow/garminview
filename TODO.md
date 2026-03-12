# GarminView — Project TODO

**Last updated:** 2026-03-12

---

## Completed work

### Data pipeline fixes (2026-03-10)

- [x] Fixed `timestamp_16` resolution in `MonitoringFitAdapter` — was silently dropping ~80% of monitoring records
- [x] Removed `--analyze` from GarminDB CLI in sync (was ~80% of sync time)
- [x] Batch upserts (500-row batches instead of 1/row)
- [x] Date-range filtering in `DailySummaryAdapter`, `ActivityFitAdapter`, `ActivityJsonAdapter`
- [x] Garmin `-1` sentinel → NULL in `DailySummaryAdapter`, `SleepAdapter`, `RHRAdapter`
- [x] Dialect-aware upserts (MySQL vs SQLite)
- [x] Skip all-None non-PK rows in `_upsert_adapter()` — prevents NULL HR overwriting valid values in `monitoring_heart_rate`
- [x] `AnalysisEngine(session).run_all()` called after ingestion in `sync.py`
- [x] Dialect-aware batch upserts in `AnalysisEngine._compute_daily_derived()`

### Frontend dashboards (2026-03-10)

- [x] SleepDashboard.vue — duration trend, stages chart, sleep score
- [x] CardiovascularDashboard.vue — RHR, body battery max/min, HR range
- [x] WeightBodyComp.vue — weight, body fat %, muscle mass
- [x] ActivitySummary.vue — activity list table, distance/HR charts
- [x] RecoveryStress.vue — stress trend, body battery bands
- [x] RunningDashboard.vue — pace trend, distance, HR per run

### Max HR aging analysis (2026-03-10)

- [x] `MaxHRAgingYear` model + `max_hr_aging_year` table
- [x] `AnalysisEngine` extended with `MaxHRAgingAnalysis.run()`
- [x] `GET /training/max-hr-aging` API route
- [x] `MaxHRAgingDashboard.vue` — scatter+trend, annual p90, HR reserve, % age-predicted
- [x] `ScatterTrendChart.vue` chart component
- [x] Route registered at `/max-hr-aging`; nav item added

### MFP import (2026-03-10 – 2026-03-12)

- [x] `mfp_zip_parser.py` — standalone in-memory ZIP parser (no DB calls), handles `Nutrition-Summary-*.csv`, `Measurement-Summary-*.csv`, `Exercise-Summary-*.csv`
- [x] `MFPDailyNutrition`, `MFPFoodDiaryEntry`, `MFPMeasurement`, `MFPExercise` models
- [x] `MFPNutritionAdapter`, `MFPFoodDiaryAdapter`, `MFPMeasurementAdapter` file adapters (read from GarminDB-processed CSVs)
- [x] `POST /admin/upload/mfp` endpoint — accepts ZIP, parses in-memory, runs schema migration, bulk inserts
- [x] `_migrate_mfp_food_diary_columns()` — creates missing MFP tables, detects and recreates legacy GarminDB `mfp_measurements` schema
- [x] Admin.vue Uploads tab — file picker, progress spinner, 4-card result grid, error list
- [x] `NutritionDashboard.vue` — energy balance charts, macro breakdown
- [x] Tests: `test_mfp_zip_parser.py` (9 tests), `test_admin_upload.py` (6 tests)

### Infrastructure (2026-03-12)

- [x] Dependabot configured (`.github/dependabot.yml`) — weekly pip, npm, and GitHub Actions updates
- [x] `docs/SCHEMA.md` created — complete data dictionary for all ~50 tables, reconciled against live MariaDB with 107 divergences annotated
- [x] SSE reconnect + `triggerSync()` error handling in Admin.vue
- [x] Validation suite `compare.py` updated for MariaDB + expanded table map

---

## Open: High priority

### APScheduler integration

**File:** `backend/garminview/api/main.py`

`SyncSchedule` model and admin routes exist; APScheduler is not wired up.

Fix: In `create_app()`, start an APScheduler instance, load `sync_schedule` rows from DB, register jobs. On config update via admin API, hot-reload the schedule.

---

## Open: Medium priority

### Historical monitoring re-ingestion (2012–2023)

The `timestamp_16` fix means all historical monitoring data was stored with NULL `hr`. Re-ingestion backfills ~11 years of minute-level HR data.

```bash
cd ~/Github/garminview/backend
uv run python tests/validation/run_garminview.py --start 2012-01-01 --end 2023-12-31
```

Run validation suite after:

```bash
uv run python tests/validation/compare.py
```

### Python model / live DB alignment

`docs/SCHEMA.md` documents 107 column name divergences between the SQLAlchemy models and the live MariaDB schema (e.g., `heart_rate` vs `hr`, `avg_speed_ms` vs `avg_speed`). These should be reconciled via an Alembic migration so the models match the actual columns.

File: `backend/garminview/models/` + a new Alembic revision.

### CLAUDE.md update

Add to `CLAUDE.md`:
- MariaDB connection details
- `uv run python tests/validation/compare.py` as the QA command
- The `timestamp_16` resolution pattern for future FIT adapter work
- Note on `--analyze` flag being excluded from GarminDB CLI calls

### Lower-priority dashboards

- `LongTermTrends.vue` — connect to `/training/correlations/`
- `CorrelationExplorer.vue` — connect to `/training/correlations/`
- `AssessmentsGoals.vue` — connect to `/assessments/`
- `DataQuality.vue` — connect to `/admin/data-quality`
- `TrainingLoadDashboard.vue` — full PMC chart (ATL/CTL/TSB over time)

---

## Open: Low priority / future

### Actalog API integration

Pull workout session data (sets, reps, loads, RPE) from a self-hosted Actalog instance. Fill activity gaps where Garmin was not worn. Run cross-source correlations between strength load and Garmin recovery signals. See deleted detail in git history for full spec.

**New files required:**
- `backend/garminview/models/actalog.py`
- `backend/garminview/ingestion/api_adapters/actalog_client.py`
- `backend/garminview/ingestion/api_adapters/actalog_adapter.py`
- `backend/garminview/analysis/actalog_dedup.py`
- `backend/garminview/analysis/strength_metrics.py`
- `backend/garminview/api/routes/strength.py`
- `frontend/src/views/StrengthDashboard.vue`

### Garmin Connect API adapters

Routes returning empty results for `hrv_data`, `training_readiness`, `vo2max`, `race_predictions`, `lactate_threshold` — these require live API calls via `python-garminconnect`. Low priority until API auth is configured.

**File:** `backend/garminview/ingestion/orchestrator.py` `_run_api_adapters()` (currently a pass)

### Noise reduction

- Add `GARMINVIEW_LOG_LEVEL=WARNING` for `garmindb_cli` subprocess output
- Filter GarminDB `UnknownEnumValue_13` log lines from the Admin sync log display

---

## Verification commands

```bash
# Data pipeline
cd backend
uv run python tests/validation/compare.py --days 30   # all tables PASS

# Tests
uv run pytest -q                                      # all green

# Max HR aging
curl http://localhost:8000/training/max-hr-aging      # returns yearly rows

# MFP upload
# Upload a MFP export ZIP via Admin UI → Uploads tab

# Energy balance
curl http://localhost:8000/nutrition/energy-balance?days=30
```
