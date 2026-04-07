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
    """Hot-reload one SyncSchedule job after an admin update. No-op if scheduler not running."""
    if _scheduler is None or not _scheduler.running:
        return
    from garminview.models.config import SyncSchedule
    row = session.get(SyncSchedule, schedule_id)
    if row:
        _register_job(row)


def _backfill_hr_zones(session_factory) -> None:
    """Compute daily_hr_zones for any missing dates in the last 90 days."""
    from datetime import date, timedelta
    from garminview.analysis.hr_zones import compute_daily_hr_zones
    from garminview.models.health import DailyHRZones

    today = date.today()
    cutoff = today - timedelta(days=90)
    all_dates = [cutoff + timedelta(days=i) for i in range((today - cutoff).days + 1)]

    with session_factory() as session:
        existing = {
            row.date
            for row in session.query(DailyHRZones.date)
            .filter(DailyHRZones.date >= cutoff)
            .all()
        }
        missing = [d for d in all_dates if d not in existing]
        if missing:
            _log.info("Backfilling daily_hr_zones for %d dates", len(missing))
            compute_daily_hr_zones(session, missing)


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
        _log.warning("Could not load sync schedules from DB (will retry on restart): %s", exc)

    _scheduler.start()
    _log.info("APScheduler started")

    # Backfill missing daily HR zones for last 90 days
    try:
        _backfill_hr_zones(session_factory)
    except Exception as exc:
        _log.warning("HR zones backfill failed: %s", exc)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
