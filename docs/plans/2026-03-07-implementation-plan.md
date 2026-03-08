# GarminView Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a personal Garmin fitness data platform with a Python/FastAPI backend, Vue.js frontend, dual SQLite/MariaDB support, and a full ingestion-to-visualization pipeline.

**Architecture:** GarminDB acts as a download+FIT-parse tool only; garminview owns its own database (SQLite dev, MariaDB prod) via SQLAlchemy 2.x + Alembic. Data flows raw files → garminview adapters → DB → analysis engine → FastAPI → Vue.js.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x, Alembic, fitparse, tenacity, APScheduler, structlog, Vue.js 3.x, Pinia, vue-echarts, WeasyPrint, pytest, Marimo

---

## Phase 1: Foundation

### Task 1: Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/garminview/__init__.py`
- Create: `backend/garminview/core/__init__.py`
- Create: `backend/garminview/core/config.py`
- Create: `backend/garminview/core/database.py`
- Create: `backend/garminview/core/logging.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `.env.example`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "garminview"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "pymysql>=1.1.0",
    "cryptography>=42.0.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "fitparse>=1.2.0",
    "garminconnect>=0.2.19",
    "tenacity>=8.2.0",
    "apscheduler>=3.10.0",
    "structlog>=24.1.0",
    "pandas>=2.2.0",
    "scipy>=1.12.0",
    "numpy>=1.26.0",
    "weasyprint>=61.0",
    "jinja2>=3.1.0",
    "pyecharts>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.3.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create core/config.py**

```python
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBBackend(str, Enum):
    sqlite = "sqlite"
    mariadb = "mariadb"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GARMINVIEW_")

    db_backend: DBBackend = DBBackend.sqlite
    db_path: str = "garminview.db"          # sqlite only
    db_url: str = ""                         # mariadb: user:pass@host:port/dbname
    health_data_dir: str = "~/HealthData"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"
    cors_origins: list[str] = ["http://localhost:5173"]


def get_config() -> Config:
    return Config()
```

**Step 3: Create core/database.py**

```python
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from garminview.core.config import Config, DBBackend


class Base(DeclarativeBase):
    pass


def create_db_engine(config: Config) -> Engine:
    if config.db_backend == DBBackend.mariadb:
        url = f"mysql+pymysql://{config.db_url}?charset=utf8mb4"
        return create_engine(url, pool_pre_ping=True, pool_size=10)
    db_path = config.db_path.replace("~", __import__("os").path.expanduser("~"))
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def verify_connection(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
```

**Step 4: Create core/logging.py**

```python
import structlog
import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper()))
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str):
    return structlog.get_logger(name)
```

**Step 5: Create tests/conftest.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from garminview.core.database import Base
from garminview.core.config import Config, DBBackend


@pytest.fixture(scope="function")
def test_config():
    return Config(db_backend=DBBackend.sqlite, db_path=":memory:")


@pytest.fixture(scope="function")
def engine(test_config):
    from garminview.core.database import create_db_engine
    eng = create_db_engine(test_config)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def session(engine):
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
```

**Step 6: Create .env.example**

```
GARMINVIEW_DB_BACKEND=sqlite
GARMINVIEW_DB_PATH=garminview.db
# For MariaDB:
# GARMINVIEW_DB_BACKEND=mariadb
# GARMINVIEW_DB_URL=user:password@localhost:3306/garminview
GARMINVIEW_HEALTH_DATA_DIR=~/HealthData
GARMINVIEW_LOG_LEVEL=INFO
GARMINVIEW_SECRET_KEY=change-me
```

**Step 7: Write test for config + DB connection**

```python
# tests/test_core.py
def test_sqlite_engine_created(test_config, engine):
    from garminview.core.database import verify_connection
    verify_connection(engine)  # must not raise


def test_mariadb_url_format():
    from garminview.core.config import Config, DBBackend
    cfg = Config(db_backend=DBBackend.mariadb, db_url="user:pass@localhost:3306/gv")
    assert cfg.db_backend == DBBackend.mariadb
```

**Step 8: Run tests**

```bash
cd backend && uv venv && source .venv/bin/activate && uv pip install -e ".[dev]" && uv run pytest tests/test_core.py -v
```
Expected: 2 passed

**Step 9: Commit**

```bash
git add backend/ .env.example
git commit -m "feat: project scaffold — config, DB engine factory, logging"
```

---

### Task 2: SQLAlchemy Models — Groups 1–4

**Files:**
- Create: `backend/garminview/models/__init__.py`
- Create: `backend/garminview/models/health.py`
- Create: `backend/garminview/models/monitoring.py`
- Create: `backend/garminview/models/activities.py`
- Create: `backend/garminview/models/supplemental.py`
- Test: `backend/tests/test_models.py`

**Step 1: Write failing test**

```python
# tests/test_models.py
def test_all_tables_created(engine):
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "daily_summary" in tables
    assert "sleep" in tables
    assert "activities" in tables
    assert "hrv_data" in tables
    assert "body_composition" in tables
```

**Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_models.py -v
```
Expected: FAIL — tables not found

**Step 3: Create models/health.py**

```python
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
```

**Step 4: Create models/monitoring.py**

```python
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
```

**Step 5: Create models/activities.py**

```python
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
```

**Step 6: Create models/supplemental.py**

```python
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
```

**Step 7: Create models/__init__.py** (imports all models so Base.metadata knows about them)

```python
from garminview.models.health import (
    DailySummary, Sleep, SleepEvent, Weight, Stress, RestingHeartRate
)
from garminview.models.monitoring import (
    MonitoringHeartRate, MonitoringIntensity, MonitoringSteps,
    MonitoringRespiration, MonitoringPulseOx, MonitoringClimb
)
from garminview.models.activities import (
    Activity, ActivityLap, ActivityRecord, StepsActivity, ActivityHRZone
)
from garminview.models.supplemental import (
    HRVData, TrainingReadiness, TrainingStatus, BodyBatteryEvent,
    VO2Max, RacePrediction, LactateThreshold, HillScore, EnduranceScore,
    PersonalRecord, BodyComposition, BloodPressure, Gear, GearStats
)

__all__ = [
    "DailySummary", "Sleep", "SleepEvent", "Weight", "Stress", "RestingHeartRate",
    "MonitoringHeartRate", "MonitoringIntensity", "MonitoringSteps",
    "MonitoringRespiration", "MonitoringPulseOx", "MonitoringClimb",
    "Activity", "ActivityLap", "ActivityRecord", "StepsActivity", "ActivityHRZone",
    "HRVData", "TrainingReadiness", "TrainingStatus", "BodyBatteryEvent",
    "VO2Max", "RacePrediction", "LactateThreshold", "HillScore", "EnduranceScore",
    "PersonalRecord", "BodyComposition", "BloodPressure", "Gear", "GearStats",
]
```

**Step 8: Update conftest.py** to import models before `Base.metadata.create_all`

```python
# Add to top of conftest.py after imports:
import garminview.models  # noqa: F401 — registers all models with Base.metadata
```

**Step 9: Run tests**

```bash
uv run pytest tests/test_models.py -v
```
Expected: PASS

**Step 10: Commit**

```bash
git add backend/
git commit -m "feat: SQLAlchemy models — health, monitoring, activities, supplemental"
```

---

### Task 3: SQLAlchemy Models — Groups 5–9 (Derived, Assessments, Config, Sync, Schema)

**Files:**
- Create: `backend/garminview/models/derived.py`
- Create: `backend/garminview/models/assessments.py`
- Create: `backend/garminview/models/config.py`
- Create: `backend/garminview/models/sync.py`

**Step 1: Create models/derived.py**

```python
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
```

**Step 2: Create models/assessments.py**

```python
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
```

**Step 3: Create models/config.py**

```python
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profile"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str | None] = mapped_column(String(128))
    birth_date: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(8))
    height_cm: Mapped[float | None] = mapped_column(__import__("sqlalchemy").Float)
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
    target_value: Mapped[float | None] = mapped_column(__import__("sqlalchemy").Float)
    source: Mapped[str] = mapped_column(String(16), default="user")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class NotificationConfig(Base):
    __tablename__ = "notification_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[str | None] = mapped_column(Text)
```

**Step 4: Create models/sync.py**

```python
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from garminview.core.database import Base


class SyncLog(Base):
    __tablename__ = "sync_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    records_upserted: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="running")
    error_message: Mapped[str | None] = mapped_column(Text)


class DataProvenance(Base):
    __tablename__ = "data_provenance"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(64))
    record_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    imported_at: Mapped[datetime] = mapped_column(DateTime)


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(DateTime)
    applied_by: Mapped[str] = mapped_column(String(16), default="alembic")
```

**Step 5: Update models/__init__.py** to include all new models

**Step 6: Write test**

```python
# tests/test_models.py (add)
def test_derived_and_config_tables(engine):
    from sqlalchemy import inspect
    tables = inspect(engine).get_table_names()
    for t in ["daily_derived", "goals", "assessments", "app_config",
              "sync_schedule", "sync_log", "schema_version", "user_profile"]:
        assert t in tables, f"Missing table: {t}"
```

**Step 7: Run tests, commit**

```bash
uv run pytest tests/test_models.py -v
git add backend/
git commit -m "feat: complete SQLAlchemy models — derived, assessments, config, sync"
```

---

### Task 4: Alembic Setup + Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (directory)

**Step 1: Initialize Alembic**

```bash
cd backend && alembic init alembic
```

**Step 2: Edit alembic/env.py** — replace the generated file:

```python
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from garminview.core.config import get_config, DBBackend
from garminview.core.database import Base
import garminview.models  # noqa — registers all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    cfg = get_config()
    if cfg.db_backend == DBBackend.mariadb:
        return f"mysql+pymysql://{cfg.db_url}?charset=utf8mb4"
    return f"sqlite:///{cfg.db_path}"

def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    cfg = config.get_section(config.config_ini_section)
    cfg["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.",
                                     poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 3: Generate initial migration**

```bash
cd backend && alembic revision --autogenerate -m "initial schema"
```

**Step 4: Apply migration**

```bash
alembic upgrade head
```

**Step 5: Write startup version check**

```python
# garminview/core/startup.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from garminview.models.sync import SchemaVersion

CURRENT_SCHEMA_VERSION = "20260307_001"

def check_schema_version(session: Session) -> None:
    latest = (session.query(SchemaVersion)
              .order_by(SchemaVersion.applied_at.desc()).first())
    if latest and latest.version != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Schema version mismatch: DB has {latest.version}, "
            f"code expects {CURRENT_SCHEMA_VERSION}. Run: alembic upgrade head"
        )

def record_migration(session: Session, version: str, description: str) -> None:
    session.add(SchemaVersion(
        version=version,
        description=description,
        applied_at=datetime.now(timezone.utc),
        applied_by="alembic",
    ))
    session.commit()
```

**Step 6: Commit**

```bash
git add backend/alembic/ backend/alembic.ini backend/garminview/core/startup.py
git commit -m "feat: Alembic migrations setup + schema version tracking"
```

---

## Phase 2: Ingestion Pipeline

### Task 5: Base Adapter + Sync Log

**Files:**
- Create: `backend/garminview/ingestion/__init__.py`
- Create: `backend/garminview/ingestion/base.py`
- Create: `backend/garminview/ingestion/sync_logger.py`
- Test: `backend/tests/ingestion/test_base.py`

**Step 1: Write failing test**

```python
# tests/ingestion/test_base.py
from garminview.ingestion.base import BaseAdapter

def test_base_adapter_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        BaseAdapter()  # cannot instantiate abstract class
```

**Step 2: Create ingestion/base.py**

```python
from abc import ABC, abstractmethod
from datetime import date
from typing import Iterator


class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        """Yield records as dicts for upsert into target table."""

    @abstractmethod
    def source_name(self) -> str:
        """Identifier for sync_log and data_provenance."""

    @abstractmethod
    def target_table(self) -> str:
        """Name of the DB table this adapter writes to."""
```

**Step 3: Create ingestion/sync_logger.py**

```python
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from garminview.models.sync import SyncLog


class SyncLogger:
    def __init__(self, session: Session, source: str, mode: str,
                 date_start: date | None = None, date_end: date | None = None):
        self._session = session
        self._log = SyncLog(
            started_at=datetime.now(timezone.utc),
            source=source,
            mode=mode,
            date_start=date_start,
            date_end=date_end,
            status="running",
            records_upserted=0,
        )
        session.add(self._log)
        session.commit()

    def increment(self, count: int = 1) -> None:
        self._log.records_upserted = (self._log.records_upserted or 0) + count
        self._session.commit()

    def success(self) -> None:
        self._log.finished_at = datetime.now(timezone.utc)
        self._log.status = "success"
        self._session.commit()

    def fail(self, error: str) -> None:
        self._log.finished_at = datetime.now(timezone.utc)
        self._log.status = "failed"
        self._log.error_message = error
        self._session.commit()
```

**Step 4: Run test, commit**

```bash
uv run pytest tests/ingestion/ -v
git add backend/garminview/ingestion/ backend/tests/ingestion/
git commit -m "feat: base adapter interface + sync logger"
```

---

### Task 6: Rate Limiter

**Files:**
- Create: `backend/garminview/ingestion/rate_limiter.py`
- Test: `backend/tests/ingestion/test_rate_limiter.py`

**Step 1: Write failing test**

```python
def test_retry_on_too_many_requests():
    from unittest.mock import patch, MagicMock
    from garminconnect import GarminConnectTooManyRequestsError
    from garminview.ingestion.rate_limiter import call_with_backoff

    call_count = 0
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise GarminConnectTooManyRequestsError("rate limited")
        return "ok"

    result = call_with_backoff(flaky)
    assert result == "ok"
    assert call_count == 3
```

**Step 2: Create ingestion/rate_limiter.py**

```python
from tenacity import (
    retry, retry_if_exception_type, wait_exponential,
    stop_after_attempt, before_sleep_log
)
import logging
from garminconnect import GarminConnectTooManyRequestsError

logger = logging.getLogger(__name__)

_retry = retry(
    retry=retry_if_exception_type(GarminConnectTooManyRequestsError),
    wait=wait_exponential(multiplier=1, min=30, max=300),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def call_with_backoff(fn, *args, **kwargs):
    return _retry(fn)(*args, **kwargs)
```

**Step 3: Run test, commit**

```bash
uv run pytest tests/ingestion/test_rate_limiter.py -v
git add backend/garminview/ingestion/rate_limiter.py backend/tests/ingestion/test_rate_limiter.py
git commit -m "feat: rate limiter with exponential backoff for Garmin API"
```

---

### Task 7: Daily Summary File Adapter

**Files:**
- Create: `backend/garminview/ingestion/file_adapters/daily_summary.py`
- Create: `backend/tests/ingestion/fixtures/daily_summary_sample.json`
- Test: `backend/tests/ingestion/test_daily_summary_adapter.py`

**Step 1: Create fixture** (`daily_summary_sample.json` — minimal valid structure):

```json
{
  "calendarDate": "2026-01-15",
  "totalSteps": 8234,
  "floorsAscended": 12,
  "totalDistanceMeters": 6543,
  "totalKilocalories": 2341,
  "bmrKilocalories": 1800,
  "activeKilocalories": 541,
  "averageHeartRate": 68,
  "minHeartRate": 48,
  "maxHeartRate": 142,
  "restingHeartRateValue": 52,
  "averageStressLevel": 28,
  "maxBodyBattery": 87,
  "minBodyBattery": 34,
  "averageSpo2": 96.5,
  "averageRespirationValue": 14.2,
  "totalLiquidConsumptionMl": 2100,
  "dailyHydrationGoal": 2500,
  "moderateIntensityMinutes": 45,
  "vigorousIntensityMinutes": 20,
  "sleepingSeconds": 28800
}
```

**Step 2: Write failing test**

```python
# tests/ingestion/test_daily_summary_adapter.py
import json
from pathlib import Path
from datetime import date

FIXTURE = Path(__file__).parent / "fixtures" / "daily_summary_sample.json"

def test_daily_summary_adapter_parses_record():
    from garminview.ingestion.file_adapters.daily_summary import DailySummaryAdapter
    adapter = DailySummaryAdapter(data_dir=FIXTURE.parent)
    records = list(adapter._parse_file(FIXTURE))
    assert len(records) == 1
    r = records[0]
    assert r["date"] == date(2026, 1, 15)
    assert r["steps"] == 8234
    assert r["hr_resting"] == 52
```

**Step 3: Create file_adapters/daily_summary.py**

```python
import json
from datetime import date
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class DailySummaryAdapter(BaseAdapter):
    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:daily_summary"

    def target_table(self) -> str:
        return "daily_summary"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        for path in sorted(self._data_dir.glob("*.json")):
            yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        d = raw.get("calendarDate")
        if not d:
            return
        yield {
            "date": date.fromisoformat(d),
            "steps": raw.get("totalSteps"),
            "floors": raw.get("floorsAscended"),
            "distance_m": raw.get("totalDistanceMeters"),
            "calories_total": raw.get("totalKilocalories"),
            "calories_bmr": raw.get("bmrKilocalories"),
            "calories_active": raw.get("activeKilocalories"),
            "hr_avg": raw.get("averageHeartRate"),
            "hr_min": raw.get("minHeartRate"),
            "hr_max": raw.get("maxHeartRate"),
            "hr_resting": raw.get("restingHeartRateValue"),
            "stress_avg": raw.get("averageStressLevel"),
            "body_battery_max": raw.get("maxBodyBattery"),
            "body_battery_min": raw.get("minBodyBattery"),
            "spo2_avg": raw.get("averageSpo2"),
            "respiration_avg": raw.get("averageRespirationValue"),
            "hydration_intake_ml": raw.get("totalLiquidConsumptionMl"),
            "hydration_goal_ml": raw.get("dailyHydrationGoal"),
            "intensity_min_moderate": raw.get("moderateIntensityMinutes"),
            "intensity_min_vigorous": raw.get("vigorousIntensityMinutes"),
        }
```

**Step 4: Run test, commit**

```bash
uv run pytest tests/ingestion/test_daily_summary_adapter.py -v
git add backend/garminview/ingestion/file_adapters/ backend/tests/ingestion/
git commit -m "feat: DailySummaryAdapter — parse Garmin daily summary JSON"
```

---

### Task 8: Sleep, Weight, RHR File Adapters

Follow the same pattern as Task 7 for:
- `SleepAdapter` → parses `sleep/*.json` → `sleep` + `sleep_events` tables
- `WeightAdapter` → parses `weight/*.json` → `weight` table
- `RHRAdapter` → parses `rhr/*.json` → `resting_heart_rate` table

Key JSON fields to map (Garmin field → model field):
- Sleep: `calendarDate`, `sleepStartTimestampGMT`, `sleepEndTimestampGMT`, `deepSleepSeconds/60`, `lightSleepSeconds/60`, `remSleepSeconds/60`, `awakeSleepSeconds/60`, `sleepScores.overall.value`, `averageSpO2Value`, `averageRespirationValue`, `averageStressLevel`
- Weight: `date`, `weight` (divide by 1000 if in grams)
- RHR: `calendarDate`, `restingHeartRate`

Write one test per adapter with a fixture JSON. Commit after all three pass.

---

### Task 9: Monitoring FIT Adapter

**Files:**
- Create: `backend/garminview/ingestion/file_adapters/monitoring_fit.py`
- Test: `backend/tests/ingestion/test_monitoring_fit.py`

**Step 1: Write failing test**

```python
def test_monitoring_fit_adapter_interface():
    from garminview.ingestion.file_adapters.monitoring_fit import MonitoringFitAdapter
    adapter = MonitoringFitAdapter(data_dir="/tmp/nonexistent")
    assert adapter.source_name() == "garmin_files:monitoring_fit"
    assert adapter.target_table() == "monitoring_heart_rate"
```

**Step 2: Create monitoring_fit.py**

```python
import fitparse
from datetime import date
from pathlib import Path
from typing import Iterator
from garminview.ingestion.base import BaseAdapter


class MonitoringFitAdapter(BaseAdapter):
    """Parses monitoring FIT files → monitoring_heart_rate, monitoring_steps,
    monitoring_intensity, monitoring_respiration, monitoring_pulse_ox, monitoring_climb."""

    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:monitoring_fit"

    def target_table(self) -> str:
        return "monitoring_heart_rate"  # primary; others written by orchestrator

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        for path in sorted(self._data_dir.glob("*.fit")):
            yield from self._parse_fit(path)

    def _parse_fit(self, path: Path) -> Iterator[dict]:
        try:
            ff = fitparse.FitFile(str(path))
            for record in ff.get_messages("monitoring"):
                data = {f.name: f.value for f in record}
                ts = data.get("timestamp")
                if not ts:
                    continue
                yield {
                    "type": "heart_rate",
                    "timestamp": ts,
                    "hr": data.get("heart_rate"),
                    "steps": data.get("steps"),
                    "activity_type": str(data.get("activity_type", "")),
                    "moderate_time_s": data.get("moderate_activity_time"),
                    "vigorous_time_s": data.get("vigorous_activity_time"),
                    "ascent_m": data.get("ascent"),
                    "descent_m": data.get("descent"),
                    "cum_ascent_m": data.get("cum_ascent"),
                    "cum_descent_m": data.get("cum_descent"),
                    "rr": data.get("respiration_rate"),
                    "spo2": data.get("pulse_ox"),
                }
        except Exception as e:
            from garminview.core.logging import get_logger
            get_logger(__name__).warning("fit_parse_error", path=str(path), error=str(e))
```

**Step 3: Run test, commit**

```bash
uv run pytest tests/ingestion/test_monitoring_fit.py -v
git add backend/garminview/ingestion/file_adapters/monitoring_fit.py
git commit -m "feat: MonitoringFitAdapter — parse monitoring FIT files"
```

---

### Task 10: Activity JSON + FIT Adapters

Follow same pattern for:
- `ActivityJsonAdapter` → parses `activities/*.json` → `activities` table
- `ActivityFitAdapter` → parses `activities/*.fit` → `activity_records`, `activity_laps`, `steps_activities`, `activity_hr_zones`

Key fields from activity JSON:
```
activityId, activityName, activityType.typeKey, sport,
beginTimestamp, duration, movingDuration, distance,
calories, averageHR, maxHR, averageRunCadence,
averageSpeed, elevationGain, elevationLoss,
trainingLoad, aerobicTrainingEffect, anaerobicTrainingEffect
```

Commit after both adapters have passing tests.

---

### Task 11: Garmin API Adapters (HRV, Training, Body)

**Files:**
- Create: `backend/garminview/ingestion/api_adapters/base_api.py`
- Create: `backend/garminview/ingestion/api_adapters/hrv.py`
- Create: `backend/garminview/ingestion/api_adapters/training.py`
- Create: `backend/garminview/ingestion/api_adapters/body.py`
- Create: `backend/garminview/ingestion/api_adapters/performance.py`

**Step 1: Create base_api.py** (shared Garmin client init)

```python
from garminconnect import Garmin
from garminview.ingestion.rate_limiter import call_with_backoff


class BaseAPIAdapter:
    def __init__(self, client: Garmin):
        self._client = client

    def _call(self, method, *args, **kwargs):
        return call_with_backoff(getattr(self._client, method), *args, **kwargs)
```

**Step 2: Create api_adapters/hrv.py**

```python
from datetime import date, timedelta
from typing import Iterator
from garminview.ingestion.api_adapters.base_api import BaseAPIAdapter


class HRVAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:hrv"

    def target_table(self) -> str:
        return "hrv_data"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_hrv_data", d.isoformat())
                if raw:
                    yield self._parse(d, raw)
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        summary = raw.get("hrvSummary", {})
        return {
            "date": d,
            "hrv_rmssd": summary.get("rmssd"),
            "hrv_5min_high": summary.get("highFrequency"),
            "hrv_5min_low": summary.get("lowFrequency"),
            "baseline_low": summary.get("baselineLowUpper"),
            "baseline_high": summary.get("baselineBalancedUpper"),
            "status": summary.get("status"),
        }
```

Create similar adapters for:
- `TrainingReadinessAdapter` → `get_training_readiness`
- `TrainingStatusAdapter` → `get_training_status`
- `VO2MaxAdapter` → `get_max_metrics` + `get_fitnessage_data`
- `BodyCompositionAdapter` → `get_body_composition` (date range, chunk 28 days)
- `RacePredictionsAdapter` → `get_race_predictions`
- `LactateThresholdAdapter` → `get_lactate_threshold`
- `BloodPressureAdapter` → `get_blood_pressure`
- `PersonalRecordsAdapter` → `get_personal_records`
- `GearAdapter` → `get_gear` + `get_gear_stats`

Write a test for HRVAdapter using a mocked Garmin client. Commit after all API adapters pass.

---

### Task 12: Ingestion Orchestrator

**Files:**
- Create: `backend/garminview/ingestion/orchestrator.py`
- Test: `backend/tests/ingestion/test_orchestrator.py`

**Step 1: Write failing test**

```python
def test_orchestrator_runs_file_adapters(session, tmp_path, monkeypatch):
    from garminview.ingestion.orchestrator import IngestionOrchestrator
    from datetime import date

    orch = IngestionOrchestrator(session=session, health_data_dir=tmp_path)
    # Should not raise even with empty data dir
    orch.run_incremental()
    from garminview.models.sync import SyncLog
    logs = session.query(SyncLog).all()
    assert len(logs) > 0
```

**Step 2: Create orchestrator.py**

```python
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from garminview.ingestion.sync_logger import SyncLogger
from garminview.ingestion.file_adapters.daily_summary import DailySummaryAdapter
from garminview.ingestion.file_adapters.sleep import SleepAdapter
from garminview.ingestion.file_adapters.weight import WeightAdapter
from garminview.ingestion.file_adapters.rhr import RHRAdapter
from garminview.ingestion.file_adapters.monitoring_fit import MonitoringFitAdapter
from garminview.ingestion.file_adapters.activity_json import ActivityJsonAdapter
from garminview.ingestion.file_adapters.activity_fit import ActivityFitAdapter
from garminview.models.health import DailySummary
from garminview.core.logging import get_logger

log = get_logger(__name__)


class IngestionOrchestrator:
    def __init__(self, session: Session, health_data_dir: str | Path,
                 garmin_client=None):
        self._session = session
        self._data_dir = Path(health_data_dir).expanduser()
        self._garmin_client = garmin_client

    def run_full(self, start_date: date, end_date: date) -> None:
        self._run_file_adapters(start_date, end_date)
        if self._garmin_client:
            self._run_api_adapters(start_date, end_date)

    def run_incremental(self) -> None:
        last = self._get_last_sync_date()
        end = date.today()
        self.run_full(last, end)

    def run_analysis_only(self) -> None:
        from garminview.analysis.engine import AnalysisEngine
        AnalysisEngine(self._session).run_all()

    def _get_last_sync_date(self) -> date:
        result = self._session.execute(
            select(func.max(DailySummary.date))
        ).scalar()
        return result - timedelta(days=3) if result else date(2020, 1, 1)

    def _run_file_adapters(self, start_date: date, end_date: date) -> None:
        adapters = [
            DailySummaryAdapter(self._data_dir / "monitoring"),
            SleepAdapter(self._data_dir / "sleep"),
            WeightAdapter(self._data_dir / "weight"),
            RHRAdapter(self._data_dir / "rhr"),
            MonitoringFitAdapter(self._data_dir / "monitoring"),
            ActivityJsonAdapter(self._data_dir / "activities"),
            ActivityFitAdapter(self._data_dir / "activities"),
        ]
        for adapter in adapters:
            sync_log = SyncLogger(self._session, adapter.source_name(),
                                  "incremental", start_date, end_date)
            try:
                count = self._upsert_adapter(adapter, start_date, end_date)
                sync_log.increment(count)
                sync_log.success()
            except Exception as e:
                log.error("adapter_failed", source=adapter.source_name(), error=str(e))
                sync_log.fail(str(e))

    def _upsert_adapter(self, adapter, start_date: date, end_date: date) -> int:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        count = 0
        table = adapter.target_table()
        model = self._get_model_for_table(table)
        for record in adapter.fetch(start_date, end_date):
            stmt = sqlite_insert(model).values(**record)
            stmt = stmt.on_conflict_do_update(
                index_elements=self._get_pk_columns(model),
                set_=record,
            )
            self._session.execute(stmt)
            count += 1
        self._session.commit()
        return count

    def _get_model_for_table(self, table_name: str):
        import garminview.models as m
        TABLE_MAP = {
            "daily_summary": m.DailySummary,
            "sleep": m.Sleep,
            "sleep_events": m.SleepEvent,
            "weight": m.Weight,
            "resting_heart_rate": m.RestingHeartRate,
            "monitoring_heart_rate": m.MonitoringHeartRate,
            "activities": m.Activity,
        }
        return TABLE_MAP[table_name]

    def _get_pk_columns(self, model) -> list:
        from sqlalchemy import inspect
        return [c.key for c in inspect(model).primary_key]

    def _run_api_adapters(self, start_date: date, end_date: date) -> None:
        pass  # populated in Task 11
```

**Step 3: Run test, commit**

```bash
uv run pytest tests/ingestion/test_orchestrator.py -v
git add backend/garminview/ingestion/orchestrator.py
git commit -m "feat: ingestion orchestrator — coordinates all file + API adapters"
```

---

## Phase 3: Analysis Engine

### Task 13: Training Load Metrics

**Files:**
- Create: `backend/garminview/analysis/__init__.py`
- Create: `backend/garminview/analysis/metrics/training_load.py`
- Test: `backend/tests/analysis/test_training_load.py`

**Step 1: Write failing tests**

```python
# tests/analysis/test_training_load.py
from garminview.analysis.metrics.training_load import calc_trimp, calc_ewma_series

def test_trimp_calculation():
    # Banister TRIMP: 60 min, avg HR 150, max HR 190
    result = calc_trimp(duration_min=60, avg_hr=150, max_hr=190)
    assert 80 < result < 120  # reasonable range

def test_ewma_series():
    loads = [100, 80, 120, 90, 110, 95, 105]
    atl = calc_ewma_series(loads, tau=7)
    assert len(atl) == len(loads)
    assert atl[-1] > 0
    # EWMA should be between min and max of series
    assert min(loads) * 0.5 < atl[-1] < max(loads) * 1.5

def test_acwr_in_safe_zone():
    from garminview.analysis.metrics.training_load import calc_acwr
    atl, ctl = 80.0, 90.0
    acwr = calc_acwr(atl, ctl)
    assert 0.85 < acwr < 0.95
```

**Step 2: Create analysis/metrics/training_load.py**

```python
import math
from typing import Sequence


def calc_trimp(duration_min: float, avg_hr: int, max_hr: int,
               resting_hr: int = 50) -> float:
    """Banister (1991) TRIMP."""
    if max_hr <= resting_hr or avg_hr <= resting_hr:
        return 0.0
    hr_fraction = (avg_hr - resting_hr) / (max_hr - resting_hr)
    return duration_min * hr_fraction * math.exp(1.92 * hr_fraction)


def calc_ewma_series(values: Sequence[float | None], tau: int) -> list[float]:
    """Exponentially weighted moving average with time constant tau (days)."""
    result = []
    ewma = 0.0
    for v in values:
        if v is None:
            v = 0.0
        ewma = ewma + (v - ewma) / tau
        result.append(round(ewma, 4))
    return result


def calc_acwr(atl: float, ctl: float) -> float | None:
    """Acute:Chronic Workload Ratio. None if CTL is zero."""
    if ctl == 0:
        return None
    return round(atl / ctl, 4)


def calc_monotony(daily_loads: Sequence[float]) -> float | None:
    """Foster (1998) monotony = mean / SD of 7-day window."""
    import statistics
    if len(daily_loads) < 2:
        return None
    mean = statistics.mean(daily_loads)
    stdev = statistics.stdev(daily_loads)
    if stdev == 0:
        return None
    return round(mean / stdev, 4)


def calc_strain(weekly_load: float, monotony: float) -> float:
    return round(weekly_load * monotony, 4)
```

**Step 3: Run tests, commit**

```bash
uv run pytest tests/analysis/test_training_load.py -v
git add backend/garminview/analysis/metrics/training_load.py
git commit -m "feat: training load metric formulas — TRIMP, EWMA, ACWR, monotony"
```

---

### Task 14: Sleep Science Metrics

**Files:**
- Create: `backend/garminview/analysis/metrics/sleep_science.py`
- Test: `backend/tests/analysis/test_sleep_science.py`

**Step 1: Write failing tests**

```python
def test_sleep_efficiency():
    from garminview.analysis.metrics.sleep_science import calc_sleep_efficiency
    # 7h sleep, 30min awake, 8h in bed
    eff = calc_sleep_efficiency(total_sleep_min=420, awake_min=30, time_in_bed_min=480)
    assert abs(eff - 87.5) < 0.1

def test_sleep_debt_positive():
    from garminview.analysis.metrics.sleep_science import calc_sleep_debt
    actual = [6.5, 7.0, 6.0, 7.5, 6.5, 7.0, 6.0]
    debt = calc_sleep_debt(actual_hours=actual, target_hours=8.0)
    assert debt > 0

def test_social_jet_lag():
    from garminview.analysis.metrics.sleep_science import calc_social_jet_lag
    weekday_mids = [2.0, 2.5, 2.0, 2.5, 2.0]  # 2am midpoint
    weekend_mids = [4.0, 4.5]  # 4am midpoint
    sjl = calc_social_jet_lag(weekday_mids, weekend_mids)
    assert abs(sjl - 2.0) < 0.5
```

**Step 2: Create analysis/metrics/sleep_science.py**

```python
import statistics
from typing import Sequence


def calc_sleep_efficiency(total_sleep_min: float, awake_min: float,
                          time_in_bed_min: float) -> float | None:
    if time_in_bed_min <= 0:
        return None
    return round((total_sleep_min - awake_min) / time_in_bed_min * 100, 2)


def calc_sleep_debt(actual_hours: Sequence[float],
                    target_hours: float = 8.0) -> float:
    """Cumulative debt in hours over the provided window."""
    return round(sum(max(0, target_hours - h) for h in actual_hours), 2)


def calc_social_jet_lag(weekday_midpoints: Sequence[float],
                        weekend_midpoints: Sequence[float]) -> float | None:
    """Absolute difference between mean weekend and weekday sleep midpoints (hours)."""
    if not weekday_midpoints or not weekend_midpoints:
        return None
    return round(abs(statistics.mean(weekend_midpoints) -
                     statistics.mean(weekday_midpoints)), 2)


def calc_sleep_regularity_index(sleep_states: Sequence[Sequence[int]]) -> float | None:
    """
    SRI (Phillips 2017): probability of same state (0=awake, 1=asleep)
    at same time across consecutive day pairs.
    sleep_states: list of daily binary arrays (1=asleep, 0=awake), same length.
    """
    if len(sleep_states) < 2:
        return None
    matches = 0
    total = 0
    for i in range(len(sleep_states) - 1):
        day_a, day_b = sleep_states[i], sleep_states[i + 1]
        for a, b in zip(day_a, day_b):
            if a == b:
                matches += 1
            total += 1
    if total == 0:
        return None
    return round(matches / total * 100, 2)
```

**Step 3: Run tests, commit**

```bash
uv run pytest tests/analysis/test_sleep_science.py -v
git commit -m "feat: sleep science metrics — efficiency, debt, SJL, SRI"
```

---

### Task 15: Cardiovascular + Composite Score Metrics

Follow same TDD pattern for:

```python
# analysis/metrics/cardiovascular.py
def calc_rhr_zscore(rhr: float, mean_30d: float, std_30d: float) -> float
def calc_hrv_cv(hrv_series: Sequence[float]) -> float
def calc_heart_rate_recovery(hr_at_end: int, hr_1min_post: int) -> int
def calc_cardiac_drift(first_half_ef: float, second_half_ef: float) -> float

# analysis/metrics/body_composition.py
def calc_lbm(weight_kg: float, fat_pct: float) -> float
def calc_ffmi(lbm_kg: float, height_m: float) -> float
def calc_weight_velocity(weights: Sequence[float], days: int) -> float

# analysis/metrics/composite_scores.py
def calc_readiness_composite(hrv_norm, rhr_norm, sleep_score, body_battery, stress) -> float
def calc_overtraining_risk(rhr_zscore, hrv_status, acwr, monotony) -> int  # 0-3
def calc_wellness_score(...) -> float
```

Write 2–3 unit tests per function. Commit after each file.

---

### Task 16: Trend Classifier

**Files:**
- Create: `backend/garminview/analysis/assessments/trend_classifier.py`
- Test: `backend/tests/analysis/test_trend_classifier.py`

**Step 1: Write failing test**

```python
def test_classify_improving_trend():
    from garminview.analysis.assessments.trend_classifier import classify_trend
    import datetime
    # Steadily improving RHR (decreasing = improving for RHR)
    series = [62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49]
    dates = [datetime.date(2026, 1, i+1) for i in range(len(series))]
    result = classify_trend(dates, series, lower_is_better=True)
    assert result.direction == "improving"
    assert result.p_value < 0.05

def test_insufficient_data():
    from garminview.analysis.assessments.trend_classifier import classify_trend
    import datetime
    dates = [datetime.date(2026, 1, i+1) for i in range(3)]
    result = classify_trend(dates, [50, 51, 50], lower_is_better=False)
    assert result.direction == "insufficient_data"
```

**Step 2: Create assessments/trend_classifier.py**

```python
from dataclasses import dataclass
from datetime import date
from typing import Sequence
import numpy as np
from scipy import stats


@dataclass
class TrendResult:
    direction: str  # improving / stable / declining / insufficient_data
    slope: float | None = None
    r_squared: float | None = None
    p_value: float | None = None


def classify_trend(dates: Sequence[date], values: Sequence[float],
                   lower_is_better: bool = False,
                   min_samples: int = 7) -> TrendResult:
    clean = [(d, v) for d, v in zip(dates, values) if v is not None]
    if len(clean) < min_samples:
        return TrendResult(direction="insufficient_data")

    xs = np.array([(d - clean[0][0]).days for d, _ in clean], dtype=float)
    ys = np.array([v for _, v in clean], dtype=float)
    slope, intercept, r, p, se = stats.linregress(xs, ys)

    if p > 0.05:
        return TrendResult(direction="stable", slope=slope, r_squared=r**2, p_value=p)

    if (slope < 0 and lower_is_better) or (slope > 0 and not lower_is_better):
        direction = "improving"
    else:
        direction = "declining"

    return TrendResult(direction=direction, slope=round(slope, 6),
                       r_squared=round(r**2, 4), p_value=round(p, 6))
```

**Step 3: Run tests, commit**

```bash
uv run pytest tests/analysis/test_trend_classifier.py -v
git commit -m "feat: trend classifier — OLS regression → improving/stable/declining"
```

---

### Task 17: Analysis Engine Orchestrator

**Files:**
- Create: `backend/garminview/analysis/engine.py`
- Test: `backend/tests/analysis/test_engine.py`

**Step 1: Write failing test**

```python
def test_engine_runs_without_data(session):
    from garminview.analysis.engine import AnalysisEngine
    engine = AnalysisEngine(session)
    engine.run_all()  # must not raise with empty DB
```

**Step 2: Create analysis/engine.py**

```python
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from garminview.models.health import DailySummary, Sleep, RestingHeartRate
from garminview.models.supplemental import HRVData
from garminview.models.derived import DailyDerived
from garminview.analysis.metrics.training_load import (
    calc_trimp, calc_ewma_series, calc_acwr, calc_monotony, calc_strain
)
from garminview.analysis.metrics.sleep_science import (
    calc_sleep_efficiency, calc_sleep_debt
)
from garminview.analysis.metrics.composite_scores import calc_readiness_composite
from garminview.core.logging import get_logger

log = get_logger(__name__)


class AnalysisEngine:
    def __init__(self, session: Session):
        self._session = session

    def run_all(self) -> None:
        log.info("analysis_engine_start")
        self._compute_daily_derived()
        self._compute_weekly_derived()
        self._run_trend_classifications()
        log.info("analysis_engine_complete")

    def _compute_daily_derived(self) -> None:
        from sqlalchemy.dialects.sqlite import insert as upsert
        start = self._get_earliest_date()
        if not start:
            return
        end = date.today()

        # Load full series for EWMA (history-dependent)
        summaries = {r.date: r for r in self._session.query(DailySummary).all()}
        sleeps = {r.date: r for r in self._session.query(Sleep).all()}
        rhrs = {r.date: r for r in self._session.query(RestingHeartRate).all()}
        hrvs = {r.date: r for r in self._session.query(HRVData).all()}

        all_dates = sorted(summaries.keys())
        trimp_series = [
            calc_trimp(
                duration_min=(summaries[d].intensity_min_moderate or 0) +
                             (summaries[d].intensity_min_vigorous or 0) * 2,
                avg_hr=summaries[d].hr_avg or 70,
                max_hr=summaries[d].hr_max or 180,
            ) if d in summaries else 0.0
            for d in all_dates
        ]
        atl_series = calc_ewma_series(trimp_series, tau=7)
        ctl_series = calc_ewma_series(trimp_series, tau=42)

        for i, d in enumerate(all_dates):
            atl = atl_series[i]
            ctl = ctl_series[i]
            sleep = sleeps.get(d)
            sleep_eff = None
            if sleep and sleep.total_sleep_min and sleep.awake_min:
                time_in_bed = (sleep.total_sleep_min + sleep.awake_min)
                sleep_eff = calc_sleep_efficiency(sleep.total_sleep_min,
                                                  sleep.awake_min, time_in_bed)

            row = {
                "date": d,
                "trimp": round(trimp_series[i], 4),
                "atl": atl,
                "ctl": ctl,
                "tsb": round(ctl - atl, 4),
                "acwr": calc_acwr(atl, ctl),
                "sleep_efficiency_pct": sleep_eff,
            }
            stmt = upsert(DailyDerived).values(**row)
            stmt = stmt.on_conflict_do_update(index_elements=["date"], set_=row)
            self._session.execute(stmt)

        self._session.commit()
        log.info("daily_derived_computed", count=len(all_dates))

    def _get_earliest_date(self) -> date | None:
        return self._session.execute(
            select(func.min(DailySummary.date))
        ).scalar()

    def _compute_weekly_derived(self) -> None:
        pass  # Phase 3 continuation

    def _run_trend_classifications(self) -> None:
        pass  # Phase 3 continuation
```

**Step 3: Run tests, commit**

```bash
uv run pytest tests/analysis/test_engine.py -v
git commit -m "feat: analysis engine orchestrator — daily derived metrics pipeline"
```

---

## Phase 4: FastAPI

### Task 18: FastAPI App + Health Check

**Files:**
- Create: `backend/garminview/api/__init__.py`
- Create: `backend/garminview/api/main.py`
- Create: `backend/garminview/api/deps.py`
- Test: `backend/tests/api/test_health_check.py`

**Step 1: Write failing test**

```python
# tests/api/test_health_check.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(engine):
    from garminview.api.main import create_app
    app = create_app(engine)
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**Step 2: Create api/deps.py**

```python
from sqlalchemy.orm import Session
from garminview.core.database import get_session_factory


def get_db(engine) -> Session:
    factory = get_session_factory(engine)
    with factory() as session:
        yield session
```

**Step 3: Create api/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from garminview.core.config import get_config
from garminview.core.logging import configure_logging


def create_app(engine: Engine | None = None) -> FastAPI:
    config = get_config()
    configure_logging(config.log_level)

    app = FastAPI(title="GarminView API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from garminview.api.routes import health, sync, admin
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(sync.router, prefix="/sync", tags=["sync"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])

    @app.get("/")
    def root():
        return {"status": "ok", "version": "1.0.0"}

    return app
```

**Step 4: Create routes/health.py** (minimal — returns daily summary)

```python
from fastapi import APIRouter, Depends
from datetime import date

router = APIRouter()

@router.get("/")
def health_check():
    return {"status": "ok"}

@router.get("/daily/{date_str}")
def daily_summary(date_str: str):
    # Stub — implemented fully in Phase 4
    return {"date": date_str, "data": {}}
```

**Step 5: Run tests, commit**

```bash
uv run pytest tests/api/test_health_check.py -v
git commit -m "feat: FastAPI app skeleton — health check, CORS, router structure"
```

---

### Task 19: Core API Routes (Health, Activities, Training, Body)

For each domain, follow this pattern:

1. Write Pydantic response schema in `api/schemas/<domain>.py`
2. Write route handler in `api/routes/<domain>.py` querying SQLAlchemy models
3. Write integration test using `AsyncClient` + in-memory DB with seed data
4. Commit

**api/schemas/health.py** example:

```python
from pydantic import BaseModel
from datetime import date

class DailySummaryResponse(BaseModel):
    date: date
    steps: int | None
    hr_resting: int | None
    stress_avg: int | None
    body_battery_max: int | None
    sleep_score: int | None
    wellness_score: float | None

    model_config = {"from_attributes": True}
```

Routes to implement:
- `GET /health/daily?start=&end=` → list of DailySummaryResponse
- `GET /health/sleep?start=&end=` → sleep records with stage breakdown
- `GET /activities?start=&end=&type=` → paginated activity list
- `GET /activities/{id}` → activity detail with laps + HR zones
- `GET /training/load?start=&end=` → ATL/CTL/TSB series
- `GET /training/readiness?start=&end=` → readiness scores
- `GET /body/weight?start=&end=` → weight + body comp trend
- `GET /body/composition?start=&end=` → full body composition series

---

### Task 20: Admin Routes + SSE Sync Stream

**Files:**
- Create: `backend/garminview/api/routes/admin.py`
- Create: `backend/garminview/api/routes/sync.py`

**admin.py** key endpoints:

```python
@router.get("/config")
def get_all_config(session: Session = Depends(get_db)):
    rows = session.query(AppConfig).order_by(AppConfig.category, AppConfig.key).all()
    return {"config": [r.__dict__ for r in rows]}

@router.put("/config/{key}")
def update_config(key: str, value: str, session: Session = Depends(get_db)):
    row = session.get(AppConfig, key)
    if not row:
        raise HTTPException(404, "Config key not found")
    row.value = value
    row.updated_at = datetime.now(timezone.utc)
    session.commit()
    return {"key": key, "value": value}

@router.get("/schedules")
def list_schedules(session: Session = Depends(get_db)): ...

@router.put("/schedules/{id}")
def update_schedule(id: int, cron: str, enabled: bool, session: Session = Depends(get_db)): ...

@router.post("/schedules/{id}/run")
def trigger_schedule(id: int): ...

@router.get("/schema-version")
def schema_version(session: Session = Depends(get_db)): ...
```

**sync.py** — SSE stream:

```python
from fastapi.responses import StreamingResponse
import asyncio

@router.get("/stream")
async def sync_stream():
    async def event_generator():
        # Yields SSE events: sync progress, completion, errors
        while True:
            # Check sync_log for running jobs
            await asyncio.sleep(1)
            yield f"data: {{\"status\": \"idle\"}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Commit admin + sync routes together.

---

### Task 21: Assessments, Correlations, Export, Data Quality Routes

Follow same pattern — Pydantic schema + route handler + integration test for each:

- `GET /assessments?period_type=weekly&start=&end=`
- `GET /correlations/matrix` — precomputed correlation results
- `GET /correlations/scatter?metric_a=sleep_score&metric_b=hrv_rmssd`
- `GET /data-quality/completeness?start=&end=`
- `GET /data-quality/flags`
- `GET /export/csv?metrics=&start=&end=`
- `GET /export/json?metrics=&start=&end=`

Commit after each group.

---

## Phase 5: Vue.js Frontend

### Task 22: Vue.js Project Scaffold

**Step 1: Scaffold**

```bash
cd /home/jcz/Github/garminview
npm create vue@latest frontend -- --typescript --router --pinia --vitest
cd frontend && npm install
npm install vue-echarts echarts axios dayjs
```

**Step 2: Configure API base URL**

```typescript
// src/api/client.ts
import axios from "axios"

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  withCredentials: true,
})
```

**Step 3: Create Pinia stores**

```typescript
// src/stores/dateRange.ts
import { defineStore } from "pinia"
import { ref, computed } from "vue"
import dayjs from "dayjs"

export const useDateRangeStore = defineStore("dateRange", () => {
  const endDate = ref(dayjs().format("YYYY-MM-DD"))
  const startDate = ref(dayjs().subtract(90, "day").format("YYYY-MM-DD"))
  const preset = ref<"7d" | "30d" | "90d" | "1y" | "custom">("90d")

  function setPreset(p: typeof preset.value) {
    preset.value = p
    endDate.value = dayjs().format("YYYY-MM-DD")
    const days = { "7d": 7, "30d": 30, "90d": 90, "1y": 365 }
    if (p !== "custom") startDate.value = dayjs().subtract(days[p], "day").format("YYYY-MM-DD")
  }

  return { startDate, endDate, preset, setPreset }
})
```

```typescript
// src/stores/sync.ts
import { defineStore } from "pinia"
import { ref } from "vue"

export const useSyncStore = defineStore("sync", () => {
  const status = ref<"idle" | "running" | "error">("idle")
  const lastSync = ref<string | null>(null)
  const progress = ref("")

  function connectSSE() {
    const es = new EventSource("/sync/stream")
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      status.value = data.status
      progress.value = data.message ?? ""
    }
  }

  return { status, lastSync, progress, connectSSE }
})
```

**Step 4: Configure router**

```typescript
// src/router/index.ts
import { createRouter, createWebHistory } from "vue-router"

const routes = [
  { path: "/", component: () => import("@/views/DailyOverview.vue") },
  { path: "/sleep", component: () => import("@/views/SleepDashboard.vue") },
  { path: "/body", component: () => import("@/views/WeightBodyComp.vue") },
  { path: "/cardio", component: () => import("@/views/CardiovascularDashboard.vue") },
  { path: "/training", component: () => import("@/views/TrainingLoadDashboard.vue") },
  { path: "/activities", component: () => import("@/views/ActivitySummary.vue") },
  { path: "/running", component: () => import("@/views/RunningDashboard.vue") },
  { path: "/recovery", component: () => import("@/views/RecoveryStress.vue") },
  { path: "/trends", component: () => import("@/views/LongTermTrends.vue") },
  { path: "/correlations", component: () => import("@/views/CorrelationExplorer.vue") },
  { path: "/assessments", component: () => import("@/views/AssessmentsGoals.vue") },
  { path: "/data-quality", component: () => import("@/views/DataQuality.vue") },
  { path: "/admin", component: () => import("@/views/Admin.vue") },
]
export default createRouter({ history: createWebHistory(), routes })
```

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: Vue.js scaffold — router, Pinia stores, API client, ECharts"
```

---

### Task 23: Shared Chart Components

**Files:**
- Create: `frontend/src/components/charts/TimeSeriesChart.vue`
- Create: `frontend/src/components/charts/PMCChart.vue`
- Create: `frontend/src/components/charts/CalendarHeatmap.vue`
- Create: `frontend/src/components/charts/StackedBarChart.vue`
- Create: `frontend/src/components/ui/MetricCard.vue`
- Create: `frontend/src/components/ui/DateRangePicker.vue`

**TimeSeriesChart.vue** (core reusable component):

```vue
<template>
  <v-chart :option="option" autoresize style="height: 300px" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

interface Series {
  name: string
  data: [string, number | null][]
  color?: string
  smooth?: boolean
}

const props = defineProps<{
  series: Series[]
  yAxisLabel?: string
  showRollingAvg?: boolean
  rollingDays?: number
}>()

const option = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { data: props.series.map(s => s.name) },
  dataZoom: [{ type: "inside" }],
  xAxis: { type: "time" },
  yAxis: { type: "value", name: props.yAxisLabel },
  series: props.series.map(s => ({
    name: s.name,
    type: "line",
    data: s.data,
    smooth: s.smooth ?? false,
    itemStyle: s.color ? { color: s.color } : undefined,
    connectNulls: false,
  })),
}))
</script>
```

**MetricCard.vue**:

```vue
<template>
  <div class="metric-card">
    <div class="metric-label">{{ label }}</div>
    <div class="metric-value">{{ formattedValue }}</div>
    <div class="metric-trend" :class="trendClass">{{ trendLabel }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{
  label: string
  value: number | null
  unit?: string
  trend?: "improving" | "stable" | "declining" | "insufficient_data"
}>()

const formattedValue = computed(() =>
  props.value != null ? `${props.value}${props.unit ?? ""}` : "—"
)
const trendClass = computed(() => ({
  "trend-up": props.trend === "improving",
  "trend-down": props.trend === "declining",
  "trend-flat": props.trend === "stable",
}))
const trendLabel = computed(() => {
  const map = { improving: "↑ Improving", declining: "↓ Declining",
                stable: "→ Stable", insufficient_data: "" }
  return props.trend ? map[props.trend] : ""
})
</script>
```

**Step: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: shared chart components — TimeSeriesChart, MetricCard, DateRangePicker"
```

---

### Task 24: Dashboard Views

Implement each view using `useMetricData` composable:

```typescript
// src/composables/useMetricData.ts
import { ref, watch } from "vue"
import { api } from "@/api/client"
import { useDateRangeStore } from "@/stores/dateRange"

export function useMetricData<T>(endpoint: string) {
  const store = useDateRangeStore()
  const data = ref<T | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetch() {
    loading.value = true
    error.value = null
    try {
      const res = await api.get(endpoint, {
        params: { start: store.startDate, end: store.endDate }
      })
      data.value = res.data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  watch([() => store.startDate, () => store.endDate], fetch, { immediate: true })
  return { data, loading, error, fetch }
}
```

**DailyOverview.vue** structure:

```vue
<template>
  <div class="dashboard">
    <DateRangePicker />
    <div class="metric-grid">
      <MetricCard label="Steps" :value="today?.steps" unit=" steps" :trend="trends?.steps" />
      <MetricCard label="RHR" :value="today?.hr_resting" unit=" bpm" :trend="trends?.rhr" />
      <MetricCard label="Sleep" :value="today?.sleep_score" unit="/100" :trend="trends?.sleep" />
      <MetricCard label="HRV" :value="today?.hrv" unit=" ms" :trend="trends?.hrv" />
      <MetricCard label="Stress" :value="today?.stress_avg" :trend="trends?.stress" />
      <MetricCard label="Body Battery" :value="today?.body_battery_max" :trend="null" />
    </div>
    <TimeSeriesChart :series="rhrSeries" y-axis-label="BPM" />
  </div>
</template>
```

Implement all 13 views (stub first, fill in progressively):
- DailyOverview, SleepDashboard, WeightBodyComp, CardiovascularDashboard
- TrainingLoadDashboard (PMCChart), ActivitySummary (CalendarHeatmap)
- RunningDashboard, RecoveryStress, LongTermTrends
- CorrelationExplorer, AssessmentsGoals, DataQuality, Admin

Commit after each view.

---

### Task 25: Admin View

**Admin.vue** — tabbed layout:

```vue
<template>
  <div class="admin">
    <nav class="tabs">
      <button v-for="tab in tabs" :key="tab.id"
              :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id">
        {{ tab.label }}
      </button>
    </nav>
    <ProfileEditor v-if="activeTab === 'profile'" />
    <ScheduleManager v-if="activeTab === 'schedules'" />
    <ConfigEditor v-if="activeTab === 'config'" />
    <BenchmarkTargets v-if="activeTab === 'benchmarks'" />
    <SchemaVersionLog v-if="activeTab === 'schema'" />
  </div>
</template>
```

**ConfigEditor.vue** — fetches `/admin/config`, renders grouped key-value pairs with inline edit:

```vue
<template>
  <div v-for="(items, category) in grouped" :key="category">
    <h3>{{ category }}</h3>
    <div v-for="item in items" :key="item.key" class="config-row">
      <span class="key">{{ item.key }}</span>
      <input v-model="item.value" @blur="save(item)" />
      <span class="desc">{{ item.description }}</span>
    </div>
  </div>
</template>
```

**ScheduleManager.vue** — table with cron expression editor, enable toggle, last/next run display, manual trigger button.

Commit admin components together.

---

## Phase 6: Marimo Notebooks

### Task 26: Shared Notebook Utilities

**Files:**
- Create: `backend/notebooks/shared/__init__.py`
- Create: `backend/notebooks/shared/db.py`
- Create: `backend/notebooks/shared/queries.py`

**shared/db.py**:

```python
from sqlalchemy.orm import Session
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory


def get_notebook_session() -> Session:
    """Get a DB session for notebook use, reading config from env/.env"""
    config = get_config()
    engine = create_db_engine(config)
    factory = get_session_factory(engine)
    return factory()
```

**shared/queries.py**:

```python
from datetime import date
from sqlalchemy.orm import Session
import pandas as pd
from garminview.models.health import DailySummary, Sleep
from garminview.models.derived import DailyDerived


def get_daily_summary_df(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.query(DailySummary).filter(
        DailySummary.date >= start, DailySummary.date <= end
    ).order_by(DailySummary.date).all()
    return pd.DataFrame([{c.key: getattr(r, c.key)
                          for c in DailySummary.__table__.columns} for r in rows])


def get_training_load_df(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.query(DailyDerived).filter(
        DailyDerived.date >= start, DailyDerived.date <= end
    ).order_by(DailyDerived.date).all()
    return pd.DataFrame([{"date": r.date, "atl": r.atl, "ctl": r.ctl,
                          "tsb": r.tsb, "acwr": r.acwr} for r in rows])
```

Commit shared utilities.

---

### Task 27: Health + Training Load Notebooks

**health_explorer.py** — Marimo notebook:

```python
import marimo as mo
import pandas as pd
from datetime import date, timedelta
from notebooks.shared.db import get_notebook_session
from notebooks.shared.queries import get_daily_summary_df

session = get_notebook_session()

date_range = mo.ui.date_range(
    start=date.today() - timedelta(days=90),
    stop=date.today(),
    label="Date Range"
)

metric = mo.ui.dropdown(
    ["steps", "hr_resting", "stress_avg", "sleep_score", "body_battery_max"],
    value="hr_resting",
    label="Metric"
)

mo.md("## Health Explorer")
date_range, metric

df = get_daily_summary_df(session, date_range.value[0], date_range.value[1])

import altair as alt
chart = alt.Chart(df).mark_line().encode(
    x="date:T", y=f"{metric.value}:Q"
).properties(width=700, height=300)
chart
```

Similarly implement:
- `training_load.py` — PMC chart (ATL/CTL/TSB) with adjustable τ sliders
- `activity_explorer.py` — filter by type/date, pace/HR/elevation charts
- `correlation_explorer.py` — any two metrics, scatter + regression

Commit all notebooks.

---

## Phase 7: Export & Polish

### Task 28: CSV + JSON Export

**Files:**
- Create: `backend/garminview/api/routes/export.py`
- Test: `backend/tests/api/test_export.py`

**export.py**:

```python
import csv, io, json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from datetime import date
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/csv")
def export_csv(start: date, end: date, metrics: str = "daily_summary",
               session: Session = Depends(get_db)):
    output = io.StringIO()
    # Query relevant model, write to CSV
    rows = _query_metric(session, metrics, start, end)
    if not rows:
        return StreamingResponse(iter([""]), media_type="text/csv")
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={metrics}_{start}_{end}.csv"}
    )
```

Write test asserting CSV response has correct headers and rows. Commit.

---

### Task 29: PDF Report Generation

**Files:**
- Create: `backend/garminview/export/pdf_generator.py`
- Create: `backend/garminview/export/templates/weekly_report.html`

```python
# export/pdf_generator.py
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"


def generate_weekly_pdf(data: dict) -> bytes:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("weekly_report.html")
    html_content = template.render(**data)
    return HTML(string=html_content).write_pdf()
```

Commit export layer.

---

## Phase 8: Validation Suite

### Task 30: GarminDB Comparison Suite

**Files:**
- Create: `backend/tests/validation/run_garmindb.py`
- Create: `backend/tests/validation/run_garminview.py`
- Create: `backend/tests/validation/compare.py`

**compare.py** — diff tables between two DB connections:

```python
import pandas as pd
from sqlalchemy import create_engine, text


def compare_table(garmindb_engine, garminview_engine,
                  garmindb_table: str, garminview_table: str,
                  key_cols: list[str]) -> dict:
    df_gdb = pd.read_sql_table(garmindb_table, garmindb_engine)
    df_gv = pd.read_sql_table(garminview_table, garminview_engine)

    df_gdb = df_gdb.set_index(key_cols).sort_index()
    df_gv = df_gv.set_index(key_cols).sort_index()

    common_cols = list(set(df_gdb.columns) & set(df_gv.columns))
    diff = (df_gdb[common_cols] - df_gv[common_cols]).abs()

    return {
        "garmindb_rows": len(df_gdb),
        "garminview_rows": len(df_gv),
        "missing_in_garminview": len(df_gdb) - len(df_gv),
        "max_diff_per_col": diff.max().to_dict(),
        "match": diff.max().max() < 0.01 and len(df_gdb) == len(df_gv),
    }
```

Run comparison:

```bash
python tests/validation/compare.py \
  --garmindb-path ~/HealthData/DBs/garmin.db \
  --garminview-path garminview.db \
  --tables daily_summary sleep weight resting_heart_rate
```

Commit validation suite.

---

## Running the Full Stack

```bash
# Backend — use uv for all Python tooling
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
alembic upgrade head
uv run uvicorn garminview.api.main:create_app --factory --reload --port 8000

# Tests
uv run pytest

# Frontend
cd frontend
npm run dev   # port 5173

# Run ingestion (first time)
uv run python -c "
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory
from garminview.ingestion.orchestrator import IngestionOrchestrator
from datetime import date

cfg = get_config()
engine = create_db_engine(cfg)
factory = get_session_factory(engine)
with factory() as session:
    orch = IngestionOrchestrator(session, cfg.health_data_dir)
    orch.run_full(date(2020, 1, 1), date.today())
"

# Marimo notebooks — uv-managed
uv run marimo run notebooks/health_explorer.py
uv run marimo run notebooks/training_load.py
uv run marimo run notebooks/activity_explorer.py
uv run marimo run notebooks/correlation_explorer.py
```
