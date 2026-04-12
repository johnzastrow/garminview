from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from datetime import datetime, timezone
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from garminview.models.config import AppConfig, SyncSchedule, UserProfile
from garminview.models.assessments import DataQualityFlag
from garminview.models.actalog import ActalogNoteParse
from garminview.analysis.athlete_metrics import compute_athlete_metrics
from garminview.models.sync import SyncLog, SchemaVersion
from garminview.api.deps import get_db
from garminview.api.schemas.admin import TaskItem

import logging
_log = logging.getLogger(__name__)


def _migrate_anomaly_columns(session: Session) -> None:
    """Add anomaly exclusion columns to data_quality_flags if not present."""
    try:
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(session.bind)
        existing = {c["name"] for c in inspector.get_columns("data_quality_flags")}
        with session.connection() as conn:
            if "source_table" not in existing:
                conn.execute(text("ALTER TABLE data_quality_flags ADD COLUMN source_table VARCHAR(64)"))
            if "record_id" not in existing:
                conn.execute(text("ALTER TABLE data_quality_flags ADD COLUMN record_id VARCHAR(128)"))
            if "excluded" not in existing:
                conn.execute(text("ALTER TABLE data_quality_flags ADD COLUMN excluded BOOLEAN NOT NULL DEFAULT 0"))
        session.commit()
    except Exception:
        session.rollback()

def _migrate_mfp_food_diary_columns(session: Session) -> None:
    """Lazy migration: create all MFP tables if absent, add extended macro columns to mfp_food_diary."""
    try:
        from garminview.models.nutrition import (
            MFPDailyNutrition, MFPFoodDiaryEntry, MFPMeasurement, MFPExercise,
        )
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(session.bind)
        existing_tables = set(inspector.get_table_names())
        added = []

        # Create any missing MFP tables (idempotent via checkfirst=True)
        with session.connection() as conn:
            for model, tname in [
                (MFPDailyNutrition, "mfp_daily_nutrition"),
                (MFPFoodDiaryEntry, "mfp_food_diary"),
                (MFPMeasurement, "mfp_measurements"),
                (MFPExercise, "mfp_exercises"),
            ]:
                if tname not in existing_tables:
                    model.__table__.create(conn, checkfirst=True)
                    added.append(f"table:{tname}")
                elif tname == "mfp_measurements":
                    # Detect GarminDB-schema table (has BodyFat_Perc instead of name)
                    existing_col_names = {c["name"] for c in inspector.get_columns(tname)}
                    if "name" not in existing_col_names:
                        conn.execute(text("DROP TABLE mfp_measurements"))
                        MFPMeasurement.__table__.create(conn, checkfirst=True)
                        added.append("table:mfp_measurements_recreated")

            # Add extended macro columns to mfp_food_diary if absent
            existing_cols = {c["name"] for c in inspector.get_columns("mfp_food_diary")}
            for col, definition in [
                ("sodium_mg", "FLOAT"),
                ("sugar_g", "FLOAT"),
                ("fiber_g", "FLOAT"),
                ("cholesterol_mg", "FLOAT"),
            ]:
                if col not in existing_cols:
                    conn.execute(text(f"ALTER TABLE mfp_food_diary ADD COLUMN {col} {definition}"))
                    added.append(col)

        if added:
            session.add(SchemaVersion(
                version="mfp_upload_v1",
                description=f"MFP upload migration: added {', '.join(added)}",
                applied_at=datetime.now(timezone.utc),
                applied_by="mfp_upload",
            ))
        session.commit()
    except Exception:
        session.rollback()


def _bulk_insert(session: Session, model, rows: list, dialect: str) -> None:
    """Insert rows in 500-row batches (for autoincrement-PK tables)."""
    _BATCH = 500
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _ins
        else:
            from sqlalchemy.dialects.mysql import insert as _ins
        session.execute(_ins(model).values(batch))


def _upsert(session: Session, model, rows: list, pk_cols: list[str], dialect: str) -> None:
    """Upsert rows in 500-row batches (for natural-PK tables)."""
    _BATCH = 500
    for i in range(0, len(rows), _BATCH):
        batch = rows[i:i + _BATCH]
        non_pk = [c for c in batch[0] if c not in pk_cols]
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _ins
            stmt = _ins(model).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=pk_cols,
                set_={c: getattr(stmt.excluded, c) for c in non_pk},
            )
        else:
            from sqlalchemy.dialects.mysql import insert as _ins
            stmt = _ins(model).values(batch)
            stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_pk})
        session.execute(stmt)


router = APIRouter()


@router.get("/config")
def get_all_config(session: Annotated[Session, Depends(get_db)]):
    rows = session.query(AppConfig).order_by(AppConfig.category, AppConfig.key).all()
    return {"config": [{"key": r.key, "value": r.value, "category": r.category} for r in rows]}


@router.put("/config/{key}")
def update_config(key: str, value: Annotated[str, Body()], session: Annotated[Session, Depends(get_db)]):
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


@router.post("/schedules")
def create_schedule(source: str, cron: str,
                    session: Annotated[Session, Depends(get_db)],
                    enabled: bool = True):
    if source not in ("garminview", "actalog"):
        raise HTTPException(400, "source must be 'garminview' or 'actalog'")
    row = SyncSchedule(source=source, mode="full", cron_expression=cron, enabled=enabled)
    session.add(row)
    session.commit()
    from garminview.core.startup import reload_schedule
    reload_schedule(row.id, session)
    return {"id": row.id, "source": source, "cron": cron, "enabled": enabled}


@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, cron: str, enabled: bool,
                    session: Annotated[Session, Depends(get_db)]):
    row = session.get(SyncSchedule, schedule_id)
    if not row:
        raise HTTPException(404, "Schedule not found")
    row.cron_expression = cron
    row.enabled = enabled
    session.commit()
    from garminview.core.startup import reload_schedule
    reload_schedule(schedule_id, session)
    return {"id": schedule_id, "cron": cron, "enabled": enabled}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, session: Annotated[Session, Depends(get_db)]):
    row = session.get(SyncSchedule, schedule_id)
    if not row:
        raise HTTPException(404, "Schedule not found")
    # Disable in scheduler first
    row.enabled = False
    session.commit()
    from garminview.core.startup import reload_schedule
    reload_schedule(schedule_id, session)
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.get("/schema-version")
def schema_version(session: Annotated[Session, Depends(get_db)]):
    latest = session.query(SchemaVersion).order_by(SchemaVersion.applied_at.desc()).first()
    return {"version": latest.version if latest else None}


@router.get("/sync-logs")
def sync_logs(session: Annotated[Session, Depends(get_db)], limit: int = 20):
    rows = session.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit).all()
    return {"logs": [{"id": r.id, "source": r.source, "status": r.status,
                      "started_at": r.started_at, "records_upserted": r.records_upserted} for r in rows]}


@router.get("/profile")
def get_profile(session: Annotated[Session, Depends(get_db)]):
    p = session.query(UserProfile).first()
    if not p:
        return {}
    return {
        "name": p.name,
        "birth_date": str(p.birth_date) if p.birth_date else None,
        "sex": p.sex,
        "height_cm": p.height_cm,
        "weight_kg": p.weight_kg,
        "resting_hr": p.resting_hr,
        "max_hr_override": p.max_hr_override,
        "units": p.units,
    }


@router.put("/profile")
def update_profile(
    session: Annotated[Session, Depends(get_db)],
    name: str | None = None,
    birth_date: str | None = None,
    sex: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    resting_hr: int | None = None,
    max_hr_override: int | None = None,
):
    p = session.query(UserProfile).first()
    if not p:
        p = UserProfile(id=1)
        session.add(p)
    if name is not None: p.name = name
    if birth_date is not None:
        from datetime import date as _date
        p.birth_date = _date.fromisoformat(birth_date)
    if sex is not None: p.sex = sex
    if height_cm is not None: p.height_cm = height_cm
    if weight_kg is not None: p.weight_kg = weight_kg
    if resting_hr is not None: p.resting_hr = resting_hr
    if max_hr_override is not None: p.max_hr_override = max_hr_override if max_hr_override > 0 else None
    session.commit()

    # If HR-relevant fields changed, recompute zone data for the last 90 days
    if resting_hr is not None or max_hr_override is not None:
        try:
            from datetime import date, timedelta
            from garminview.analysis.hr_zones import compute_daily_hr_zones
            today = date.today()
            cutoff = today - timedelta(days=90)
            dates = [cutoff + timedelta(days=i) for i in range((today - cutoff).days + 1)]
            compute_daily_hr_zones(session, dates)
        except Exception as exc:
            _log.warning("HR zones recompute after profile update failed: %s", exc)

    return get_profile(session)


@router.get("/athlete-metrics")
def athlete_metrics(session: Annotated[Session, Depends(get_db)]):
    from datetime import timedelta
    from sqlalchemy import func
    from garminview.models.monitoring import MonitoringHeartRate
    from garminview.models.activities import Activity

    # Time windows for measured data — use recent data to reflect current fitness
    MAX_HR_WINDOW_DAYS = 365     # 12 months: HRmax declines ~0.7 bpm/yr with age
    VO2MAX_RUN_WINDOW_DAYS = 180 # 6 months: aerobic fitness changes across training seasons
    max_hr_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=MAX_HR_WINDOW_DAYS)
    run_cutoff    = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=VO2MAX_RUN_WINDOW_DAYS)

    p = session.query(UserProfile).first()
    if not p:
        return {"error": "No profile data. Set birth_date to enable metrics."}

    # Fetch excluded record IDs for each table
    excluded_mhr = session.query(DataQualityFlag.record_id).filter(
        DataQualityFlag.flag_type == "user_exclusion",
        DataQualityFlag.source_table == "monitoring_heart_rate",
    ).all()
    excluded_mhr_ids = [r[0] for r in excluded_mhr]

    excluded_act = session.query(DataQualityFlag.record_id).filter(
        DataQualityFlag.flag_type == "user_exclusion",
        DataQualityFlag.source_table == "activities",
    ).all()
    excluded_act_ids = [r[0] for r in excluded_act]

    # Measured max HR — last 12 months, plausible range, excluding flagged records
    mhr_q = session.query(func.max(MonitoringHeartRate.hr)).filter(
        MonitoringHeartRate.hr < 220,
        MonitoringHeartRate.timestamp >= max_hr_cutoff,
    )
    if excluded_mhr_ids:
        from sqlalchemy import cast, String
        mhr_q = mhr_q.filter(
            ~func.cast(MonitoringHeartRate.timestamp, String).in_(excluded_mhr_ids)
        )
    measured_mon = mhr_q.scalar()

    act_q = session.query(func.max(Activity.max_hr)).filter(
        Activity.max_hr < 220,
        Activity.start_time >= max_hr_cutoff,
    )
    if excluded_act_ids:
        act_q = act_q.filter(~Activity.activity_id.in_([int(i) for i in excluded_act_ids if i and i.isdigit()]))
    measured_act = act_q.scalar()

    # Running-based VO2max — best steady-state run in last 6 months (20+ min, submaximal HR)
    running_vo2max = None
    best_run_date = None
    if p.resting_hr and p.birth_date:
        from garminview.analysis.athlete_metrics import calc_age, calc_max_hr_methods
        age = calc_age(p.birth_date)
        max_hr_for_calc, _, _ = calc_max_hr_methods(age, p.sex or "male", p.max_hr_override)

        hr_lo = round(max_hr_for_calc * 0.60)
        hr_hi = round(max_hr_for_calc * 0.90)
        best_run = (
            session.query(Activity)
            .filter(Activity.sport.in_(["running", "trail_running", "treadmill_running"]))
            .filter(Activity.avg_hr.between(hr_lo, hr_hi))
            .filter(Activity.avg_speed.isnot(None))
            .filter(Activity.elapsed_time_s >= 1200)
            .filter(Activity.start_time >= run_cutoff)
            .order_by(Activity.avg_speed.desc())
            .first()
        )
        if best_run and best_run.avg_speed:
            speed_m_min = best_run.avg_speed * 60
            vo2_at_speed = 0.2 * speed_m_min + 3.5
            hrr_fraction = (best_run.avg_hr - p.resting_hr) / (max_hr_for_calc - p.resting_hr)
            if 0.2 < hrr_fraction < 1.0:
                running_vo2max = vo2_at_speed / hrr_fraction
                best_run_date = best_run.start_time.date().isoformat() if best_run.start_time else None

    # Garmin device VO2max — read from GarminDB SQLite (steps_activities.vo2_max)
    garmin_vo2max = None
    garmin_vo2max_date = None
    try:
        from garminview.core.config import get_config as _get_config
        import sqlite3 as _sqlite3, os as _os
        _cfg = _get_config()
        _gdb = _os.path.join(_os.path.expanduser(_cfg.health_data_dir), "DBs", "garmin_activities.db")
        if _os.path.exists(_gdb):
            _conn = _sqlite3.connect(_gdb)
            _cutoff_str = max_hr_cutoff.strftime("%Y-%m-%d %H:%M:%S")
            row = _conn.execute("""
                SELECT s.vo2_max, a.start_time
                FROM steps_activities s
                JOIN activities a ON a.activity_id = s.activity_id
                WHERE s.vo2_max IS NOT NULL AND a.start_time >= ?
                ORDER BY a.start_time DESC LIMIT 1
            """, (_cutoff_str,)).fetchone()
            _conn.close()
            if row:
                garmin_vo2max = float(row[0])
                garmin_vo2max_date = str(row[1])[:10]
    except Exception:
        pass

    m = compute_athlete_metrics(
        p,
        measured_max_hr_monitoring=measured_mon,
        measured_max_hr_activities=measured_act,
        running_vo2max=running_vo2max,
        garmin_vo2max=garmin_vo2max,
    )
    if not m:
        return {"error": "No profile data. Set birth_date to enable metrics."}

    def method_to_dict(mv):
        return {"method": mv.method, "label": mv.label, "value": mv.value,
                "recommended": mv.recommended, "note": mv.note}

    return {
        "age": m.age,
        "sex": m.sex,
        "resting_hr": m.resting_hr,
        "weight_kg": m.weight_kg,
        "height_cm": m.height_cm,
        "bmr": m.bmr,
        "max_hr": m.max_hr,
        "max_hr_source": m.max_hr_source,
        "max_hr_methods": [method_to_dict(mv) for mv in m.max_hr_methods],
        "vo2max_estimate": m.vo2max_estimate,
        "vo2max_methods": [method_to_dict(mv) for mv in m.vo2max_methods],
        "fitness_age": m.fitness_age,
        "fitness_age_methods": [method_to_dict(mv) for mv in m.fitness_age_methods],
        "hr_zones_method": m.hr_zones_method,
        "hr_zones": [{"zone": z.zone, "name": z.name, "min_bpm": z.min_bpm,
                      "max_bpm": z.max_bpm, "description": z.description}
                     for z in m.hr_zones],
        "data_windows": {
            "max_hr_days": MAX_HR_WINDOW_DAYS,
            "vo2max_run_days": VO2MAX_RUN_WINDOW_DAYS,
            "best_run_date": best_run_date,
            "measured_mon_hr": measured_mon,
            "measured_act_hr": measured_act,
            "garmin_vo2max": garmin_vo2max,
            "garmin_vo2max_date": garmin_vo2max_date,
        },
    }


@router.get("/anomalies")
def list_anomalies(session: Annotated[Session, Depends(get_db)]):
    """Scan data for sensor spikes and physiological anomalies."""
    _migrate_anomaly_columns(session)

    from garminview.models.monitoring import MonitoringHeartRate
    from garminview.models.activities import Activity
    from garminview.models.health import DailySummary

    # Build exclusion lookup: (source_table, record_id) → flag_id
    exclusions = session.query(DataQualityFlag).filter(
        DataQualityFlag.flag_type == "user_exclusion"
    ).all()
    excluded_set = {(f.source_table, f.record_id): f.id for f in exclusions}

    anomalies = []

    # 1. Monitoring HR spikes (> 210 bpm — above any recorded human max)
    spikes = (
        session.query(MonitoringHeartRate)
        .filter(MonitoringHeartRate.hr > 210)
        .order_by(MonitoringHeartRate.timestamp.desc())
        .limit(200)
        .all()
    )
    for row in spikes:
        rid = row.timestamp.isoformat()
        key = ("monitoring_heart_rate", rid)
        anomalies.append({
            "anomaly_id": f"mhr_{rid}",
            "source_table": "monitoring_heart_rate",
            "record_id": rid,
            "date": row.timestamp.date().isoformat(),
            "metric": "heart_rate",
            "value": row.hr,
            "anomaly_type": "sensor_spike",
            "severity": "high",
            "message": f"HR {row.hr} bpm exceeds physiological maximum (210 bpm threshold)",
            "excluded": key in excluded_set,
            "flag_id": excluded_set.get(key),
        })

    # 2. Activity max_hr > 220 (impossible — clear sensor artifact)
    bad_acts = (
        session.query(Activity)
        .filter(Activity.max_hr > 220, Activity.max_hr.isnot(None))
        .order_by(Activity.start_time.desc())
        .limit(100)
        .all()
    )
    for row in bad_acts:
        rid = str(row.activity_id)
        key = ("activities", rid)
        date_str = row.start_time.date().isoformat() if row.start_time else "unknown"
        anomalies.append({
            "anomaly_id": f"act_{rid}",
            "source_table": "activities",
            "record_id": rid,
            "date": date_str,
            "metric": "activity_max_hr",
            "value": row.max_hr,
            "anomaly_type": "sensor_spike",
            "severity": "high",
            "message": f"Activity max HR {row.max_hr} bpm exceeds 220 bpm (activity: {row.name or rid})",
            "excluded": key in excluded_set,
            "flag_id": excluded_set.get(key),
        })

    # 3. Activity max_hr implausibly high (> Tanaka estimate + 25 bpm) if profile available
    p = session.query(UserProfile).first()
    if p and p.birth_date:
        from garminview.analysis.athlete_metrics import calc_age
        age = calc_age(p.birth_date)
        tanaka = round(208 - 0.7 * age)
        threshold = tanaka + 25
        suspicious_acts = (
            session.query(Activity)
            .filter(Activity.max_hr > threshold, Activity.max_hr <= 220, Activity.max_hr.isnot(None))
            .order_by(Activity.start_time.desc())
            .limit(100)
            .all()
        )
        for row in suspicious_acts:
            rid = str(row.activity_id)
            key = ("activities", rid)
            if key not in {("activities", str(a.activity_id)) for a in bad_acts}:
                date_str = row.start_time.date().isoformat() if row.start_time else "unknown"
                anomalies.append({
                    "anomaly_id": f"act_{rid}",
                    "source_table": "activities",
                    "record_id": rid,
                    "date": date_str,
                    "metric": "activity_max_hr",
                    "value": row.max_hr,
                    "anomaly_type": "implausible",
                    "severity": "medium",
                    "message": f"Activity max HR {row.max_hr} bpm is {row.max_hr - tanaka} bpm above Tanaka estimate ({tanaka} bpm) for age {age}",
                    "excluded": key in excluded_set,
                    "flag_id": excluded_set.get(key),
                })

    # 4. Daily steps > 80,000 (extreme outlier — likely device glitch)
    high_steps = (
        session.query(DailySummary)
        .filter(DailySummary.steps > 80000)
        .order_by(DailySummary.date.desc())
        .limit(50)
        .all()
    )
    for row in high_steps:
        rid = str(row.date)
        key = ("daily_summary", rid)
        anomalies.append({
            "anomaly_id": f"steps_{rid}",
            "source_table": "daily_summary",
            "record_id": rid,
            "date": rid,
            "metric": "steps",
            "value": row.steps,
            "anomaly_type": "implausible",
            "severity": "medium",
            "message": f"{row.steps:,} steps on {rid} exceeds physiologically plausible daily maximum (80,000)",
            "excluded": key in excluded_set,
            "flag_id": excluded_set.get(key),
        })

    # Sort by date descending
    anomalies.sort(key=lambda a: a["date"], reverse=True)
    return {"anomalies": anomalies, "total": len(anomalies)}


@router.post("/anomalies/exclude")
def exclude_anomaly(
    session: Annotated[Session, Depends(get_db)],
    source_table: str,
    record_id: str,
    date: str,
    metric: str,
    value: str,
    message: str = "",
):
    """Mark an anomaly as user-excluded."""
    _migrate_anomaly_columns(session)
    from datetime import date as _date

    # Idempotent: don't create duplicate exclusions
    existing = session.query(DataQualityFlag).filter(
        DataQualityFlag.flag_type == "user_exclusion",
        DataQualityFlag.source_table == source_table,
        DataQualityFlag.record_id == record_id,
    ).first()
    if existing:
        return {"id": existing.id, "excluded": True}

    flag = DataQualityFlag(
        date=_date.fromisoformat(date),
        metric=metric,
        flag_type="user_exclusion",
        value=str(value),
        message=message,
        source_table=source_table,
        record_id=record_id,
        excluded=True,
    )
    session.add(flag)
    session.commit()
    session.refresh(flag)
    return {"id": flag.id, "excluded": True}


@router.delete("/anomalies/exclude")
def include_anomaly(
    session: Annotated[Session, Depends(get_db)],
    source_table: str,
    record_id: str,
):
    """Remove a user exclusion for an anomaly."""
    _migrate_anomaly_columns(session)

    flag = session.query(DataQualityFlag).filter(
        DataQualityFlag.flag_type == "user_exclusion",
        DataQualityFlag.source_table == source_table,
        DataQualityFlag.record_id == record_id,
    ).first()
    if flag:
        session.delete(flag)
        session.commit()
    return {"excluded": False}


@router.post("/upload/mfp")
async def upload_mfp(
    session: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload a MyFitnessPal export ZIP and upsert all data into the DB."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="File must be a .zip")

    data = await file.read()

    from garminview.ingestion.mfp_zip_parser import parse_mfp_zip, ParseResult, MFPNoFilesError
    try:
        result: ParseResult = parse_mfp_zip(data)
    except MFPNoFilesError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    _migrate_mfp_food_diary_columns(session)

    dialect = session.bind.dialect.name
    start, end = result.min_date, result.max_date

    # mfp_food_diary: delete range then reinsert (autoincrement PK)
    if result.food_diary and start and end:
        session.execute(text("DELETE FROM mfp_food_diary WHERE date >= :s AND date <= :e"),
                        {"s": start, "e": end})
        from garminview.models.nutrition import MFPFoodDiaryEntry
        _bulk_insert(session, MFPFoodDiaryEntry, result.food_diary, dialect)

    # mfp_exercises: delete range then reinsert (autoincrement PK)
    if result.exercises and start and end:
        session.execute(text("DELETE FROM mfp_exercises WHERE date >= :s AND date <= :e"),
                        {"s": start, "e": end})
        from garminview.models.nutrition import MFPExercise
        _bulk_insert(session, MFPExercise, result.exercises, dialect)

    # mfp_daily_nutrition: upsert by date (natural PK)
    if result.nutrition_daily:
        from garminview.models.nutrition import MFPDailyNutrition
        _upsert(session, MFPDailyNutrition, result.nutrition_daily, ["date"], dialect)

    # mfp_measurements: upsert by (date, name) (natural PK)
    if result.measurements:
        from garminview.models.nutrition import MFPMeasurement
        _upsert(session, MFPMeasurement, result.measurements, ["date", "name"], dialect)

    session.commit()

    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    backfill = backfill_mfp_to_main(session)
    session.commit()

    return {
        "nutrition_days": len(result.nutrition_daily),
        "food_diary_rows": len(result.food_diary),
        "measurements": len(result.measurements),
        "exercises": len(result.exercises),
        "backfill": backfill,
        "errors": [{"file": e.file, "row": e.row, "message": e.message} for e in result.errors],
    }


@router.post("/import/polar")
def import_polar(
    session: Annotated[Session, Depends(get_db)],
    path: str = Body(embed=True),
):
    """Import Polar Flow GDPR export from a filesystem directory.

    Creates all polar_* staging tables if they don't exist, then imports all JSON files.
    """
    import os
    abs_path = os.path.expanduser(path)
    if not os.path.isdir(abs_path):
        raise HTTPException(status_code=400, detail=f"Directory not found: {abs_path}")

    # Ensure polar tables exist
    from garminview.models.polar import Base as PolarBase
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(session.bind)
    existing_tables = set(inspector.get_table_names())
    with session.connection() as conn:
        for table in PolarBase.metadata.sorted_tables:
            if table.name.startswith("polar_") and table.name not in existing_tables:
                table.create(conn, checkfirst=True)
    session.commit()

    from garminview.ingestion.polar.importer import run_import
    return run_import(session, abs_path)


@router.post("/backfill/polar")
def backfill_polar(session: Annotated[Session, Depends(get_db)]):
    """Backfill core tables (activities, sleep, resting_hr, vo2max) from Polar staging data."""
    from garminview.ingestion.polar_backfill import backfill_all_polar
    return backfill_all_polar(session)


@router.post("/backfill/mfp")
def backfill_mfp(session: Annotated[Session, Depends(get_db)]):
    """Cross-populate weight and body_composition from already-uploaded MFP measurements."""
    from garminview.ingestion.mfp_backfill import backfill_mfp_to_main
    result = backfill_mfp_to_main(session)
    session.commit()
    return result


_SOURCE_LABELS: dict[str, str] = {
    "garmin_daily": "Garmin daily sync",
    "garmin_monitoring": "Garmin monitoring sync",
    "actalog": "Actalog sync",
    "hr_zones": "HR zones recompute",
}


@router.get("/tasks", response_model=list[TaskItem])
def get_tasks(
    session: Annotated[Session, Depends(get_db)],
    limit: int = 10,
):
    items: list[TaskItem] = []

    # --- Action items ---

    # Profile setup action
    try:
        p = session.query(UserProfile).first()
        if not p or p.resting_hr is None or p.max_hr_override is None:
            items.append(TaskItem(
                item_type="action",
                action_key="profile_setup",
                title="Set resting HR and max HR",
                detail="Required for heart rate zone analysis",
                link="/profile",
            ))
    except OperationalError:
        _log.warning("user_profile table not ready; skipping profile_setup check")

    # Anomalies action: count live-detected anomalies not yet user-excluded
    try:
        from garminview.models.monitoring import MonitoringHeartRate
        from garminview.models.activities import Activity
        from garminview.models.health import DailySummary as _DailySummary
        from sqlalchemy import func, cast, String

        # Build exclusion sets by source table
        _excl_q = session.query(DataQualityFlag.record_id, DataQualityFlag.source_table).filter(
            DataQualityFlag.flag_type == "user_exclusion"
        ).all()
        excl_mhr = {r[0] for r in _excl_q if r[1] == "monitoring_heart_rate"}
        excl_act = {r[0] for r in _excl_q if r[1] == "activities"}
        excl_daily = {r[0] for r in _excl_q if r[1] == "daily_summary"}

        # Count HR spikes (> 210 bpm) not excluded
        spike_q = session.query(func.count(MonitoringHeartRate.timestamp)).filter(
            MonitoringHeartRate.hr > 210
        )
        if excl_mhr:
            spike_q = spike_q.filter(
                ~cast(MonitoringHeartRate.timestamp, String).in_(excl_mhr)
            )

        # Count activity max_hr > 220 not excluded
        bad_act_q = session.query(func.count(Activity.activity_id)).filter(
            Activity.max_hr > 220,
            Activity.max_hr.isnot(None),
        )
        if excl_act:
            bad_act_q = bad_act_q.filter(
                ~Activity.activity_id.in_(
                    [int(i) for i in excl_act if i and i.isdigit()]
                )
            )

        # Count implausible step counts (> 80,000) not excluded
        high_steps_q = session.query(func.count(_DailySummary.date)).filter(
            _DailySummary.steps > 80000
        )
        if excl_daily:
            high_steps_q = high_steps_q.filter(
                ~cast(_DailySummary.date, String).in_(excl_daily)
            )

        anomaly_count = (
            (spike_q.scalar() or 0)
            + (bad_act_q.scalar() or 0)
            + (high_steps_q.scalar() or 0)
        )
        if anomaly_count > 0:
            items.append(TaskItem(
                item_type="action",
                action_key="anomalies",
                title=f"{anomaly_count} unreviewed data anomalies",
                link="/admin",
                count=anomaly_count,
            ))
    except OperationalError:
        _log.warning("anomaly detection tables not ready; skipping anomaly check")

    # Actalog review action
    try:
        actalog_row = session.get(AppConfig, "actalog_sync_enabled")
        if actalog_row and actalog_row.value and actalog_row.value.lower() in ("1", "true", "yes"):
            pending = session.query(ActalogNoteParse).filter(
                ActalogNoteParse.parse_status == "pending"
            ).count()
            if pending > 0:
                items.append(TaskItem(
                    item_type="action",
                    action_key="actalog_review",
                    title=f"{pending} workout notes awaiting review",
                    link="/actalog",
                    count=pending,
                ))
    except OperationalError:
        _log.warning("actalog tables not ready; skipping actalog_review check")

    # Sync history
    try:
        sync_rows = (
            session.query(SyncLog)
            .order_by(SyncLog.started_at.desc())
            .limit(limit)
            .all()
        )
        for row in sync_rows:
            duration_s = None
            if row.started_at and row.finished_at:
                duration_s = (row.finished_at - row.started_at).total_seconds()
            items.append(TaskItem(
                item_type="sync",
                title=_SOURCE_LABELS.get(row.source, row.source),
                detail=row.error_message[:80] if row.error_message else None,
                timestamp=row.started_at,
                duration_s=duration_s,
                records_upserted=row.records_upserted,
                status=row.status,
            ))
    except OperationalError:
        _log.warning("sync_log table not ready; skipping sync history")

    return items
