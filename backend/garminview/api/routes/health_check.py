from fastapi import APIRouter, Depends, Query
from datetime import date, datetime, timezone, timedelta
from typing import Annotated
from collections import defaultdict
from sqlalchemy.orm import Session

from garminview.models.health import DailySummary, Sleep
from garminview.models.monitoring import MonitoringHeartRate
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


@router.get("/intraday-hr")
def intraday_hr(
    session: Annotated[Session, Depends(get_db)],
    date: date = Query(...),
):
    """Return 5-minute averaged HR for a single day."""
    day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    rows = (
        session.query(MonitoringHeartRate)
        .filter(MonitoringHeartRate.timestamp >= day_start)
        .filter(MonitoringHeartRate.timestamp < day_end)
        .filter(MonitoringHeartRate.hr.isnot(None))
        .order_by(MonitoringHeartRate.timestamp)
        .all()
    )

    # Bucket into 5-min intervals in Python (dialect-agnostic)
    buckets: dict[int, list[int]] = defaultdict(list)
    epoch_start = int(day_start.timestamp())
    for row in rows:
        ts = row.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        slot = (int(ts.timestamp()) - epoch_start) // 300 * 300 + epoch_start
        buckets[slot].append(row.hr)

    return [
        {
            "timestamp": datetime.fromtimestamp(slot, tz=timezone.utc).isoformat(),
            "hr": round(sum(hrs) / len(hrs)),
        }
        for slot, hrs in sorted(buckets.items())
    ]
