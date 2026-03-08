from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String(64))
    target_value: Mapped[float] = mapped_column(Float)
    target_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="on_track")


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_type: Mapped[str] = mapped_column(String(16))  # weekly/monthly
    period_start: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))  # info/caution/warning
    summary_text: Mapped[str] = mapped_column(Text)
    supporting_metrics: Mapped[str | None] = mapped_column(Text)  # JSON


class TrendClassification(Base):
    __tablename__ = "trend_classifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(24))
    lookback_days: Mapped[int] = mapped_column(SmallInteger)
    slope: Mapped[float | None] = mapped_column(Float)
    r_squared: Mapped[float | None] = mapped_column(Float)
    p_value: Mapped[float | None] = mapped_column(Float)


class CorrelationResult(Base):
    __tablename__ = "correlation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    metric_a: Mapped[str] = mapped_column(String(64))
    metric_b: Mapped[str] = mapped_column(String(64))
    lag_days: Mapped[int] = mapped_column(SmallInteger, default=0)
    r_pearson: Mapped[float | None] = mapped_column(Float)
    r_spearman: Mapped[float | None] = mapped_column(Float)
    p_value: Mapped[float | None] = mapped_column(Float)
    n_samples: Mapped[int | None] = mapped_column(Integer)


class DataQualityFlag(Base):
    __tablename__ = "data_quality_flags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String(64))
    flag_type: Mapped[str] = mapped_column(String(16))  # missing/implausible/duplicate/gap
    value: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str | None] = mapped_column(Text)
