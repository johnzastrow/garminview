from datetime import date
from sqlalchemy.orm import Session
import pandas as pd
from garminview.models.health import DailySummary, Sleep
from garminview.models.derived import DailyDerived


def get_daily_summary_df(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.query(DailySummary).filter(
        DailySummary.date >= start, DailySummary.date <= end
    ).order_by(DailySummary.date).all()
    return pd.DataFrame([{c.key: getattr(r, c.key)
                          for c in DailySummary.__table__.columns} for r in rows])


def get_training_load_df(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.query(DailyDerived).filter(
        DailyDerived.date >= start, DailyDerived.date <= end
    ).order_by(DailyDerived.date).all()
    return pd.DataFrame([{"date": r.date, "atl": r.atl, "ctl": r.ctl,
                          "tsb": r.tsb, "acwr": r.acwr} for r in rows])


def get_sleep_df(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.query(Sleep).filter(
        Sleep.date >= start, Sleep.date <= end
    ).order_by(Sleep.date).all()
    return pd.DataFrame([{c.key: getattr(r, c.key)
                          for c in Sleep.__table__.columns} for r in rows])
