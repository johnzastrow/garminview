from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class ActalogWorkout(Base):
    __tablename__ = "actalog_workouts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_date: Mapped[datetime | None] = mapped_column(DateTime)
    workout_name: Mapped[str | None] = mapped_column(Text)
    workout_type: Mapped[str | None] = mapped_column(String(32))
    total_time_s: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    formatted_notes: Mapped[str | None] = mapped_column(Text)
    performance_notes: Mapped[str | None] = mapped_column(Text)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class ActalogMovement(Base):
    __tablename__ = "actalog_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text)
    movement_type: Mapped[str | None] = mapped_column(String(32))


class ActalogWod(Base):
    __tablename__ = "actalog_wods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text)
    alt_name: Mapped[str | None] = mapped_column(Text)
    name_source: Mapped[str | None] = mapped_column(String(16))  # PRVN | GYM | UNKNOWN
    regime: Mapped[str | None] = mapped_column(String(64))
    score_type: Mapped[str | None] = mapped_column(String(32))


class ActalogWorkoutMovement(Base):
    __tablename__ = "actalog_workout_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    movement_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_movements.id"))
    sets: Mapped[int | None] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[int | None] = mapped_column(Integer)
    is_pr: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    order_index: Mapped[int | None] = mapped_column(Integer)


class ActalogWorkoutWod(Base):
    __tablename__ = "actalog_workout_wods"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    wod_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_wods.id"))
    score_value: Mapped[str | None] = mapped_column(Text)
    time_s: Mapped[int | None] = mapped_column(Integer)
    rounds: Mapped[int | None] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[int | None] = mapped_column(Integer)
    is_pr: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    order_index: Mapped[int | None] = mapped_column(Integer)


class ActalogNoteParse(Base):
    __tablename__ = "actalog_note_parses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    content_class: Mapped[str | None] = mapped_column(String(32))   # WORKOUT | MIXED | PERFORMANCE_ONLY | SKIP
    raw_notes: Mapped[str | None] = mapped_column(Text)
    parsed_json: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str | None] = mapped_column(String(16))    # pending | approved | rejected | sent | skipped
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String(64))


class ActalogPersonalRecord(Base):
    __tablename__ = "actalog_personal_records"
    movement_id: Mapped[int] = mapped_column(Integer, ForeignKey("actalog_movements.id"), primary_key=True)
    max_weight_kg: Mapped[float | None] = mapped_column(Float)
    max_reps: Mapped[int | None] = mapped_column(Integer)
    best_time_s: Mapped[int | None] = mapped_column(Integer)
    workout_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("actalog_workouts.id"))
    workout_date: Mapped[datetime | None] = mapped_column(DateTime)
