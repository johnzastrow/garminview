from datetime import date, datetime
from sqlalchemy import Date, DateTime, Boolean, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profile"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str | None] = mapped_column(String(128))
    birth_date: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(8))
    height_cm: Mapped[float | None] = mapped_column(Float)
    units: Mapped[str] = mapped_column(String(8), default="metric")


class AppConfig(Base):
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String(16), default="string")
    category: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class SyncSchedule(Base):
    __tablename__ = "sync_schedule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))  # full/incremental/analysis_only
    cron_expression: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime)
    next_run: Mapped[datetime | None] = mapped_column(DateTime)


class GoalBenchmark(Base):
    __tablename__ = "goal_benchmarks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String(64))
    target_value: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), default="user")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class NotificationConfig(Base):
    __tablename__ = "notification_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[str | None] = mapped_column(Text)
