from fastapi import APIRouter, Depends, Query
from datetime import date
from typing import Annotated
from sqlalchemy.orm import Session

from garminview.models.health import DailySummary, Sleep
from garminview.api.schemas.health import DailySummaryResponse, SleepResponse
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/")
def health_check():
    return {"status": "ok"}


@router.get("/daily", response_model=list[DailySummaryResponse])
def daily_summaries(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(DailySummary)
    if start:
        q = q.filter(DailySummary.date >= start)
    if end:
        q = q.filter(DailySummary.date <= end)
    return q.order_by(DailySummary.date).all()


@router.get("/sleep", response_model=list[SleepResponse])
def sleep_records(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(Sleep)
    if start:
        q = q.filter(Sleep.date >= start)
    if end:
        q = q.filter(Sleep.date <= end)
    return q.order_by(Sleep.date).all()
