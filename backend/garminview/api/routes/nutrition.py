from fastapi import APIRouter, Depends, Query
from datetime import date
from typing import Annotated
from sqlalchemy.orm import Session

from garminview.models.nutrition import MFPDailyNutrition
from garminview.models.health import DailySummary
from garminview.api.schemas.nutrition import MFPNutritionResponse, EnergyBalanceResponse
from garminview.api.deps import get_db

router = APIRouter()


@router.get("/daily", response_model=list[MFPNutritionResponse])
def nutrition_daily(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = session.query(MFPDailyNutrition)
    if start:
        q = q.filter(MFPDailyNutrition.date >= start)
    if end:
        q = q.filter(MFPDailyNutrition.date <= end)
    return q.order_by(MFPDailyNutrition.date).all()


@router.get("/energy-balance", response_model=list[EnergyBalanceResponse])
def energy_balance(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Join MFP calories_in with Garmin calories_total for energy balance per day."""
    nutr_q = session.query(MFPDailyNutrition)
    if start:
        nutr_q = nutr_q.filter(MFPDailyNutrition.date >= start)
    if end:
        nutr_q = nutr_q.filter(MFPDailyNutrition.date <= end)
    nutrition = {r.date: r for r in nutr_q.all()}

    garmin_q = session.query(DailySummary)
    if start:
        garmin_q = garmin_q.filter(DailySummary.date >= start)
    if end:
        garmin_q = garmin_q.filter(DailySummary.date <= end)
    garmin = {r.date: r for r in garmin_q.all()}

    all_dates = sorted(set(nutrition) | set(garmin))
    results = []
    for d in all_dates:
        n = nutrition.get(d)
        g = garmin.get(d)
        cal_in = n.calories_in if n else None
        cal_out = g.calories_total if g else None
        balance = (cal_in - cal_out) if (cal_in is not None and cal_out is not None) else None
        results.append(EnergyBalanceResponse(
            date=d,
            calories_in=cal_in,
            calories_out=cal_out,
            energy_balance=balance,
            protein_g=n.protein_g if n else None,
            carbs_g=n.carbs_g if n else None,
            fat_g=n.fat_g if n else None,
        ))
    return results
