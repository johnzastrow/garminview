from datetime import datetime, timezone
from sqlalchemy.orm import Session
from garminview.models.sync import SchemaVersion
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
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
_log = logging.getLogger(__name__)


def _set_actalog_cfg(session, key: str, value: str) -> None:
    from garminview.models.config import AppConfig
    row = session.get(AppConfig, key)
    if row is None:
        row = AppConfig(key=key, category="actalog", data_type="string")
        session.add(row)
    row.value = value


def start_scheduler(session_factory) -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()

    async def _actalog_job():
        with session_factory() as session:
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
                _set_actalog_cfg(session, "actalog_last_sync", _dt.datetime.now(_dt.timezone.utc).isoformat())
                session.commit()
                _log.info("Actalog scheduled sync complete")
            except Exception as exc:
                _log.error("Actalog scheduled sync failed: %s", exc)

    _scheduler.add_job(
        _actalog_job,
        IntervalTrigger(hours=24),
        id="sync_actalog",
        replace_existing=True,
    )
    _scheduler.start()
    _log.info("APScheduler started with actalog interval job (24h)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
