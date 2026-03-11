from fastapi import APIRouter, Depends, Query
from datetime import date
from typing import Annotated
from sqlalchemy.orm import Session

from garminview.models.derived import DailyDerived, MaxHRAgingYear
from garminview.models.supplemental import TrainingReadiness
from garminview.api.schemas.training import TrainingLoadResponse, TrainingReadinessResponse, MaxHRAgingYearResponse
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/load", response_model=list[TrainingLoadResponse])
def training_load(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(DailyDerived)
    if start:
        q = q.filter(DailyDerived.date >= start)
    if end:
        q = q.filter(DailyDerived.date <= end)
    return q.order_by(DailyDerived.date).all()


@router.get("/readiness", response_model=list[TrainingReadinessResponse])
def training_readiness(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(TrainingReadiness)
    if start:
        q = q.filter(TrainingReadiness.date >= start)
    if end:
        q = q.filter(TrainingReadiness.date <= end)
    return q.order_by(TrainingReadiness.date).all()


@router.get("/max-hr-aging", response_model=list[MaxHRAgingYearResponse])
def max_hr_aging(session: Annotated[Session, Depends(get_db)]):
    return session.query(MaxHRAgingYear).order_by(MaxHRAgingYear.year).all()
