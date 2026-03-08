from datetime import date
from sqlalchemy import Date, Float, Integer, SmallInteger, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class DailyDerived(Base):
    __tablename__ = "daily_derived"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    trimp: Mapped[float | None] = mapped_column(Float)
    atl: Mapped[float | None] = mapped_column(Float)
    ctl: Mapped[float | None] = mapped_column(Float)
    tsb: Mapped[float | None] = mapped_column(Float)
    acwr: Mapped[float | None] = mapped_column(Float)
    monotony: Mapped[float | None] = mapped_column(Float)
    strain: Mapped[float | None] = mapped_column(Float)
    sleep_efficiency_pct: Mapped[float | None] = mapped_column(Float)
    sleep_debt_min: Mapped[float | None] = mapped_column(Float)
    sleep_sri: Mapped[float | None] = mapped_column(Float)
    social_jet_lag_h: Mapped[float | None] = mapped_column(Float)
    lbm_kg: Mapped[float | None] = mapped_column(Float)
    ffmi: Mapped[float | None] = mapped_column(Float)
    body_recomp_index: Mapped[float | None] = mapped_column(Float)
    weight_velocity: Mapped[float | None] = mapped_column(Float)
    readiness_composite: Mapped[float | None] = mapped_column(Float)
    wellness_score: Mapped[float | None] = mapped_column(Float)
    overtraining_risk: Mapped[int | None] = mapped_column(SmallInteger)
    injury_risk: Mapped[float | None] = mapped_column(Float)


class WeeklyDerived(Base):
    __tablename__ = "weekly_derived"
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    atl_avg: Mapped[float | None] = mapped_column(Float)
    ctl_avg: Mapped[float | None] = mapped_column(Float)
    tsb_avg: Mapped[float | None] = mapped_column(Float)
    weekly_load: Mapped[float | None] = mapped_column(Float)
    polarized_z1_pct: Mapped[float | None] = mapped_column(Float)
    polarized_z2_pct: Mapped[float | None] = mapped_column(Float)
    polarized_z3_pct: Mapped[float | None] = mapped_column(Float)
    intensity_min_mod: Mapped[int | None] = mapped_column(Integer)
    intensity_min_vig: Mapped[int | None] = mapped_column(Integer)


class ActivityDerived(Base):
    __tablename__ = "activity_derived"
    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    efficiency_factor: Mapped[float | None] = mapped_column(Float)
    pace_decoupling_pct: Mapped[float | None] = mapped_column(Float)
    cardiac_drift_pct: Mapped[float | None] = mapped_column(Float)
    hr_recovery_1min: Mapped[int | None] = mapped_column(SmallInteger)
    hr_recovery_2min: Mapped[int | None] = mapped_column(SmallInteger)
