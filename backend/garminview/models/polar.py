"""Polar Flow staging tables — mirrors the GDPR JSON export structure.

All tables are prefixed with polar_ and are independent of existing Garmin tables.
High-volume time-series data (samples, routes, 247ohr) is stored as JSON arrays
for compact staging. Merge/ETL to core tables is a future step.
"""

from datetime import date, datetime
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from garminview.core.database import Base

# MariaDB TEXT = 64KB max. GPS routes and per-second samples easily exceed this.
# Text(2**24) → MEDIUMTEXT on MySQL/MariaDB (16MB), plain TEXT on SQLite (unlimited).
LargeText = Text(2**24)


# ── Training sessions ────────────────────────────────────────────────

class PolarTrainingSession(Base):
    __tablename__ = "polar_training_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created: Mapped[datetime | None] = mapped_column(DateTime)
    modified: Mapped[datetime | None] = mapped_column(DateTime)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    stop_time: Mapped[datetime | None] = mapped_column(DateTime)
    name: Mapped[str | None] = mapped_column(String(256))
    sport_id: Mapped[str | None] = mapped_column(String(64))
    device_id: Mapped[str | None] = mapped_column(String(64))
    device_model: Mapped[str | None] = mapped_column(String(128))
    app_name: Mapped[str | None] = mapped_column(String(128))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    distance_m: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)
    training_load: Mapped[float | None] = mapped_column(Float)
    recovery_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    tz_offset_min: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    aerobic_threshold: Mapped[int | None] = mapped_column(Integer)
    anaerobic_threshold: Mapped[int | None] = mapped_column(Integer)
    vo2max: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarExercise(Base):
    __tablename__ = "polar_exercises"

    exercise_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    exercise_index: Mapped[int | None] = mapped_column(Integer)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    stop_time: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    distance_m: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)
    training_load: Mapped[float | None] = mapped_column(Float)
    recovery_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    sport_id: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    tz_offset_min: Mapped[int | None] = mapped_column(Integer)


class PolarExerciseStatistic(Base):
    __tablename__ = "polar_exercise_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_id: Mapped[str] = mapped_column(String(64), index=True)
    stat_type: Mapped[str] = mapped_column(String(64))
    avg: Mapped[float | None] = mapped_column(Float)
    max: Mapped[float | None] = mapped_column(Float)


class PolarExerciseZone(Base):
    __tablename__ = "polar_exercise_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_id: Mapped[str] = mapped_column(String(64), index=True)
    zone_type: Mapped[str] = mapped_column(String(64))
    zone_index: Mapped[int] = mapped_column(Integer)
    lower_limit: Mapped[float | None] = mapped_column(Float)
    higher_limit: Mapped[float | None] = mapped_column(Float)


class PolarExerciseLap(Base):
    __tablename__ = "polar_exercise_laps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_id: Mapped[str] = mapped_column(String(64), index=True)
    lap_index: Mapped[int] = mapped_column(Integer)
    raw_json: Mapped[str | None] = mapped_column(LargeText)


class PolarExerciseSample(Base):
    __tablename__ = "polar_exercise_samples"
    __table_args__ = (
        UniqueConstraint("exercise_id", "sample_type", name="uq_polar_ex_sample"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_id: Mapped[str] = mapped_column(String(64), index=True)
    sample_type: Mapped[str] = mapped_column(String(32))
    interval_ms: Mapped[int | None] = mapped_column(Integer)
    values_json: Mapped[str | None] = mapped_column(LargeText)


class PolarExerciseRoute(Base):
    __tablename__ = "polar_exercise_routes"
    __table_args__ = (
        UniqueConstraint("exercise_id", "route_type", name="uq_polar_ex_route"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_id: Mapped[str] = mapped_column(String(64), index=True)
    route_type: Mapped[str] = mapped_column(String(16))
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    waypoints_json: Mapped[str | None] = mapped_column(LargeText)


# ── Daily activities ─────────────────────────────────────────────────

class PolarActivity(Base):
    __tablename__ = "polar_activities"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    export_version: Mapped[str | None] = mapped_column(String(16))
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarActivitySample(Base):
    __tablename__ = "polar_activity_samples"
    __table_args__ = (
        UniqueConstraint("date", "sample_type", name="uq_polar_act_sample"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sample_type: Mapped[str] = mapped_column(String(16))
    values_json: Mapped[str | None] = mapped_column(LargeText)


class PolarActivityMetSource(Base):
    __tablename__ = "polar_activity_met_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    source_index: Mapped[int] = mapped_column(Integer)
    source_name: Mapped[str | None] = mapped_column(String(128))


class PolarActivityPhysicalInfo(Base):
    __tablename__ = "polar_activity_physical_info"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    sex: Mapped[str | None] = mapped_column(String(16))
    birthday: Mapped[date | None] = mapped_column(Date)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)


# ── Sleep ────────────────────────────────────────────────────────────

class PolarSleep(Base):
    __tablename__ = "polar_sleep"

    night: Mapped[date] = mapped_column(Date, primary_key=True)
    sleep_type: Mapped[str | None] = mapped_column(String(32))
    sleep_span: Mapped[str | None] = mapped_column(String(32))
    asleep_duration: Mapped[str | None] = mapped_column(String(32))
    age: Mapped[int | None] = mapped_column(Integer)
    efficiency_pct: Mapped[float | None] = mapped_column(Float)
    continuity_index: Mapped[float | None] = mapped_column(Float)
    continuity_class: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[int | None] = mapped_column(Integer)
    interruption_total_dur: Mapped[str | None] = mapped_column(String(32))
    interruption_total_count: Mapped[int | None] = mapped_column(Integer)
    interruption_short_count: Mapped[int | None] = mapped_column(Integer)
    interruption_long_count: Mapped[int | None] = mapped_column(Integer)
    sleep_start: Mapped[datetime | None] = mapped_column(DateTime)
    sleep_end: Mapped[datetime | None] = mapped_column(DateTime)
    sleep_goal: Mapped[str | None] = mapped_column(String(32))
    rating: Mapped[str | None] = mapped_column(String(32))
    device_id: Mapped[str | None] = mapped_column(String(64))
    battery_ran_out: Mapped[bool | None] = mapped_column(Boolean)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarSleepState(Base):
    __tablename__ = "polar_sleep_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    night: Mapped[date] = mapped_column(Date, index=True)
    state_index: Mapped[int] = mapped_column(Integer)
    offset_from_start: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str | None] = mapped_column(String(16))


# ── 24/7 Optical HR ─────────────────────────────────────────────────

class Polar247OHR(Base):
    __tablename__ = "polar_247ohr"
    __table_args__ = (
        UniqueConstraint("date", "device_id", name="uq_polar_247ohr"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    device_id: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(Integer)
    samples_json: Mapped[str | None] = mapped_column(LargeText)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


# ── Fitness tests ────────────────────────────────────────────────────

class PolarFitnessTest(Base):
    __tablename__ = "polar_fitness_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created: Mapped[datetime | None] = mapped_column(DateTime)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    own_index: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    fitness_class: Mapped[str | None] = mapped_column(String(32))
    tz_offset_min: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    vo2max: Mapped[float | None] = mapped_column(Float)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


# ── Training targets ────────────────────────────────────────────────

class PolarTrainingTarget(Base):
    __tablename__ = "polar_training_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    name: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    done: Mapped[bool | None] = mapped_column(Boolean)
    program_ref: Mapped[int | None] = mapped_column(Integer)
    non_user_editable: Mapped[bool | None] = mapped_column(Boolean)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarTrainingTargetPhase(Base):
    __tablename__ = "polar_training_target_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    exercise_index: Mapped[int | None] = mapped_column(Integer)
    sport: Mapped[str | None] = mapped_column(String(64))
    phase_index: Mapped[int | None] = mapped_column(Integer)
    phase_name: Mapped[str | None] = mapped_column(String(128))
    change_type: Mapped[str | None] = mapped_column(String(32))
    goal_type: Mapped[str | None] = mapped_column(String(32))
    goal_duration: Mapped[str | None] = mapped_column(String(32))
    intensity_type: Mapped[str | None] = mapped_column(String(32))
    intensity_upper_zone: Mapped[int | None] = mapped_column(Integer)
    intensity_lower_zone: Mapped[int | None] = mapped_column(Integer)


# ── Account & profile ───────────────────────────────────────────────

class PolarAccount(Base):
    __tablename__ = "polar_account"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(256))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    nickname: Mapped[str | None] = mapped_column(String(128))
    sex: Mapped[str | None] = mapped_column(String(16))
    birthday: Mapped[date | None] = mapped_column(Date)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    vo2max: Mapped[float | None] = mapped_column(Float)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    sleep_goal: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str | None] = mapped_column(String(64))
    settings_json: Mapped[str | None] = mapped_column(Text)
    linked_apps_json: Mapped[str | None] = mapped_column(Text)
    motto: Mapped[str | None] = mapped_column(String(256))
    phone: Mapped[str | None] = mapped_column(String(32))
    country_code: Mapped[str | None] = mapped_column(String(8))
    city: Mapped[str | None] = mapped_column(String(128))
    favourite_sports_json: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


# ── Catch-all JSON blob tables ──────────────────────────────────────

class PolarDevice(Base):
    __tablename__ = "polar_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_json: Mapped[str | None] = mapped_column(LargeText)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarSportProfile(Base):
    __tablename__ = "polar_sport_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport: Mapped[str | None] = mapped_column(String(64))
    raw_json: Mapped[str | None] = mapped_column(LargeText)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarCalendarItem(Base):
    __tablename__ = "polar_calendar_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    datetime_: Mapped[datetime | None] = mapped_column("datetime", DateTime)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    vo2max: Mapped[float | None] = mapped_column(Float)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    aerobic_threshold: Mapped[int | None] = mapped_column(Integer)
    anaerobic_threshold: Mapped[int | None] = mapped_column(Integer)
    ftp: Mapped[int | None] = mapped_column(Integer)
    training_background: Mapped[str | None] = mapped_column(String(32))
    typical_day: Mapped[str | None] = mapped_column(String(32))


class PolarProgram(Base):
    __tablename__ = "polar_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_type: Mapped[str | None] = mapped_column(String(64))
    raw_json: Mapped[str | None] = mapped_column(LargeText)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarPlannedRoute(Base):
    __tablename__ = "polar_planned_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_json: Mapped[str | None] = mapped_column(LargeText)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


class PolarFavouriteTarget(Base):
    __tablename__ = "polar_favourite_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_json: Mapped[str | None] = mapped_column(LargeText)
    source_file: Mapped[str | None] = mapped_column(String(256))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime)


# ── Import tracking ─────────────────────────────────────────────────

class PolarImportLog(Base):
    __tablename__ = "polar_import_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_path: Mapped[str | None] = mapped_column(String(512))
    files_found: Mapped[int | None] = mapped_column(Integer)
    files_imported: Mapped[int | None] = mapped_column(Integer)
    files_skipped: Mapped[int | None] = mapped_column(Integer)
    files_errored: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(16))
    error_detail: Mapped[str | None] = mapped_column(Text)


class PolarImportFile(Base):
    __tablename__ = "polar_import_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(Integer, index=True)
    filename: Mapped[str | None] = mapped_column(String(256))
    file_type: Mapped[str | None] = mapped_column(String(64))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(16))
    records_upserted: Mapped[int | None] = mapped_column(Integer)
    error_detail: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
