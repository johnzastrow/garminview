from fastapi import APIRouter, Depends, Query
from datetime import date
from typing import Annotated
from sqlalchemy.orm import Session

from garminview.models.health import Weight
from garminview.models.supplemental import BodyComposition
from garminview.api.schemas.body import WeightResponse, BodyCompositionResponse
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/weight", response_model=list[WeightResponse])
def weight_trend(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(Weight)
    if start:
        q = q.filter(Weight.date >= start)
    if end:
        q = q.filter(Weight.date <= end)
    return q.order_by(Weight.date).all()


@router.get("/composition", response_model=list[BodyCompositionResponse])
def body_composition(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(BodyComposition)
    if start:
        q = q.filter(BodyComposition.date >= start)
    if end:
        q = q.filter(BodyComposition.date <= end)
    return q.order_by(BodyComposition.date).all()
