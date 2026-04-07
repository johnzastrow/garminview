from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, String, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class DailySummary(Base):
    __tablename__ = "daily_summary"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    steps: Mapped[int | None] = mapped_column(Integer)
    floors: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    calories_total: Mapped[int | None] = mapped_column(Integer)
    calories_bmr: Mapped[int | None] = mapped_column(Integer)
    calories_active: Mapped[int | None] = mapped_column(Integer)
    hr_avg: Mapped[int | None] = mapped_column(SmallInteger)
    hr_min: Mapped[int | None] = mapped_column(SmallInteger)
    hr_max: Mapped[int | None] = mapped_column(SmallInteger)
    hr_resting: Mapped[int | None] = mapped_column(SmallInteger)
    stress_avg: Mapped[int | None] = mapped_column(SmallInteger)
    body_battery_max: Mapped[int | None] = mapped_column(SmallInteger)
    body_battery_min: Mapped[int | None] = mapped_column(SmallInteger)
    spo2_avg: Mapped[float | None] = mapped_column(Float)
    respiration_avg: Mapped[float | None] = mapped_column(Float)
    hydration_intake_ml: Mapped[int | None] = mapped_column(Integer)
    hydration_goal_ml: Mapped[int | None] = mapped_column(Integer)
    intensity_min_moderate: Mapped[int | None] = mapped_column(Integer)
    intensity_min_vigorous: Mapped[int | None] = mapped_column(Integer)
    sleep_score: Mapped[int | None] = mapped_column(SmallInteger)


class Sleep(Base):
    __tablename__ = "sleep"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)
    total_sleep_min: Mapped[int | None] = mapped_column(Integer)
    deep_sleep_min: Mapped[int | None] = mapped_column(Integer)
    light_sleep_min: Mapped[int | None] = mapped_column(Integer)
    rem_sleep_min: Mapped[int | None] = mapped_column(Integer)
    awake_min: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(SmallInteger)
    qualifier: Mapped[str | None] = mapped_column(String(32))
    avg_spo2: Mapped[float | None] = mapped_column(Float)
    avg_respiration: Mapped[float | None] = mapped_column(Float)
    avg_stress: Mapped[int | None] = mapped_column(SmallInteger)


class SleepEvent(Base):
    __tablename__ = "sleep_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    event_type: Mapped[str] = mapped_column(String(16))  # deep/light/rem/awake
    start: Mapped[datetime | None] = mapped_column(DateTime)
    duration_min: Mapped[int | None] = mapped_column(Integer)


class Weight(Base):
    __tablename__ = "weight"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    weight_kg: Mapped[float | None] = mapped_column(Float)


class Stress(Base):
    __tablename__ = "stress"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    stress_level: Mapped[int | None] = mapped_column(SmallInteger)


class RestingHeartRate(Base):
    __tablename__ = "resting_heart_rate"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    resting_hr: Mapped[int | None] = mapped_column(SmallInteger)


class DailyHRZones(Base):
    __tablename__ = "daily_hr_zones"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    z1_min: Mapped[int | None] = mapped_column(SmallInteger)
    z2_min: Mapped[int | None] = mapped_column(SmallInteger)
    z3_min: Mapped[int | None] = mapped_column(SmallInteger)
    z4_min: Mapped[int | None] = mapped_column(SmallInteger)
    z5_min: Mapped[int | None] = mapped_column(SmallInteger)
    valid_max_hr: Mapped[int | None] = mapped_column(SmallInteger)
    raw_max_hr: Mapped[int | None] = mapped_column(SmallInteger)
    rejected_count: Mapped[int | None] = mapped_column(SmallInteger)
    total_count: Mapped[int | None] = mapped_column(SmallInteger)
    zone_method: Mapped[str | None] = mapped_column(String(20))
    computed_at: Mapped[datetime | None] = mapped_column(DateTime)
