from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from typing import Annotated
from sqlalchemy import func
from sqlalchemy.orm import Session

from garminview.models.activities import Activity, ActivityHRZone, StepsActivity
from garminview.api.schemas.activities import ActivityResponse, ActivityDetailResponse
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/", response_model=list[ActivityResponse])
def list_activities(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
    type: str = Query(default=None),
    sport: str = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
):
    q = session.query(Activity)
    if start:
        q = q.filter(Activity.start_time >= str(start))
    if end:
        q = q.filter(Activity.start_time <= str(end))
    if type:
        q = q.filter(Activity.type == type)
    if sport:
        q = q.filter(Activity.sport == sport)
    return q.order_by(Activity.start_time.desc()).offset(offset).limit(limit).all()


@router.get("/hr-zones")
def hr_zones_aggregate(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Return total seconds spent in each HR zone (1–5) across all activities in range."""
    q = (
        session.query(ActivityHRZone.zone, func.sum(ActivityHRZone.time_in_zone_s).label("total_s"))
        .join(Activity, Activity.activity_id == ActivityHRZone.activity_id)
    )
    if start:
        q = q.filter(Activity.start_time >= str(start))
    if end:
        q = q.filter(Activity.start_time <= str(end))
    rows = q.group_by(ActivityHRZone.zone).order_by(ActivityHRZone.zone).all()
    return [{"zone": row.zone, "total_s": int(row.total_s or 0)} for row in rows]


@router.get("/vo2max-trend")
def vo2max_trend(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Return (date, vo2max) pairs from running activities that have a Garmin VO2max estimate."""
    q = (
        session.query(Activity.start_time, StepsActivity.vo2max)
        .join(StepsActivity, StepsActivity.activity_id == Activity.activity_id)
        .filter(StepsActivity.vo2max.isnot(None))
    )
    if start:
        q = q.filter(Activity.start_time >= str(start))
    if end:
        q = q.filter(Activity.start_time <= str(end))
    rows = q.order_by(Activity.start_time).all()
    return [{"date": str(r.start_time)[:10], "vo2max": round(float(r.vo2max), 1)} for r in rows]


@router.get("/{activity_id}", response_model=ActivityDetailResponse)
def get_activity(activity_id: int, session: Annotated[Session, Depends(get_db)]):
    activity = session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity
