from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, SmallInteger, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class Activity(Base):
    __tablename__ = "activities"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(256))
    type: Mapped[str | None] = mapped_column(String(64))
    sport: Mapped[str | None] = mapped_column(String(64))
    sub_sport: Mapped[str | None] = mapped_column(String(64))
    start_time: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    elapsed_time_s: Mapped[int | None] = mapped_column(Integer)
    moving_time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)
    avg_hr: Mapped[int | None] = mapped_column(SmallInteger)
    max_hr: Mapped[int | None] = mapped_column(SmallInteger)
    avg_cadence: Mapped[int | None] = mapped_column(SmallInteger)
    avg_speed: Mapped[float | None] = mapped_column(Float)
    ascent_m: Mapped[float | None] = mapped_column(Float)
    descent_m: Mapped[float | None] = mapped_column(Float)
    training_load: Mapped[float | None] = mapped_column(Float)
    aerobic_effect: Mapped[float | None] = mapped_column(Float)
    anaerobic_effect: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(32))  # garmin_fit / garmin_api


class ActivityLap(Base):
    __tablename__ = "activity_laps"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lap_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    elapsed_time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[int | None] = mapped_column(SmallInteger)
    max_hr: Mapped[int | None] = mapped_column(SmallInteger)
    avg_speed: Mapped[float | None] = mapped_column(Float)
    ascent_m: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)


class ActivityRecord(Base):
    __tablename__ = "activity_records"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    hr: Mapped[int | None] = mapped_column(SmallInteger)
    cadence: Mapped[int | None] = mapped_column(SmallInteger)
    altitude_m: Mapped[float | None] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float)
    power: Mapped[int | None] = mapped_column(Integer)


class StepsActivity(Base):
    __tablename__ = "steps_activities"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pace_avg: Mapped[float | None] = mapped_column(Float)
    pace_moving: Mapped[float | None] = mapped_column(Float)
    pace_max: Mapped[float | None] = mapped_column(Float)
    steps_per_min: Mapped[float | None] = mapped_column(Float)
    step_length_m: Mapped[float | None] = mapped_column(Float)
    vertical_oscillation_mm: Mapped[float | None] = mapped_column(Float)
    vertical_ratio_pct: Mapped[float | None] = mapped_column(Float)
    gct_ms: Mapped[float | None] = mapped_column(Float)
    stance_pct: Mapped[float | None] = mapped_column(Float)
    vo2max: Mapped[float | None] = mapped_column(Float)


class ActivityHRZone(Base):
    __tablename__ = "activity_hr_zones"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    zone: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    time_in_zone_s: Mapped[int | None] = mapped_column(Integer)
