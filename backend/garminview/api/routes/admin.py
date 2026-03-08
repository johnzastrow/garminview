from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Annotated
from sqlalchemy.orm import Session

from garminview.models.config import AppConfig, SyncSchedule
from garminview.models.sync import SyncLog, SchemaVersion
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/config")
def get_all_config(session: Annotated[Session, Depends(get_db)]):
    rows = session.query(AppConfig).order_by(AppConfig.category, AppConfig.key).all()
    return {"config": [{"key": r.key, "value": r.value, "category": r.category} for r in rows]}


@router.put("/config/{key}")
def update_config(key: str, value: str, session: Annotated[Session, Depends(get_db)]):
    row = session.get(AppConfig, key)
    if not row:
        raise HTTPException(404, "Config key not found")
    row.value = value
    row.updated_at = datetime.now(timezone.utc)
    session.commit()
    return {"key": key, "value": value}


@router.get("/schedules")
def list_schedules(session: Annotated[Session, Depends(get_db)]):
    rows = session.query(SyncSchedule).all()
    return {"schedules": [{"id": r.id, "source": r.source, "cron": r.cron_expression,
                           "enabled": r.enabled, "last_run": r.last_run} for r in rows]}


@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, cron: str, enabled: bool,
                    session: Annotated[Session, Depends(get_db)]):
    row = session.get(SyncSchedule, schedule_id)
    if not row:
        raise HTTPException(404, "Schedule not found")
    row.cron_expression = cron
    row.enabled = enabled
    session.commit()
    return {"id": schedule_id, "cron": cron, "enabled": enabled}


@router.get("/schema-version")
def schema_version(session: Annotated[Session, Depends(get_db)]):
    latest = session.query(SchemaVersion).order_by(SchemaVersion.applied_at.desc()).first()
    return {"version": latest.version if latest else None}


@router.get("/sync-logs")
def sync_logs(session: Annotated[Session, Depends(get_db)], limit: int = 20):
    rows = session.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit).all()
    return {"logs": [{"id": r.id, "source": r.source, "status": r.status,
                      "started_at": r.started_at, "records_upserted": r.records_upserted} for r in rows]}
