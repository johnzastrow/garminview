import csv
import io
import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from garminview.api.deps import get_db
from garminview.models.health import DailySummary, Sleep, Weight
from garminview.models.activities import Activity
from garminview.models.derived import DailyDerived

router = APIRouter(prefix="/export", tags=["export"])

_METRIC_MODELS: dict[str, Any] = {
    "daily_summary": DailySummary,
    "sleep": Sleep,
    "weight": Weight,
    "activities": Activity,
    "training_load": DailyDerived,
}


def _query_metric(session: Session, metric: str, start: date, end: date) -> list[dict]:
    model = _METRIC_MODELS.get(metric)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'. Valid: {list(_METRIC_MODELS)}")
    date_col = model.date if hasattr(model, "date") else None
    if date_col is None:
        raise HTTPException(status_code=400, detail=f"Model {metric} has no date column for filtering")
    rows = session.query(model).filter(date_col >= start, date_col <= end).all()
    return [{c.key: getattr(r, c.key) for c in model.__table__.columns} for r in rows]


@router.get("/csv")
def export_csv(
    start: date,
    end: date,
    metrics: str = "daily_summary",
    session: Session = Depends(get_db),
):
    rows = _query_metric(session, metrics, start, end)
    if not rows:
        return StreamingResponse(iter([""]), media_type="text/csv")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={metrics}_{start}_{end}.csv"},
    )


@router.get("/json")
def export_json(
    start: date,
    end: date,
    metrics: str = "daily_summary",
    session: Session = Depends(get_db),
):
    rows = _query_metric(session, metrics, start, end)
    # Convert date/datetime objects for JSON serialisation
    serialisable = [{k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                     for k, v in row.items()} for row in rows]
    payload = json.dumps(serialisable, indent=2)
    return StreamingResponse(
        iter([payload]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={metrics}_{start}_{end}.json"},
    )
