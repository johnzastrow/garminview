"""FastAPI routes for Actalog workout data and admin endpoints."""
from __future__ import annotations

from datetime import datetime, date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, Date as SADate
from sqlalchemy.orm import Session

from garminview.api.deps import get_db
from garminview.api.schemas.actalog import (
    WorkoutListItem,
    WorkoutDetail,
    MovementItem,
    WodItem,
    SessionVitals,
    MovementRef,
    MovementHistoryItem,
    PRItem,
    CrossRefItem,
    ActalogConfigOut,
    ActalogSyncStatus,
    ActalogConfigIn,
)
from garminview.models.actalog import (
    ActalogWorkout,
    ActalogMovement,
    ActalogWorkoutMovement,
    ActalogWorkoutWod,
    ActalogWod,
    ActalogPersonalRecord,
)
from garminview.models.config import AppConfig
from garminview.models.health import DailySummary
from garminview.models.monitoring import MonitoringHeartRate
from garminview.models.supplemental import BodyBatteryEvent
from garminview.models.health import Stress
from garminview.models.sync import SyncLog

router = APIRouter()
admin_router = APIRouter()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_cfg(session: Session, key: str) -> str | None:
    row = session.get(AppConfig, key)
    return row.value if row else None


def _set_cfg(session: Session, key: str, value: str) -> None:
    row = session.get(AppConfig, key)
    if row is None:
        row = AppConfig(key=key, category="actalog", data_type="string")
        session.add(row)
    row.value = value
    row.updated_at = datetime.now()


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------

@router.get("/workouts", response_model=list[WorkoutListItem])
def list_workouts(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    q = session.query(ActalogWorkout)
    if start:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) >= start)
    if end:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) <= end)
    q = q.order_by(ActalogWorkout.workout_date.desc()).offset(offset).limit(limit)
    return q.all()


@router.get("/workouts/{workout_id}", response_model=WorkoutDetail)
def get_workout(
    workout_id: int,
    session: Annotated[Session, Depends(get_db)],
):
    workout = session.get(ActalogWorkout, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    movements = (
        session.query(ActalogWorkoutMovement)
        .filter(ActalogWorkoutMovement.workout_id == workout_id)
        .order_by(ActalogWorkoutMovement.order_index)
        .all()
    )
    wods = (
        session.query(ActalogWorkoutWod)
        .filter(ActalogWorkoutWod.workout_id == workout_id)
        .order_by(ActalogWorkoutWod.order_index)
        .all()
    )

    return WorkoutDetail(
        id=workout.id,
        workout_date=workout.workout_date,
        workout_name=workout.workout_name,
        workout_type=workout.workout_type,
        total_time_s=workout.total_time_s,
        notes=workout.notes,
        movements=[MovementItem.model_validate(m) for m in movements],
        wods=[WodItem.model_validate(w) for w in wods],
    )


@router.get("/workouts/{workout_id}/session-vitals", response_model=SessionVitals)
def get_session_vitals(
    workout_id: int,
    session: Annotated[Session, Depends(get_db)],
):
    workout = session.get(ActalogWorkout, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Build detail object
    movements = (
        session.query(ActalogWorkoutMovement)
        .filter(ActalogWorkoutMovement.workout_id == workout_id)
        .order_by(ActalogWorkoutMovement.order_index)
        .all()
    )
    wods = (
        session.query(ActalogWorkoutWod)
        .filter(ActalogWorkoutWod.workout_id == workout_id)
        .order_by(ActalogWorkoutWod.order_index)
        .all()
    )

    detail = WorkoutDetail(
        id=workout.id,
        workout_date=workout.workout_date,
        workout_name=workout.workout_name,
        workout_type=workout.workout_type,
        total_time_s=workout.total_time_s,
        notes=workout.notes,
        movements=[MovementItem.model_validate(m) for m in movements],
        wods=[WodItem.model_validate(w) for w in wods],
    )

    # No duration → no vitals possible
    if workout.total_time_s is None or workout.workout_date is None:
        return SessionVitals(workout=detail, has_vitals=False)

    workout_day = workout.workout_date.date()
    workout_start = workout.workout_date
    # End time estimate: start + duration
    from datetime import timedelta
    workout_end = workout_start + timedelta(seconds=workout.total_time_s)

    # HR series from monitoring
    hr_rows = (
        session.query(MonitoringHeartRate)
        .filter(MonitoringHeartRate.timestamp >= workout_start)
        .filter(MonitoringHeartRate.timestamp <= workout_end)
        .order_by(MonitoringHeartRate.timestamp)
        .all()
    )
    hr_series = [{"ts": r.timestamp.isoformat(), "hr": r.hr} for r in hr_rows]

    # Body battery events for the workout day
    bb_rows = (
        session.query(BodyBatteryEvent)
        .filter(BodyBatteryEvent.date == workout_day)
        .order_by(BodyBatteryEvent.start)
        .all()
    )
    body_battery = [
        {"start": r.start.isoformat() if r.start else None, "value": r.value, "event_type": r.event_type}
        for r in bb_rows
    ]

    # Stress data during workout window
    stress_rows = (
        session.query(Stress)
        .filter(Stress.timestamp >= workout_start)
        .filter(Stress.timestamp <= workout_end)
        .order_by(Stress.timestamp)
        .all()
    )
    stress = [{"ts": r.timestamp.isoformat(), "stress_level": r.stress_level} for r in stress_rows]

    has_vitals = bool(hr_series or body_battery or stress)

    return SessionVitals(
        workout=detail,
        has_vitals=has_vitals,
        hr_series=hr_series,
        body_battery=body_battery,
        stress=stress,
    )


@router.get("/movements", response_model=list[MovementRef])
def list_movements(
    session: Annotated[Session, Depends(get_db)],
):
    return session.query(ActalogMovement).order_by(ActalogMovement.name).all()


@router.get("/movements/{movement_id}/history", response_model=list[MovementHistoryItem])
def movement_history(
    movement_id: int,
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = (
        session.query(ActalogWorkoutMovement, ActalogWorkout.workout_date)
        .join(ActalogWorkout, ActalogWorkoutMovement.workout_id == ActalogWorkout.id)
        .filter(ActalogWorkoutMovement.movement_id == movement_id)
    )
    if start:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) >= start)
    if end:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) <= end)
    q = q.order_by(ActalogWorkout.workout_date.desc())

    results = []
    for wm, workout_date in q.all():
        results.append(MovementHistoryItem(
            id=wm.id,
            workout_id=wm.workout_id,
            sets=wm.sets,
            reps=wm.reps,
            weight_kg=wm.weight_kg,
            time_s=wm.time_s,
            rpe=wm.rpe,
            is_pr=wm.is_pr,
            workout_date=workout_date,
        ))
    return results


@router.get("/wods", response_model=list[dict])
def list_wods(
    session: Annotated[Session, Depends(get_db)],
):
    rows = session.query(ActalogWod).order_by(ActalogWod.name).all()
    return [
        {"id": r.id, "name": r.name, "regime": r.regime, "score_type": r.score_type}
        for r in rows
    ]


@router.get("/wods/{wod_id}/history", response_model=list[dict])
def wod_history(
    wod_id: int,
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = (
        session.query(ActalogWorkoutWod, ActalogWorkout.workout_date)
        .join(ActalogWorkout, ActalogWorkoutWod.workout_id == ActalogWorkout.id)
        .filter(ActalogWorkoutWod.wod_id == wod_id)
    )
    if start:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) >= start)
    if end:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) <= end)
    q = q.order_by(ActalogWorkout.workout_date.desc())

    results = []
    for ww, workout_date in q.all():
        results.append({
            "id": ww.id,
            "workout_id": ww.workout_id,
            "wod_id": ww.wod_id,
            "score_value": ww.score_value,
            "time_s": ww.time_s,
            "rounds": ww.rounds,
            "reps": ww.reps,
            "weight_kg": ww.weight_kg,
            "rpe": ww.rpe,
            "is_pr": ww.is_pr,
            "workout_date": workout_date.isoformat() if workout_date else None,
        })
    return results


@router.get("/prs", response_model=list[PRItem])
def list_prs(
    session: Annotated[Session, Depends(get_db)],
):
    rows = (
        session.query(ActalogPersonalRecord, ActalogMovement.name, ActalogMovement.movement_type)
        .join(ActalogMovement, ActalogPersonalRecord.movement_id == ActalogMovement.id)
        .order_by(ActalogMovement.name)
        .all()
    )
    results = []
    for pr, mov_name, mov_type in rows:
        results.append(PRItem(
            movement_id=pr.movement_id,
            movement_name=mov_name,
            movement_type=mov_type,
            max_weight_kg=pr.max_weight_kg,
            max_reps=pr.max_reps,
            best_time_s=pr.best_time_s,
            workout_date=pr.workout_date,
        ))
    return results


@router.get("/cross-reference", response_model=list[CrossRefItem])
def cross_reference(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    from sqlalchemy import func

    q = (
        session.query(
            ActalogWorkout.workout_date,
            ActalogWorkout.workout_name,
            ActalogWorkout.workout_type,
            func.sum(
                ActalogWorkoutMovement.sets * ActalogWorkoutMovement.reps * ActalogWorkoutMovement.weight_kg
            ).label("total_volume_kg"),
            DailySummary.body_battery_max,
            DailySummary.hr_resting,
            DailySummary.sleep_score,
            DailySummary.stress_avg,
        )
        .outerjoin(
            ActalogWorkoutMovement,
            ActalogWorkoutMovement.workout_id == ActalogWorkout.id,
        )
        .outerjoin(
            DailySummary,
            cast(ActalogWorkout.workout_date, SADate) == DailySummary.date,
        )
        .group_by(
            ActalogWorkout.id,
            ActalogWorkout.workout_date,
            ActalogWorkout.workout_name,
            ActalogWorkout.workout_type,
            DailySummary.body_battery_max,
            DailySummary.hr_resting,
            DailySummary.sleep_score,
            DailySummary.stress_avg,
        )
    )
    if start:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) >= start)
    if end:
        q = q.filter(cast(ActalogWorkout.workout_date, SADate) <= end)
    q = q.order_by(ActalogWorkout.workout_date.desc())

    results = []
    for row in q.all():
        results.append(CrossRefItem(
            workout_date=row.workout_date,
            workout_name=row.workout_name,
            workout_type=row.workout_type,
            total_volume_kg=row.total_volume_kg,
            body_battery_max=row.body_battery_max,
            hr_resting=row.hr_resting,
            sleep_score=row.sleep_score,
            stress_avg=row.stress_avg,
        ))
    return results


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@admin_router.get("/config", response_model=ActalogConfigOut)
def get_actalog_config(
    session: Annotated[Session, Depends(get_db)],
):
    """Read actalog config from app_config table. Password is never returned."""
    url = _get_cfg(session, "actalog_url")
    email = _get_cfg(session, "actalog_email")
    weight_unit = _get_cfg(session, "actalog_weight_unit")
    sync_interval_raw = _get_cfg(session, "actalog_sync_interval_hours")
    sync_enabled_raw = _get_cfg(session, "actalog_sync_enabled")
    last_sync = _get_cfg(session, "actalog_last_sync")

    sync_interval_hours: int | None = int(sync_interval_raw) if sync_interval_raw else None
    sync_enabled: bool = sync_enabled_raw.lower() in ("1", "true", "yes") if sync_enabled_raw else False

    return ActalogConfigOut(
        url=url,
        email=email,
        weight_unit=weight_unit,
        sync_interval_hours=sync_interval_hours,
        sync_enabled=sync_enabled,
        last_sync=last_sync,
    )


@admin_router.put("/config")
def update_admin_config(
    session: Annotated[Session, Depends(get_db)],
    body: ActalogConfigIn,
):
    """Write actalog config to app_config table. Accepts a JSON request body."""
    now = datetime.now()
    updates = {
        "actalog_url": body.url,
        "actalog_email": body.email,
        "actalog_password": body.password,
        "actalog_weight_unit": body.weight_unit,
        "actalog_sync_interval_hours": str(body.sync_interval_hours) if body.sync_interval_hours is not None else None,
        "actalog_sync_enabled": str(body.sync_enabled).lower() if body.sync_enabled is not None else None,
    }
    for key, val in updates.items():
        if val is None:
            continue
        row = session.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, category="actalog", data_type="string")
            session.add(row)
        row.value = val
        row.updated_at = now
    session.commit()
    return {"ok": True}


@admin_router.post("/sync")
async def trigger_sync(session: Annotated[Session, Depends(get_db)]):
    """Run ActalogSync.run() using stored config. Returns counts dict."""
    url = _get_cfg(session, "actalog_url")
    email = _get_cfg(session, "actalog_email")
    password = _get_cfg(session, "actalog_password")
    if not url or not email or not password:
        raise HTTPException(400, "Actalog not configured — set url, email, and password first")

    from garminview.ingestion.actalog_client import ActalogClient
    from garminview.ingestion.actalog_sync import ActalogSync
    from garminview.ingestion.sync_logger import SyncLogger

    weight_unit = _get_cfg(session, "actalog_weight_unit") or "kg"
    refresh_token = _get_cfg(session, "actalog_refresh_token")

    client = ActalogClient(
        base_url=url, email=email, password=password,
        refresh_token=refresh_token, weight_unit=weight_unit,
    )
    sync_log = SyncLogger(session, source="actalog", mode="full")
    orchestrator = ActalogSync(session, weight_unit=weight_unit)

    try:
        counts = await orchestrator.run(client, sync_log)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Actalog sync failed: {exc}")

    if client.refresh_token and client.refresh_token != refresh_token:
        _set_cfg(session, "actalog_refresh_token", client.refresh_token)
    _set_cfg(session, "actalog_last_sync", datetime.now().isoformat())
    session.commit()

    return counts


@admin_router.post("/test-connection")
async def test_connection(
    session: Annotated[Session, Depends(get_db)],
    url: str | None = Query(default=None),
    email: str | None = Query(default=None),
    password: str | None = Query(default=None),
):
    """Test actalog login. Falls back to stored config if params not provided."""
    from garminview.ingestion.actalog_client import ActalogClient

    resolved_url = url or _get_cfg(session, "actalog_url")
    resolved_email = email or _get_cfg(session, "actalog_email")
    resolved_password = password or _get_cfg(session, "actalog_password")

    if not resolved_url or not resolved_email or not resolved_password:
        raise HTTPException(status_code=400, detail="URL, email, and password are required")

    client = ActalogClient(base_url=resolved_url, email=resolved_email, password=resolved_password)
    try:
        await client._login()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}")


@admin_router.get("/sync/status", response_model=ActalogSyncStatus)
def sync_status(
    session: Annotated[Session, Depends(get_db)],
):
    """Return the most recent sync log entry for source='actalog'."""
    row = (
        session.query(SyncLog)
        .filter(SyncLog.source == "actalog")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if row is None:
        return ActalogSyncStatus(
            last_sync=None,
            status=None,
            records_upserted=None,
            error_message=None,
        )
    return ActalogSyncStatus(
        last_sync=row.started_at.isoformat() if row.started_at else None,
        status=row.status,
        records_upserted=row.records_upserted,
        error_message=row.error_message,
    )
