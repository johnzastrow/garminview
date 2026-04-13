# GarminView — Project TODO

**Last updated:** 2026-04-08

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

### Open work completion (2026-03-12)

- [x] Noise reduction — filter UnknownEnumValue from sync log; GARMINDB_LOG_LEVEL=WARNING
- [x] Garmin Connect API adapters — _run_api_adapters() with 10 adapters; credential UI in Admin
- [x] APScheduler SyncSchedule DB integration — loads cron jobs from DB; hot-reload on schedule update
- [x] Schema alignment migration (0005) — 5 missing tables created; httpx to main deps; Caddyfile route fix
- [x] CLAUDE.md update — MariaDB info, FIT patterns, column naming conventions
- [x] garmindb in Docker — garmindb>=1.1.0 in deps; HealthData volume writable
- [x] Docker local deploy v0.6.0 — stack running at localhost:8010 against MariaDB
- [x] Historical monitoring re-ingestion — 2012–2023 backfill run

### MFP Backfill (2026-03-12)

- [x] Migration 0007 — add source column to weight and body_composition
- [x] Tag Garmin weight/body_composition rows with source='garmin'
- [x] `backfill_mfp_to_main()` — cross-populate weight and body_composition from MFP
- [x] `POST /admin/backfill/mfp` endpoint with auto-trigger on upload
- [x] Admin UI "Backfill from MFP" button with counts
- [x] Version bump to v0.9.1

---

## Upcoming

- [ ] **Polar data import** — 26 staging tables for Polar Flow GDPR export (plan: `docs/plans/2026-04-08-polar-integration-plan.md`)
- [x] **HR Zones chart** — Age-adapted Karvonen zones, stacked bar on Daily Overview
- [x] **Data Management Tasks Panel** — Actionable items: sync gaps, data quality, manual entry reminders
- [x] **Actalog Review Workflow** — AI-processed workout review queue with write-back to Actalog API

### Actalog Review Workflow (2026-04-13)

- [x] Auto-parse workout notes after scheduled sync
- [x] Review queue UI with editable Markdown + preview toggle
- [x] Sortable/filterable queue with keyword search
- [x] Write-back to Actalog API (JWT auth, WOD/movement creation)
- [x] Retry push for approved-not-sent items
- [x] Consolidated Actalog screen with tabs (Workouts, Review, Analytics, Settings)
- [x] Parser and connection config moved from Admin to Actalog Settings tab
- [x] Version bump to v0.10.0

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
