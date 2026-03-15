from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class ActalogWorkout(Base):
    __tablename__ = "actalog_workouts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_date: Mapped[datetime | None] = mapped_column(DateTime)
    workout_name: Mapped[str | None] = mapped_column(Text)
    workout_type: Mapped[str | None] = mapped_column(String(32))
    total_time_s: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class ActalogMovement(Base):
    __tablename__ = "actalog_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    movement_type: Mapped[str | None] = mapped_column(String(32))


class ActalogWod(Base):
    __tablename__ = "actalog_wods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    regime: Mapped[str | None] = mapped_column(String(64))
    score_type: Mapped[str | None] = mapped_column(String(32))


class ActalogWorkoutMovement(Base):
    __tablename__ = "actalog_workout_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    movement_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_movements.id"))
    sets: Mapped[int | None] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[int | None] = mapped_column(Integer)
    is_pr: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int | None] = mapped_column(Integer)


class ActalogWorkoutWod(Base):
    __tablename__ = "actalog_workout_wods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    wod_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_wods.id"))
    score_value: Mapped[str | None] = mapped_column(Text)
    time_s: Mapped[int | None] = mapped_column(Integer)
    rounds: Mapped[int | None] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[int | None] = mapped_column(Integer)
    is_pr: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int | None] = mapped_column(Integer)


class ActalogPersonalRecord(Base):
    __tablename__ = "actalog_personal_records"
    movement_id: Mapped[int] = mapped_column(Integer, ForeignKey("actalog_movements.id"), primary_key=True)
    max_weight_kg: Mapped[float | None] = mapped_column(Float)
    max_reps: Mapped[int | None] = mapped_column(Integer)
    best_time_s: Mapped[int | None] = mapped_column(Integer)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    workout_date: Mapped[datetime | None] = mapped_column(DateTime)
