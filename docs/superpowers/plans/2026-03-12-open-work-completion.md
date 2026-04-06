# GarminView Open Work Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all open TODO items (noise reduction, Garmin API adapters, APScheduler hot-reload, schema migration, GarminDB in Docker) and deploy locally against remote MariaDB.

**Architecture:** Each task is self-contained. Execution order matters: Tasks 1–6 are code changes committed incrementally; Task 7 adds `garmindb` to the Python project + changes docker-compose; Task 8 bumps the version and builds/deploys Docker images. The historical re-ingestion (Task 9) is a data operation run after deployment.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, APScheduler 3.x, garminconnect, garmindb, Vue.js 3, Docker / docker compose, MariaDB (remote host)

---

## File Map

| File | Change |
|------|--------|
| `backend/garminview/api/routes/sync.py` | Filter `UnknownEnumValue` lines; pass `env=` to suppress garmindb log noise |
| `backend/garminview/ingestion/orchestrator.py` | Implement `_run_api_adapters()` |
| `backend/garminview/core/startup.py` | Load `SyncSchedule` rows on startup; add `reload_schedule()` |
| `backend/garminview/api/routes/admin.py` | Call `reload_schedule()` from `PUT /admin/schedules/{id}` |
| `frontend/src/views/Admin.vue` | Add Garmin credentials fields to Config tab |
| `backend/alembic/versions/<new>.py` | Column-rename migration for remaining model/DB divergences |
| `backend/pyproject.toml` | Add `garmindb` dependency, bump version to 0.6.0 |
| `backend/uv.lock` | Auto-updated by `uv lock` |
| `docker-compose.yml` | Remove `:ro` from HealthData volume mount |
| `CLAUDE.md` | MariaDB connection info, QA commands, FIT adapter notes |

---

## Task 1: Noise Reduction in sync.py

**Files:**
- Modify: `backend/garminview/api/routes/sync.py`

- [ ] **Step 1: Filter UnknownEnumValue lines and suppress garmindb log noise**

In `_run_sync()`, find the GarminDB subprocess block. Make two changes:
1. Add `env=` to the subprocess call that sets `GARMINDB_LOG_LEVEL=WARNING`
2. Add a `continue` guard before `_broadcast` for lines containing `UnknownEnumValue`

Replace the subprocess block:

```python
# BEFORE:
            proc = await asyncio.create_subprocess_exec(
                garmindb_cli,
                "--all", "--download", "--import", "--latest",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for raw in proc.stdout:
                _broadcast("log", raw.decode().rstrip())

# AFTER:
            import os
            proc = await asyncio.create_subprocess_exec(
                garmindb_cli,
                "--all", "--download", "--import", "--latest",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "GARMINDB_LOG_LEVEL": "WARNING"},
            )
            async for raw in proc.stdout:
                line = raw.decode().rstrip()
                if "UnknownEnumValue" in line:
                    continue
                _broadcast("log", line)
```

- [ ] **Step 2: Commit**

```bash
cd /home/jcz/Github/garminview
git add backend/garminview/api/routes/sync.py
git commit -m "fix: suppress UnknownEnumValue log spam from garmindb subprocess"
```

---

## Task 2: Garmin Connect API Credentials + _run_api_adapters()

**Files:**
- Modify: `backend/garminview/ingestion/orchestrator.py`
- Modify: `frontend/src/views/Admin.vue`

- [ ] **Step 1: Implement _run_api_adapters() in orchestrator.py**

Locate `_run_api_adapters` at the bottom of the file (currently `pass`). Replace the entire method body:

```python
    def _run_api_adapters(self, start_date: date, end_date: date) -> None:
        from garminview.models.config import AppConfig

        def _cfg(key: str) -> str | None:
            row = self._session.get(AppConfig, key)
            return row.value if row else None

        email = _cfg("garmin_email")
        password = _cfg("garmin_password")
        if not email or not password:
            log.warning("garmin_api_skipped",
                        reason="garmin_email/garmin_password not set in app_config")
            return

        try:
            from garminconnect import Garmin
            client = Garmin(email, password)
            client.login()
        except Exception as exc:
            log.error("garmin_login_failed", error=str(exc))
            return

        from garminview.ingestion.api_adapters.hrv import HRVAdapter
        from garminview.ingestion.api_adapters.training import (
            TrainingReadinessAdapter, TrainingStatusAdapter,
        )
        from garminview.ingestion.api_adapters.body import (
            VO2MaxAdapter, BodyCompositionAdapter, BloodPressureAdapter,
            PersonalRecordsAdapter, GearAdapter,
        )
        from garminview.ingestion.api_adapters.performance import (
            RacePredictionsAdapter, LactateThresholdAdapter,
        )

        api_adapters = [
            HRVAdapter(client),
            TrainingReadinessAdapter(client),
            TrainingStatusAdapter(client),
            VO2MaxAdapter(client),
            BodyCompositionAdapter(client),
            BloodPressureAdapter(client),
            PersonalRecordsAdapter(client),
            GearAdapter(client),
            RacePredictionsAdapter(client),
            LactateThresholdAdapter(client),
        ]

        for adapter in api_adapters:
            sync_log = SyncLogger(self._session, adapter.source_name(),
                                  "incremental", start_date, end_date)
            try:
                count = self._upsert_adapter(adapter, start_date, end_date)
                sync_log.increment(count)
                sync_log.success()
            except Exception as exc:
                log.error("api_adapter_failed",
                          source=adapter.source_name(), error=str(exc))
                sync_log.fail(str(exc))
```

- [ ] **Step 2: Add Garmin credential fields to Admin.vue**

Open `frontend/src/views/Admin.vue`. Find the Config tab section where `app_config` keys are edited (look for existing `actalog_` config rows). Add immediately after the last `actalog_` row:

```html
<!-- Garmin Connect API credentials -->
<tr>
  <td class="cfg-key">garmin_email</td>
  <td>
    <input v-model="cfgDraft['garmin_email']" class="cfg-input" type="email"
           placeholder="your@email.com" />
  </td>
  <td><button class="cfg-save" @click="saveConfig('garmin_email')">Save</button></td>
</tr>
<tr>
  <td class="cfg-key">garmin_password</td>
  <td>
    <input v-model="cfgDraft['garmin_password']" class="cfg-input" type="password"
           placeholder="••••••••" />
  </td>
  <td><button class="cfg-save" @click="saveConfig('garmin_password')">Save</button></td>
</tr>
```

- [ ] **Step 3: Verify the import compiles**

```bash
cd /home/jcz/Github/garminview/backend
uv run python -c "from garminview.ingestion.orchestrator import IngestionOrchestrator; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd /home/jcz/Github/garminview
git add backend/garminview/ingestion/orchestrator.py frontend/src/views/Admin.vue
git commit -m "feat: implement Garmin Connect API adapters and credential config UI"
```

---

## Task 3: APScheduler SyncSchedule DB Integration + Hot-Reload

**Files:**
- Modify: `backend/garminview/core/startup.py`
- Modify: `backend/garminview/api/routes/admin.py`

- [ ] **Step 1: Rewrite startup.py**

Replace the entire content of `backend/garminview/core/startup.py` with:

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from garminview.models.sync import SchemaVersion
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import logging

CURRENT_SCHEMA_VERSION = "20260307_001"


def check_schema_version(session: Session) -> None:
    latest = (session.query(SchemaVersion)
              .order_by(SchemaVersion.applied_at.desc()).first())
    if latest and latest.version != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Schema version mismatch: DB has {latest.version}, "
            f"code expects {CURRENT_SCHEMA_VERSION}. Run: alembic upgrade head"
        )


def record_migration(session: Session, version: str, description: str) -> None:
    session.add(SchemaVersion(
        version=version,
        description=description,
        applied_at=datetime.now(timezone.utc),
        applied_by="alembic",
    ))
    session.commit()


_scheduler: AsyncIOScheduler | None = None
_session_factory = None
_log = logging.getLogger(__name__)


def _set_actalog_cfg(session, key: str, value: str) -> None:
    from garminview.models.config import AppConfig
    row = session.get(AppConfig, key)
    if row is None:
        row = AppConfig(key=key, category="actalog", data_type="string")
        session.add(row)
    row.value = value


async def _actalog_job():
    with _session_factory() as session:
        from garminview.models.config import AppConfig

        def cfg(key: str) -> str | None:
            row = session.get(AppConfig, key)
            return row.value if row else None

        if (cfg("actalog_sync_enabled") or "false").lower() != "true":
            return
        url = cfg("actalog_url")
        email = cfg("actalog_email")
        password = cfg("actalog_password")
        if not url or not email or not password:
            return

        from garminview.ingestion.actalog_client import ActalogClient
        from garminview.ingestion.actalog_sync import ActalogSync
        from garminview.ingestion.sync_logger import SyncLogger

        weight_unit = cfg("actalog_weight_unit") or "kg"
        refresh_token = cfg("actalog_refresh_token")
        client = ActalogClient(
            base_url=url, email=email, password=password,
            refresh_token=refresh_token, weight_unit=weight_unit,
        )
        sync_log = SyncLogger(session, source="actalog", mode="full")
        orchestrator = ActalogSync(session, weight_unit=weight_unit)
        try:
            await orchestrator.run(client, sync_log)
            if client.refresh_token and client.refresh_token != refresh_token:
                _set_actalog_cfg(session, "actalog_refresh_token", client.refresh_token)
            import datetime as _dt
            _set_actalog_cfg(session, "actalog_last_sync",
                             _dt.datetime.now(_dt.timezone.utc).isoformat())
            session.commit()
            _log.info("Actalog scheduled sync complete")
        except Exception as exc:
            _log.error("Actalog scheduled sync failed: %s", exc)


async def _garminview_sync_job():
    from garminview.api.routes.sync import _run_sync, _running
    if _running:
        _log.info("Scheduled garminview sync skipped — sync already running")
        return
    await _run_sync()


def _job_id(source: str, schedule_id: int) -> str:
    return f"sync_{source}_{schedule_id}"


def _register_job(row) -> None:
    """Register or replace one SyncSchedule job in the running scheduler."""
    job_id = _job_id(row.source, row.id)
    if not row.enabled:
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
        return

    if row.source == "actalog":
        fn = _actalog_job
    elif row.source == "garminview":
        fn = _garminview_sync_job
    else:
        _log.warning("Unknown sync source %s — skipping schedule %d", row.source, row.id)
        return

    try:
        trigger = CronTrigger.from_crontab(row.cron_expression)
    except Exception as exc:
        _log.error("Invalid cron '%s' for schedule %d: %s",
                   row.cron_expression, row.id, exc)
        return

    _scheduler.add_job(fn, trigger, id=job_id, replace_existing=True)
    _log.info("Registered job %s cron=%s", job_id, row.cron_expression)


def reload_schedule(schedule_id: int, session) -> None:
    """Hot-reload one SyncSchedule job after an admin update. Safe to call if
    scheduler is not yet running (no-op)."""
    if _scheduler is None or not _scheduler.running:
        return
    from garminview.models.config import SyncSchedule
    row = session.get(SyncSchedule, schedule_id)
    if row:
        _register_job(row)


def start_scheduler(session_factory) -> None:
    global _scheduler, _session_factory
    _session_factory = session_factory
    _scheduler = AsyncIOScheduler()

    # Fixed 24h actalog fallback job (used if no SyncSchedule DB row exists for actalog)
    _scheduler.add_job(
        _actalog_job,
        IntervalTrigger(hours=24),
        id="sync_actalog_legacy",
        replace_existing=True,
    )

    # Load DB-configured schedules
    try:
        with session_factory() as session:
            from garminview.models.config import SyncSchedule
            rows = session.query(SyncSchedule).all()
            for row in rows:
                _register_job(row)
    except Exception as exc:
        _log.warning("Could not load sync schedules from DB (will retry on next restart): %s", exc)

    _scheduler.start()
    _log.info("APScheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Add reload_schedule() call to PUT /admin/schedules/{id}**

In `backend/garminview/api/routes/admin.py`, find the `update_schedule` route and add the hot-reload call after `session.commit()`:

```python
# Find:
    row.cron_expression = cron
    row.enabled = enabled
    session.commit()
    return {"id": schedule_id, "cron": cron, "enabled": enabled}

# Replace with:
    row.cron_expression = cron
    row.enabled = enabled
    session.commit()
    from garminview.core.startup import reload_schedule
    reload_schedule(schedule_id, session)
    return {"id": schedule_id, "cron": cron, "enabled": enabled}
```

- [ ] **Step 3: Verify startup imports cleanly**

```bash
cd /home/jcz/Github/garminview/backend
uv run python -c "from garminview.api.main import create_app; create_app(); print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd /home/jcz/Github/garminview
git add backend/garminview/core/startup.py backend/garminview/api/routes/admin.py
git commit -m "feat: APScheduler loads SyncSchedule from DB with cron triggers and hot-reload"
```

---

## Task 4: Schema Alignment Alembic Migration

**Files:**
- Create: `backend/alembic/versions/0005_align_column_names.py`

- [ ] **Step 1: Check current drift**

```bash
cd /home/jcz/Github/garminview/backend
uv run alembic check
```

If output is "No new upgrade operations detected" — the models and migrations are already aligned. Skip directly to Step 4 (write a no-op placeholder migration).

If it lists columns, proceed with Step 2.

- [ ] **Step 2: Generate revision stub**

```bash
cd /home/jcz/Github/garminview/backend
uv run alembic revision --rev-id 0005 -m "align_column_names"
```

- [ ] **Step 3: Write the migration body**

Open the generated `alembic/versions/0005_align_column_names.py`. The initial migration already uses the correct column names (lat/lon/hr/speed/avg_speed etc.) matching the current models.

If `alembic check` reported specific differences, add dialect-aware rename operations:

```python
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Example pattern for any remaining renames (add only what alembic check reported):
    #
    # bind = op.get_bind()
    # if bind.dialect.name == "sqlite":
    #     with op.batch_alter_table("table_name") as batch_op:
    #         batch_op.alter_column("old_name", new_column_name="new_name",
    #                               existing_type=sa.Integer())
    # else:
    #     op.execute(sa.text("ALTER TABLE table_name RENAME COLUMN old_name TO new_name"))
    pass


def downgrade() -> None:
    pass
```

- [ ] **Step 4: Apply migration**

```bash
cd /home/jcz/Github/garminview/backend
uv run alembic upgrade head
```

Expected: applies without errors.

- [ ] **Step 5: Run tests**

```bash
cd /home/jcz/Github/garminview/backend
uv run pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd /home/jcz/Github/garminview
git add backend/alembic/versions/0005_align_column_names.py
git commit -m "chore: schema alignment migration (aligns column names with live MariaDB)"
```

---

## Task 5: CLAUDE.md Update

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add new section after QA commands**

Open `/home/jcz/Github/garminview/CLAUDE.md`. Add after the `## QA commands` section:

```markdown
## Production Database

MariaDB on external host — connection configured via `GARMINVIEW_DB_URL` in `.env`.
Format: `user:password@host:port/dbname`

## Key Implementation Patterns

### FIT file timestamp_16 resolution
When parsing FIT monitoring files, `timestamp_16` values are 16-bit offsets from
a base `timestamp` record. Always resolve them using the last seen full `timestamp`
field. Dropping the base timestamp causes ~80% of records to store NULL heart rate.
See `MonitoringFitAdapter` for the reference implementation.

### GarminDB CLI flags
Never pass `--analyze` to `garmindb_cli.py` — it re-analyzes the entire DB and
was ~80% of total sync time. Only use `--all --download --import --latest`.

### Column naming conventions (match live MariaDB)
- Short: `hr` not `heart_rate`, `lat`/`lon` not `latitude`/`longitude`
- Speed: `avg_speed` not `avg_speed_ms`
- Elevation: `ascent_m`/`descent_m` not `total_ascent_m`/`total_descent_m`
```

- [ ] **Step 2: Commit**

```bash
cd /home/jcz/Github/garminview
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with MariaDB info, FIT patterns, column naming"
```

---

## Task 6: GarminDB Dependency + Docker Volume

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add garmindb to pyproject.toml dependencies**

In `backend/pyproject.toml`, add after `"garminconnect>=0.2.19",`:

```toml
    "garmindb>=1.1.0",
```

- [ ] **Step 2: Update the lockfile**

```bash
cd /home/jcz/Github/garminview/backend
uv lock
```

Expected: `uv.lock` updates with garmindb and its dependencies.

- [ ] **Step 3: Verify garmindb_cli.py is accessible**

```bash
cd /home/jcz/Github/garminview/backend
uv run garmindb_cli.py --version
```

Expected: prints garmindb version string.

- [ ] **Step 4: Remove :ro from HealthData volume in docker-compose.yml**

Find:
```yaml
      - ${HEALTH_DATA_DIR:-~/HealthData}:/data/HealthData:ro
```

Change to:
```yaml
      - ${HEALTH_DATA_DIR:-~/HealthData}:/data/HealthData
```

Leave `.GarminDb` mount as `:ro`.

- [ ] **Step 5: Run tests**

```bash
cd /home/jcz/Github/garminview/backend
uv run pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
cd /home/jcz/Github/garminview
git add backend/pyproject.toml backend/uv.lock docker-compose.yml
git commit -m "feat: add garmindb to container deps; make HealthData volume writable for scheduled sync"
```

---

## Task 7: Version Bump + Docker Build + Local Deploy

**Files:**
- Modify: `backend/pyproject.toml` (version field)
- Modify: `backend/garminview/api/main.py` (version strings)

- [ ] **Step 1: Bump version to 0.6.0**

In `backend/pyproject.toml`:
```toml
version = "0.6.0"
```

In `backend/garminview/api/main.py`, update both version references from `"0.5.0"` to `"0.6.0"`.

- [ ] **Step 2: Commit version bump**

```bash
cd /home/jcz/Github/garminview
git add backend/pyproject.toml backend/garminview/api/main.py
git commit -m "chore: bump version to 0.6.0"
```

- [ ] **Step 3: Build backend image**

```bash
cd /home/jcz/Github/garminview
docker build -t ghcr.io/johnzastrow/garminview-backend:local backend/
```

Verify garmindb is installed in the image:

```bash
docker run --rm ghcr.io/johnzastrow/garminview-backend:local garmindb_cli.py --version
```

Expected: prints garmindb version.

- [ ] **Step 4: Build frontend image**

```bash
docker build -t ghcr.io/johnzastrow/garminview-frontend:local frontend/
```

Expected: builds without errors.

- [ ] **Step 5: Ensure .env is configured for MariaDB**

The `.env` file in the project root must contain:

```
IMAGE_TAG=local
GARMINVIEW_DB_BACKEND=mariadb
GARMINVIEW_DB_URL=<user>:<password>@<mariadb-host>:3306/<dbname>
HEALTH_DATA_DIR=~/HealthData
GARMINDB_CONFIG_DIR=~/.GarminDb
GARMINVIEW_PORT=8080
```

- [ ] **Step 6: Start the stack**

```bash
cd /home/jcz/Github/garminview
docker compose up -d
```

- [ ] **Step 7: Smoke test the API**

```bash
# Root check
curl -s http://localhost:8000/ | python3 -m json.tool

# Daily summary
curl -s "http://localhost:8000/health/daily?days=7" | python3 -m json.tool | head -30

# Training load
curl -s "http://localhost:8000/training/load?days=30" | python3 -m json.tool | head -20

# Schedules
curl -s http://localhost:8000/admin/schedules | python3 -m json.tool
```

Expected: all return valid JSON with data (not empty, not 500s).

- [ ] **Step 8: Verify garmindb_cli.py is on PATH inside the container**

```bash
docker compose exec backend which garmindb_cli.py
```

Expected: a path under `/app/.venv/bin/` or similar.

---

## Task 8: Historical Monitoring Re-ingestion

> **Prerequisite:** Docker stack running and connected to MariaDB (Task 7 complete).

- [ ] **Step 1: Run the backfill (run in tmux or background — takes hours)**

```bash
cd /home/jcz/Github/garminview/backend
uv run python tests/validation/run_garminview.py --start 2012-01-01 --end 2023-12-31
```

- [ ] **Step 2: Run validation suite after completion**

```bash
cd /home/jcz/Github/garminview/backend
uv run python tests/validation/compare.py
```

Expected: all tables PASS.

- [ ] **Step 3: Mark TODO.md items complete and commit**

Open `TODO.md`. Move all items under "Open:" sections into "Completed work" under a new heading `### Open work completion (2026-03-12)`.

```bash
cd /home/jcz/Github/garminview
git add TODO.md
git commit -m "docs: mark all open work items complete"
```
