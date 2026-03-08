from fastapi import APIRouter, Depends, Query
from datetime import date
from typing import Annotated
from sqlalchemy.orm import Session
from pydantic import BaseModel

from garminview.models.assessments import Assessment, CorrelationResult, DataQualityFlag
from garminview.api.deps import get_db

router = APIRouter()


class AssessmentResponse(BaseModel):
    id: int
    period_type: str
    period_start: date
    category: str
    severity: str
    summary_text: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AssessmentResponse])
def list_assessments(
    session: Annotated[Session, Depends(get_db)],
    period_type: str = Query(default=None),
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(Assessment)
    if period_type:
        q = q.filter(Assessment.period_type == period_type)
    if start:
        q = q.filter(Assessment.period_start >= start)
    if end:
        q = q.filter(Assessment.period_start <= end)
    return q.order_by(Assessment.period_start.desc()).all()


@router.get("/correlations/matrix")
def correlation_matrix(session: Annotated[Session, Depends(get_db)]):
    rows = session.query(CorrelationResult).order_by(CorrelationResult.computed_at.desc()).limit(500).all()
    return {"correlations": [{"metric_a": r.metric_a, "metric_b": r.metric_b,
                               "r_pearson": r.r_pearson, "p_value": r.p_value} for r in rows]}


@router.get("/data-quality/completeness")
def data_quality_completeness(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(DataQualityFlag)
    if start:
        q = q.filter(DataQualityFlag.date >= start)
    if end:
        q = q.filter(DataQualityFlag.date <= end)
    flags = q.all()
    return {"total_flags": len(flags), "flags": [{"date": str(f.date), "metric": f.metric,
                                                   "flag_type": f.flag_type} for f in flags[:50]]}
