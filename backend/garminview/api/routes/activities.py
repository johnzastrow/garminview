from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from typing import Annotated
from sqlalchemy.orm import Session

from garminview.models.activities import Activity
from garminview.api.schemas.activities import ActivityResponse, ActivityDetailResponse
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/", response_model=list[ActivityResponse])
def list_activities(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
    type: str = Query(default=None),
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
    return q.order_by(Activity.start_time.desc()).offset(offset).limit(limit).all()


@router.get("/{activity_id}", response_model=ActivityDetailResponse)
def get_activity(activity_id: int, session: Annotated[Session, Depends(get_db)]):
    activity = session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity
