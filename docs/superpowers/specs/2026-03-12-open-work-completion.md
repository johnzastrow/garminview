# GarminView — Open Work Completion Design

**Date:** 2026-03-12  
**Goal:** Complete all open TODO items and deploy locally via Docker connected to remote MariaDB.

---

## Scope

Six code items + one data operation + one deploy step:

1. APScheduler + SyncSchedule hot-reload
2. Garmin Connect API adapters (wire up `_run_api_adapters()`)
3. Model/DB schema alignment (Alembic migration)
4. Noise reduction (filter GarminDB log spam)
5. CLAUDE.md update
6. Historical monitoring re-ingestion (data op — run backfill command)
7. Docker build + local deploy against remote MariaDB

---

## 1. APScheduler + SyncSchedule Hot-Reload

**Files:** `backend/garminview/core/startup.py`, `backend/garminview/api/routes/admin.py`

On startup, `start_scheduler()` reads all enabled `SyncSchedule` rows from the DB and registers a `CronTrigger`-based APScheduler job for each. Job IDs follow the pattern `sync_{source}_{id}`.

When `PUT /admin/schedules/{id}` saves a change, it calls `reload_schedule(schedule_id, session)` from `startup.py`. That function:
- Removes the old job by ID (if it exists)
- If `enabled=True`, re-adds the job with a new `CronTrigger` from the updated `cron_expression`

The Garmin file-sync job calls `_run_garminview_sync()` (an async wrapper around the orchestrator). The Actalog job remains as-is. `SyncSchedule.source` values: `"garminview"` and `"actalog"`.

`stop_scheduler()` is unchanged.

---

## 2. Garmin Connect API Adapters

**Files:** `backend/garminview/core/config.py`, `backend/garminview/ingestion/orchestrator.py`

Credentials stored in `app_config` DB table (keys: `garmin_email`, `garmin_password`, `garmin_token_store`). Same pattern as Actalog.

`_run_api_adapters(start_date, end_date)` in `IngestionOrchestrator`:
1. Reads `garmin_email` and `garmin_password` from `app_config` via the session
2. If either is missing, logs a warning and returns
3. Instantiates `Garmin(email, password)`, calls `login()` with token caching in `app_config`
4. Runs each adapter: `HRVAdapter`, `TrainingReadinessAdapter`, `TrainingStatusAdapter`, `BodyBatteryAdapter`, `VO2MaxAdapter` (and others from `api_adapters/`)
5. Each adapter failure is caught independently — one failing adapter doesn't abort the rest

Admin UI: add `garmin_email` and `garmin_password` fields to the existing Config section in `Admin.vue`.

---

## 3. Model/DB Schema Alignment

**Files:** `backend/alembic/versions/<new_revision>.py`, `backend/garminview/models/*.py`

Read `docs/SCHEMA.md` to identify the 107 divergences. Generate a single Alembic revision with `ALTER TABLE ... RENAME COLUMN` statements for each divergence. Update the corresponding SQLAlchemy model `mapped_column` names and `__tablename__` references to match.

Dialect awareness: MariaDB supports `RENAME COLUMN` (MySQL 8.0+/MariaDB 10.5+); SQLite supports it from 3.25+. Both are fine.

---

## 4. Noise Reduction

**File:** `backend/garminview/api/routes/sync.py`

In `_run_sync()`, before calling `_broadcast("log", ...)` on GarminDB subprocess output, skip lines matching `"UnknownEnumValue"`. One conditional guard.

Also set `GARMINVIEW_LOG_LEVEL=WARNING` for the `garmindb_cli` subprocess via `env=` in `asyncio.create_subprocess_exec`.

---

## 5. CLAUDE.md Update

Add to `CLAUDE.md`:
- MariaDB connection: host, port, DB name (no credentials — those stay in `.env`)
- `uv run python tests/validation/compare.py` as the primary QA command
- `timestamp_16` resolution pattern for future FIT adapter work
- Note: never pass `--analyze` to `garmindb_cli.py` (was ~80% of sync time)

---

## 6. Historical Monitoring Re-ingestion

Data operation only — no code changes.

```bash
cd ~/Github/garminview/backend
uv run python tests/validation/run_garminview.py --start 2012-01-01 --end 2023-12-31
uv run python tests/validation/compare.py
```

Run after the schema alignment migration is applied so column names are correct.

---

## 7. Docker Build + Local Deploy

**GarminDB in container:** Add `garmindb` to `backend/pyproject.toml` dependencies. This installs `garmindb_cli.py` on the container PATH via the project venv so the scheduled sync can run the download step inside the container.

**Volume change:** In `docker-compose.yml`, change the HealthData mount from `:ro` to read-write so `garmindb_cli.py` can write downloaded files:

```yaml
- ${HEALTH_DATA_DIR:-~/HealthData}:/data/HealthData
```

The `.GarminDb` credentials mount remains `:ro`.

```bash
# Build images locally
docker build -t ghcr.io/johnzastrow/garminview-backend:local backend/
docker build -t ghcr.io/johnzastrow/garminview-frontend:local frontend/

# Set IMAGE_TAG=local in .env, then:
docker compose up -d
```

Verify: `curl http://localhost:8000/health/daily?days=7`

---

## Implementation Order

1. Noise reduction (trivial, independent)
2. Garmin API credentials + `_run_api_adapters()`
3. APScheduler hot-reload
4. Model/DB schema alignment (Alembic migration)
5. CLAUDE.md update
6. Tests pass: `uv run pytest -q`
7. Docker build + local deploy
8. Historical re-ingestion command
9. Validation: `uv run python tests/validation/compare.py`
