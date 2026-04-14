"""FastAPI routes for Actalog workout data and admin endpoints."""
from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import cast, Date as SADate, func, or_
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
    NoteParseItem,
    NoteParseQueue,
    ParserRunResult,
    ParserJobStatus,
    ParserConfigOut,
    ParserConfigIn,
    NoteParseApproveIn,
    ParserStats,
    ParserModelStats,
)
from garminview.models.actalog import (
    ActalogWorkout,
    ActalogMovement,
    ActalogWorkoutMovement,
    ActalogWorkoutWod,
    ActalogWod,
    ActalogPersonalRecord,
    ActalogNoteParse,
)
from garminview.ingestion.notes_parser import (
    NotesParser,
    seed_default_config,
    CONFIG_KEY_PROMPT,
    CONFIG_KEY_MODEL,
    CONFIG_KEY_URL,
    CONFIG_KEY_MIN_LENGTH,
)
from garminview.models.config import AppConfig
from garminview.models.health import DailySummary
from garminview.models.monitoring import MonitoringHeartRate
from garminview.models.supplemental import BodyBatteryEvent
from garminview.models.health import Stress
from garminview.models.sync import SyncLog

_log = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter()

# ---------------------------------------------------------------------------
# Parser run-state (in-memory flag; resets on process restart)
# ---------------------------------------------------------------------------

_parser_running: bool = False


def _run_parse_pending_bg(factory) -> None:
    """Background task: parse pending notes using a fresh DB session."""
    global _parser_running
    try:
        with factory() as session:
            seed_default_config(session)
            parser = NotesParser(session)
            parser.parse_pending()
    finally:
        _parser_running = False


def _run_reparse_all_bg(factory) -> None:
    """Background task: delete non-approved staging records and re-run the parser."""
    global _parser_running
    try:
        with factory() as session:
            session.query(ActalogNoteParse).filter(
                ActalogNoteParse.parse_status != "approved"
            ).delete(synchronize_session=False)
            session.commit()
            seed_default_config(session, update_prompt=True)
            parser = NotesParser(session)
            parser.parse_pending()
    finally:
        _parser_running = False


def _run_reparse_skipped_bg(factory) -> None:
    """Background task: delete all skipped records and re-parse them with force=True."""
    global _parser_running
    try:
        with factory() as session:
            # Find all skipped workout IDs before deleting
            skipped = session.query(ActalogNoteParse.workout_id).filter(
                ActalogNoteParse.parse_status == "skipped"
            ).all()
            workout_ids = [row[0] for row in skipped]

            if not workout_ids:
                _log.info("No skipped records to reparse")
                return

            # Delete the skipped records
            session.query(ActalogNoteParse).filter(
                ActalogNoteParse.parse_status == "skipped"
            ).delete(synchronize_session=False)
            session.commit()

            # Re-parse each with force=True (bypasses regex pre-pass)
            seed_default_config(session)
            parser = NotesParser(session)
            count = 0
            for wid in workout_ids:
                try:
                    parser.parse_workout(wid, force=True)
                    session.commit()
                    count += 1
                except Exception as exc:
                    _log.warning("Reparse skipped workout %d failed: %s", wid, exc)
                    session.rollback()
            _log.info("Reparsed %d/%d skipped workouts", count, len(workout_ids))
    finally:
        _parser_running = False


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
    stored_password = _get_cfg(session, "actalog_password")
    weight_unit = _get_cfg(session, "actalog_weight_unit")
    sync_interval_raw = _get_cfg(session, "actalog_sync_interval_hours")
    sync_enabled_raw = _get_cfg(session, "actalog_sync_enabled")
    last_sync = _get_cfg(session, "actalog_last_sync")

    sync_interval_hours: int | None = int(sync_interval_raw) if sync_interval_raw else None
    sync_enabled: bool = sync_enabled_raw.lower() in ("1", "true", "yes") if sync_enabled_raw else False

    return ActalogConfigOut(
        url=url,
        email=email,
        has_password=bool(stored_password),
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
        "actalog_password": body.password or None,  # blank string = keep existing
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


# ---------------------------------------------------------------------------
# Notes parser admin routes  (prefix: /admin/actalog/parser)
# ---------------------------------------------------------------------------

parser_router = APIRouter()


def _parse_item(row: ActalogNoteParse, session: Session) -> NoteParseItem:
    """Enrich a staging row with workout name/date for display."""
    workout = session.get(ActalogWorkout, row.workout_id) if row.workout_id else None
    formatted_markdown = None
    if row.parsed_json:
        try:
            formatted_markdown = json.loads(row.parsed_json).get("formatted_markdown")
        except Exception:
            pass
    return NoteParseItem(
        id=row.id,
        workout_id=row.workout_id,
        workout_name=workout.workout_name if workout else None,
        workout_date=workout.workout_date if workout else None,
        content_class=row.content_class,
        parse_status=row.parse_status,
        parsed_at=row.parsed_at,
        reviewed_at=row.reviewed_at,
        error_message=row.error_message,
        llm_model=row.llm_model,
        raw_notes=row.raw_notes,
        formatted_markdown=formatted_markdown,
        parsed_json=row.parsed_json,
    )


@parser_router.get("/status", response_model=ParserJobStatus)
def get_parser_status(session: Session = Depends(get_db)):
    """Return whether a parser job is currently running and total staged record count."""
    total_staged = session.query(ActalogNoteParse).count()
    return ParserJobStatus(running=_parser_running, total_staged=total_staged)


@parser_router.get("/queue", response_model=NoteParseQueue)
def get_parser_queue(
    status: str | None = Query(None, description="Filter by parse_status"),
    content_class: str | None = Query(None, description="Filter by content_class"),
    q: str | None = Query(None, description="Keyword search in workout name and notes"),
    sort: str = Query("date", description="Sort field: date"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    session: Session = Depends(get_db),
):
    """List staged parse records with filtering, sorting, and search."""
    query = session.query(ActalogNoteParse)

    if status:
        query = query.filter(ActalogNoteParse.parse_status == status)

    if content_class:
        query = query.filter(ActalogNoteParse.content_class == content_class)

    if q:
        search_term = f"%{q}%"
        query = query.join(
            ActalogWorkout, ActalogNoteParse.workout_id == ActalogWorkout.id
        ).filter(
            or_(
                ActalogWorkout.name.ilike(search_term),
                ActalogNoteParse.raw_notes.ilike(search_term),
            )
        )

    sort_col = ActalogNoteParse.parsed_at
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    rows = query.all()
    return NoteParseQueue(
        total=len(rows),
        items=[_parse_item(r, session) for r in rows],
    )


@parser_router.post("/run", response_model=ParserJobStatus)
def run_parser(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
):
    """Start the parser on all unprocessed notes. Returns immediately."""
    global _parser_running
    from garminview.core.config import get_config
    from garminview.core.database import create_db_engine, get_session_factory
    if _parser_running:
        total_staged = session.query(ActalogNoteParse).count()
        return ParserJobStatus(running=True, total_staged=total_staged)
    _parser_running = True
    config = get_config()
    engine = create_db_engine(config)
    factory = get_session_factory(engine)
    background_tasks.add_task(_run_parse_pending_bg, factory)
    total_staged = session.query(ActalogNoteParse).count()
    return ParserJobStatus(running=True, total_staged=total_staged)


@parser_router.post("/approve/{parse_id}", response_model=NoteParseItem)
def approve_parse(
    parse_id: int,
    body: NoteParseApproveIn,
    session: Session = Depends(get_db),
):
    """Approve a parse record. Writes Markdown to workout.notes and commits WODs."""
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise HTTPException(status_code=404, detail="Parse record not found")

    workout = session.get(ActalogWorkout, record.workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Apply any human edits supplied in the request body
    markdown = body.formatted_markdown or workout.formatted_notes
    perf_notes = body.performance_notes or workout.performance_notes

    # Write approved Markdown to the canonical notes field
    workout.notes = markdown
    workout.formatted_notes = markdown
    workout.performance_notes = perf_notes

    record.parse_status = "approved"
    record.reviewed_at = datetime.now()

    session.commit()

    # Trigger write-back to Actalog API (failure keeps status=approved)
    try:
        from garminview.ingestion.actalog_writeback import write_back_approved
        final_status = write_back_approved(session, parse_id, edited_markdown=markdown)
        _log.info("Parse %d: approve -> %s", parse_id, final_status)
    except Exception as exc:
        _log.warning("Write-back failed for parse %d: %s", parse_id, exc)

    # Refresh record after potential status change
    session.refresh(record)

    return _parse_item(record, session)


@parser_router.post("/push/{parse_id}", response_model=NoteParseItem)
def push_to_actalog(
    parse_id: int,
    session: Session = Depends(get_db),
):
    """Retry pushing an approved parse to Actalog API."""
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise HTTPException(status_code=404, detail="Parse record not found")
    if record.parse_status != "approved":
        raise HTTPException(status_code=400, detail="Only approved (not yet sent) records can be pushed")

    from garminview.ingestion.actalog_writeback import write_back_approved
    final_status = write_back_approved(session, parse_id)
    session.refresh(record)
    return _parse_item(record, session)


@parser_router.post("/reject/{parse_id}", response_model=NoteParseItem)
def reject_parse(
    parse_id: int,
    session: Session = Depends(get_db),
):
    """Reject a parse record. Raw notes are left untouched."""
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise HTTPException(status_code=404, detail="Parse record not found")
    record.parse_status = "rejected"
    record.reviewed_at = datetime.now()
    session.commit()
    return _parse_item(record, session)


@parser_router.post("/reparse/{workout_id}", response_model=NoteParseItem)
def reparse_workout(
    workout_id: int,
    session: Session = Depends(get_db),
):
    """Delete any existing parse for a workout and re-run the LLM."""
    existing = (
        session.query(ActalogNoteParse)
        .filter(ActalogNoteParse.workout_id == workout_id)
        .first()
    )
    if existing:
        session.delete(existing)
        session.flush()
    seed_default_config(session)
    parser = NotesParser(session)
    record = parser.parse_workout(workout_id, force=True)
    session.commit()
    return _parse_item(record, session)


@parser_router.post("/reparse-all", response_model=ParserJobStatus)
def reparse_all(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
):
    """Delete all non-approved staging records and re-run the parser. Returns immediately."""
    global _parser_running
    from garminview.core.config import get_config
    from garminview.core.database import create_db_engine, get_session_factory
    if _parser_running:
        total_staged = session.query(ActalogNoteParse).count()
        return ParserJobStatus(running=True, total_staged=total_staged)
    _parser_running = True
    config = get_config()
    engine = create_db_engine(config)
    factory = get_session_factory(engine)
    background_tasks.add_task(_run_reparse_all_bg, factory)
    total_staged = session.query(ActalogNoteParse).count()
    return ParserJobStatus(running=True, total_staged=total_staged)


@parser_router.post("/reparse-skipped", response_model=ParserJobStatus)
def reparse_skipped(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
):
    """Re-parse all skipped records with force=True (bypasses regex pre-pass). Returns immediately."""
    global _parser_running
    from garminview.core.config import get_config
    from garminview.core.database import create_db_engine, get_session_factory
    if _parser_running:
        total_staged = session.query(ActalogNoteParse).count()
        return ParserJobStatus(running=True, total_staged=total_staged)
    skipped_count = session.query(ActalogNoteParse).filter(
        ActalogNoteParse.parse_status == "skipped"
    ).count()
    if skipped_count == 0:
        total_staged = session.query(ActalogNoteParse).count()
        return ParserJobStatus(running=False, total_staged=total_staged)
    _parser_running = True
    config = get_config()
    engine = create_db_engine(config)
    factory = get_session_factory(engine)
    background_tasks.add_task(_run_reparse_skipped_bg, factory)
    total_staged = session.query(ActalogNoteParse).count()
    return ParserJobStatus(running=True, total_staged=total_staged)


@parser_router.get("/stats", response_model=ParserStats)
def get_parser_stats(session: Session = Depends(get_db)):
    """Aggregate timing and status metrics for all parse records."""
    rows = session.query(ActalogNoteParse).all()

    by_status: dict[str, int] = {}
    for r in rows:
        s = r.parse_status or "unknown"
        by_status[s] = by_status.get(s, 0) + 1

    # Group timing by model
    from collections import defaultdict
    groups: dict[str | None, list] = defaultdict(list)
    for r in rows:
        if r.parse_duration_s is not None:
            groups[r.llm_model].append(r)

    def _avg(vals):
        return round(sum(vals) / len(vals), 2) if vals else None

    by_model = []
    for model, model_rows in groups.items():
        wall = [r.parse_duration_s for r in model_rows if r.parse_duration_s is not None]
        infer = [r.llm_inference_s for r in model_rows if r.llm_inference_s is not None]
        tok_p = [r.llm_tokens_prompt for r in model_rows if r.llm_tokens_prompt is not None]
        tok_g = [r.llm_tokens_generated for r in model_rows if r.llm_tokens_generated is not None]
        by_model.append(ParserModelStats(
            model=model,
            n=len(model_rows),
            avg_wall_s=_avg(wall),
            avg_inference_s=_avg(infer),
            avg_tokens_prompt=_avg(tok_p),
            avg_tokens_generated=_avg(tok_g),
            min_wall_s=round(min(wall), 2) if wall else None,
            max_wall_s=round(max(wall), 2) if wall else None,
        ))

    return ParserStats(total=len(rows), by_status=by_status, by_model=by_model)


@parser_router.get("/config", response_model=ParserConfigOut)
def get_parser_config(session: Session = Depends(get_db)):
    seed_default_config(session)
    def cfg(key: str) -> str | None:
        row = session.get(AppConfig, key)
        return row.value if row else None
    return ParserConfigOut(
        ollama_url=cfg(CONFIG_KEY_URL),
        model=cfg(CONFIG_KEY_MODEL),
        min_note_length=int(cfg(CONFIG_KEY_MIN_LENGTH) or 20),
        system_prompt=cfg(CONFIG_KEY_PROMPT),
    )


@parser_router.post("/config", response_model=ParserConfigOut)
def save_parser_config(
    body: ParserConfigIn,
    session: Session = Depends(get_db),
):
    seed_default_config(session)
    updates = {
        CONFIG_KEY_URL: body.ollama_url,
        CONFIG_KEY_MODEL: body.model,
        CONFIG_KEY_MIN_LENGTH: str(body.min_note_length) if body.min_note_length else None,
        CONFIG_KEY_PROMPT: body.system_prompt,
    }
    for key, value in updates.items():
        if value is not None:
            _set_cfg(session, key, value)
    session.commit()
    return get_parser_config(session)
