from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class HRVData(Base):
    __tablename__ = "hrv_data"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    hrv_rmssd: Mapped[float | None] = mapped_column(Float)
    hrv_5min_high: Mapped[float | None] = mapped_column(Float)
    hrv_5min_low: Mapped[float | None] = mapped_column(Float)
    baseline_low: Mapped[float | None] = mapped_column(Float)
    baseline_high: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(32))


class TrainingReadiness(Base):
    __tablename__ = "training_readiness"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    score: Mapped[int | None] = mapped_column(SmallInteger)
    sleep_score: Mapped[int | None] = mapped_column(SmallInteger)
    recovery_score: Mapped[int | None] = mapped_column(SmallInteger)
    training_load_score: Mapped[int | None] = mapped_column(SmallInteger)
    hrv_score: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str | None] = mapped_column(String(32))


class TrainingStatus(Base):
    __tablename__ = "training_status"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    status: Mapped[str | None] = mapped_column(String(32))
    load_ratio: Mapped[float | None] = mapped_column(Float)


class BodyBatteryEvent(Base):
    __tablename__ = "body_battery_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)
    value: Mapped[int | None] = mapped_column(SmallInteger)
    event_type: Mapped[str | None] = mapped_column(String(16))  # drain/charge
    activity_id: Mapped[int | None] = mapped_column(Integer)


class VO2Max(Base):
    __tablename__ = "vo2max"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    vo2max_running: Mapped[float | None] = mapped_column(Float)
    vo2max_cycling: Mapped[float | None] = mapped_column(Float)
    fitness_age: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[str | None] = mapped_column(String(32))


class RacePrediction(Base):
    __tablename__ = "race_predictions"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    pred_5k_s: Mapped[int | None] = mapped_column(Integer)
    pred_10k_s: Mapped[int | None] = mapped_column(Integer)
    pred_half_s: Mapped[int | None] = mapped_column(Integer)
    pred_full_s: Mapped[int | None] = mapped_column(Integer)


class LactateThreshold(Base):
    __tablename__ = "lactate_threshold"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    lt_speed: Mapped[float | None] = mapped_column(Float)
    lt_hr: Mapped[int | None] = mapped_column(SmallInteger)
    lt_power: Mapped[int | None] = mapped_column(Integer)


class HillScore(Base):
    __tablename__ = "hill_score"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    score: Mapped[float | None] = mapped_column(Float)


class EnduranceScore(Base):
    __tablename__ = "endurance_score"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    score: Mapped[float | None] = mapped_column(Float)


class PersonalRecord(Base):
    __tablename__ = "personal_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_type: Mapped[str | None] = mapped_column(String(64))
    metric: Mapped[str | None] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float)
    achieved_date: Mapped[date | None] = mapped_column(Date)


class BodyComposition(Base):
    __tablename__ = "body_composition"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    fat_pct: Mapped[float | None] = mapped_column(Float)
    muscle_mass_kg: Mapped[float | None] = mapped_column(Float)
    bone_mass_kg: Mapped[float | None] = mapped_column(Float)
    hydration_pct: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    bmr: Mapped[int | None] = mapped_column(Integer)
    metabolic_age: Mapped[int | None] = mapped_column(SmallInteger)
    visceral_fat: Mapped[int | None] = mapped_column(SmallInteger)
    physique_rating: Mapped[int | None] = mapped_column(SmallInteger)
    source: Mapped[str | None] = mapped_column(String(16), default="garmin")


class BloodPressure(Base):
    __tablename__ = "blood_pressure"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    systolic: Mapped[int | None] = mapped_column(SmallInteger)
    diastolic: Mapped[int | None] = mapped_column(SmallInteger)
    pulse: Mapped[int | None] = mapped_column(SmallInteger)


class Gear(Base):
    __tablename__ = "gear"
    gear_uuid: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(16))
    date_begin: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)


class GearStats(Base):
    __tablename__ = "gear_stats"
    gear_uuid: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_distance_m: Mapped[float | None] = mapped_column(Float)
    total_activities: Mapped[int | None] = mapped_column(Integer)
