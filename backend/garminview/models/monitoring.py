from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class MonitoringHeartRate(Base):
    __tablename__ = "monitoring_heart_rate"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    hr: Mapped[int | None] = mapped_column(SmallInteger)


class MonitoringIntensity(Base):
    __tablename__ = "monitoring_intensity"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    moderate_time_s: Mapped[int | None] = mapped_column(Integer)
    vigorous_time_s: Mapped[int | None] = mapped_column(Integer)


class MonitoringSteps(Base):
    __tablename__ = "monitoring_steps"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    steps: Mapped[int | None] = mapped_column(Integer)
    activity_type: Mapped[str | None] = mapped_column(String(32))


class MonitoringRespiration(Base):
    __tablename__ = "monitoring_respiration"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    rr: Mapped[float | None] = mapped_column(Float)


class MonitoringPulseOx(Base):
    __tablename__ = "monitoring_pulse_ox"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    spo2: Mapped[float | None] = mapped_column(Float)


class MonitoringClimb(Base):
    __tablename__ = "monitoring_climb"
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    ascent_m: Mapped[float | None] = mapped_column(Float)
    descent_m: Mapped[float | None] = mapped_column(Float)
    cum_ascent_m: Mapped[float | None] = mapped_column(Float)
    cum_descent_m: Mapped[float | None] = mapped_column(Float)
