# Actalog Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull workout data from a self-hosted Actalog instance into garminview for storage, analysis, and cross-referencing with Garmin biometric data.

**Architecture:** Six new `actalog_*` SQLAlchemy models stored in their own file. A dedicated HTTP client handles JWT auth with refresh-token fallback. A sync orchestrator orchestrates the full fetch-upsert-PR-aggregate cycle. FastAPI routes expose data + admin endpoints. A six-tab Vue dashboard (workouts, movement progress, WOD progress, PRs, cross-reference, calendar+session vitals) consumes those routes.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.x, Alembic, httpx, tenacity, APScheduler (IntervalTrigger), Vue 3 Composition API, Pinia, vue-echarts (ECharts)

---

## Chunk 1: Models + Alembic Migration

### File Map
- Create: `backend/garminview/models/actalog.py`
- Modify: `backend/garminview/models/__init__.py`
- Create: `backend/alembic/versions/0002_add_actalog_tables.py`

---

### Task 1: SQLAlchemy models for six actalog tables

**Files:**
- Create: `backend/garminview/models/actalog.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models.py — add to existing file
def test_actalog_tables_created(engine):
    from sqlalchemy import inspect
    tables = inspect(engine).get_table_names()
    for t in [
        "actalog_workouts", "actalog_movements", "actalog_wods",
        "actalog_workout_movements", "actalog_workout_wods",
        "actalog_personal_records",
    ]:
        assert t in tables, f"Missing table: {t}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_models.py::test_actalog_tables_created -v
```

Expected: FAIL — tables do not exist yet.

- [ ] **Step 3: Write `backend/garminview/models/actalog.py`**

```python
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
```

- [ ] **Step 4: Update `backend/garminview/models/__init__.py`**

Add to the imports and `__all__` list:

```python
# After the nutrition import line, add:
from garminview.models.actalog import (
    ActalogWorkout, ActalogMovement, ActalogWod,
    ActalogWorkoutMovement, ActalogWorkoutWod, ActalogPersonalRecord,
)
```

Add to `__all__`:
```python
    "ActalogWorkout", "ActalogMovement", "ActalogWod",
    "ActalogWorkoutMovement", "ActalogWorkoutWod", "ActalogPersonalRecord",
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_models.py::test_actalog_tables_created -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd backend && git add garminview/models/actalog.py garminview/models/__init__.py
git commit -m "feat: add actalog SQLAlchemy models (6 tables)"
```

---

### Task 2: Alembic migration for actalog tables

**Files:**
- Create: `backend/alembic/versions/0002_add_actalog_tables.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/alembic/versions/0002_add_actalog_tables.py
"""add actalog tables

Revision ID: 0002_add_actalog_tables
Revises: 0c196bca2dc0
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_actalog_tables"
down_revision = "0c196bca2dc0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actalog_workouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workout_date", sa.DateTime(), nullable=True),
        sa.Column("workout_name", sa.Text(), nullable=True),
        sa.Column("workout_type", sa.String(32), nullable=True),
        sa.Column("total_time_s", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actalog_workouts_date", "actalog_workouts", ["workout_date"])

    op.create_table(
        "actalog_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("movement_type", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "actalog_wods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("regime", sa.String(64), nullable=True),
        sa.Column("score_type", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "actalog_workout_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workout_id", sa.Integer(), sa.ForeignKey("actalog_workouts.id"), nullable=True),
        sa.Column("movement_id", sa.Integer(), sa.ForeignKey("actalog_movements.id"), nullable=True),
        sa.Column("sets", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("time_s", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("rpe", sa.Integer(), nullable=True),
        sa.Column("is_pr", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actalog_wm_workout", "actalog_workout_movements", ["workout_id"])
    op.create_index("ix_actalog_wm_movement", "actalog_workout_movements", ["movement_id"])

    op.create_table(
        "actalog_workout_wods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workout_id", sa.Integer(), sa.ForeignKey("actalog_workouts.id"), nullable=True),
        sa.Column("wod_id", sa.Integer(), sa.ForeignKey("actalog_wods.id"), nullable=True),
        sa.Column("score_value", sa.Text(), nullable=True),
        sa.Column("time_s", sa.Integer(), nullable=True),
        sa.Column("rounds", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("rpe", sa.Integer(), nullable=True),
        sa.Column("is_pr", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actalog_ww_workout", "actalog_workout_wods", ["workout_id"])

    op.create_table(
        "actalog_personal_records",
        sa.Column("movement_id", sa.Integer(), sa.ForeignKey("actalog_movements.id"), nullable=False),
        sa.Column("max_weight_kg", sa.Float(), nullable=True),
        sa.Column("max_reps", sa.Integer(), nullable=True),
        sa.Column("best_time_s", sa.Integer(), nullable=True),
        sa.Column("workout_id", sa.Integer(), sa.ForeignKey("actalog_workouts.id"), nullable=True),
        sa.Column("workout_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("movement_id"),
    )


def downgrade() -> None:
    op.drop_table("actalog_personal_records")
    op.drop_index("ix_actalog_ww_workout", "actalog_workout_wods")
    op.drop_table("actalog_workout_wods")
    op.drop_index("ix_actalog_wm_movement", "actalog_workout_movements")
    op.drop_index("ix_actalog_wm_workout", "actalog_workout_movements")
    op.drop_table("actalog_workout_movements")
    op.drop_table("actalog_wods")
    op.drop_table("actalog_movements")
    op.drop_index("ix_actalog_workouts_date", "actalog_workouts")
    op.drop_table("actalog_workouts")
```

- [ ] **Step 2: Apply migration to dev DB**

```bash
cd backend && uv run alembic upgrade head
```

Expected: "Running upgrade 0c196bca2dc0 -> 0002_add_actalog_tables"

- [ ] **Step 3: Commit**

```bash
cd backend && git add alembic/versions/0002_add_actalog_tables.py
git commit -m "feat: alembic migration for actalog tables"
```

---

## Chunk 2: HTTP Client

### File Map
- Create: `backend/garminview/ingestion/actalog_client.py`
- Create: `backend/tests/ingestion/test_actalog_client.py`

---

### Task 3: Actalog HTTP client with JWT auth and retry

**Files:**
- Create: `backend/garminview/ingestion/actalog_client.py`

The client handles:
1. Token refresh → login fallback → in-memory access token
2. Paginated `GET /api/workouts`
3. Single workout detail `GET /api/workouts/{id}`
4. PR movements `GET /api/pr-movements`
5. `tenacity` retry on HTTP 429

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/ingestion/test_actalog_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from garminview.ingestion.actalog_client import ActalogClient


@pytest.mark.asyncio
async def test_login_sends_remember_me():
    """Login must include remember_me: true to receive a refresh token."""
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "acc123",
        "refresh_token": "ref456",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        token = await client._login()
        call_json = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
        assert call_json.get("remember_me") is True
        assert token == "acc123"
        assert client.refresh_token == "ref456"


@pytest.mark.asyncio
async def test_refresh_returns_access_token():
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw",
                           refresh_token="old_ref")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "new_acc"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        token = await client._refresh()
        assert token == "new_acc"


@pytest.mark.asyncio
async def test_authenticate_uses_refresh_when_available():
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw",
                           refresh_token="ref")
    client._refresh = AsyncMock(return_value="acc_from_refresh")
    client._login = AsyncMock(return_value="acc_from_login")

    token = await client.authenticate()
    assert token == "acc_from_refresh"
    client._login.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_falls_back_to_login_on_refresh_failure():
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw",
                           refresh_token="bad_ref")
    client._refresh = AsyncMock(side_effect=Exception("401"))
    client._login = AsyncMock(return_value="acc_from_login")

    token = await client.authenticate()
    assert token == "acc_from_login"


@pytest.mark.asyncio
async def test_list_workouts_paginates():
    """Should keep fetching until an empty page is returned."""
    client = ActalogClient(base_url="https://test.example", email="u@x.com", password="pw")
    client._access_token = "tok"

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = [{"id": 1}, {"id": 2}]
    page1.raise_for_status = MagicMock()

    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = []
    page2.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[page1, page2]):
        workouts = await client.list_workouts()
        assert len(workouts) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/ingestion/test_actalog_client.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Write `backend/garminview/ingestion/actalog_client.py`**

```python
from __future__ import annotations
import httpx
from tenacity import retry, retry_if_exception, wait_exponential, stop_after_attempt
import logging

logger = logging.getLogger(__name__)

LBS_TO_KG = 0.453592


def _is_429(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


_retry = retry(
    retry=retry_if_exception(_is_429),
    wait=wait_exponential(multiplier=1, min=30, max=300),
    stop=stop_after_attempt(5),
    reraise=True,
)


class ActalogClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        refresh_token: str | None = None,
        weight_unit: str = "kg",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.refresh_token = refresh_token
        self.weight_unit = weight_unit
        self._access_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────

    async def _login(self) -> str:
        async with httpx.AsyncClient() as http:
            r = await http.post(
                f"{self.base_url}/api/auth/login",
                json={"email": self.email, "password": self.password, "remember_me": True},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            self.refresh_token = data.get("refresh_token")
            return data["access_token"]

    async def _refresh(self) -> str:
        async with httpx.AsyncClient() as http:
            r = await http.post(
                f"{self.base_url}/api/auth/refresh",
                json={"refresh_token": self.refresh_token},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()["access_token"]

    async def authenticate(self) -> str:
        """Return a valid access token, refreshing or logging in as needed."""
        if self.refresh_token:
            try:
                self._access_token = await self._refresh()
                return self._access_token
            except Exception:
                logger.warning("Actalog token refresh failed; falling back to login")
        self._access_token = await self._login()
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    # ── Data fetching ──────────────────────────────────────────────────

    @_retry
    async def list_workouts(self, page_size: int = 100) -> list[dict]:
        """Fetch all workout list entries via pagination."""
        results = []
        page = 1
        async with httpx.AsyncClient() as http:
            while True:
                r = await http.get(
                    f"{self.base_url}/api/workouts",
                    headers=self._auth_headers(),
                    params={"page": page, "page_size": page_size},
                    timeout=30,
                )
                r.raise_for_status()
                batch = r.json()
                if not batch:
                    break
                results.extend(batch)
                if len(batch) < page_size:
                    break
                page += 1
        return results

    @_retry
    async def get_workout(self, workout_id: int) -> dict:
        """Fetch full workout detail including embedded movements and WODs."""
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{self.base_url}/api/workouts/{workout_id}",
                headers=self._auth_headers(),
                timeout=15,
            )
            r.raise_for_status()
            return r.json()

    @_retry
    async def list_pr_movements(self) -> list[dict]:
        """Fetch pre-aggregated MovementPRSummary rows from /api/pr-movements."""
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{self.base_url}/api/pr-movements",
                headers=self._auth_headers(),
                timeout=15,
            )
            r.raise_for_status()
            return r.json()

    def convert_weight(self, raw: float | None) -> float | None:
        """Convert raw weight value to kg based on configured unit."""
        if raw is None:
            return None
        if self.weight_unit == "lbs":
            return round(raw * LBS_TO_KG, 3)
        return raw
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/ingestion/test_actalog_client.py -v
```

Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
cd backend && git add garminview/ingestion/actalog_client.py tests/ingestion/test_actalog_client.py
git commit -m "feat: actalog HTTP client with JWT auth and retry"
```

---

## Chunk 3: Sync Orchestrator

### File Map
- Create: `backend/garminview/ingestion/actalog_sync.py`
- Create: `backend/tests/ingestion/test_actalog_sync.py`

---

### Task 4: Sync orchestrator — upsert workouts, movements, WODs, and PRs

**Files:**
- Create: `backend/garminview/ingestion/actalog_sync.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/ingestion/test_actalog_sync.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from garminview.ingestion.actalog_sync import ActalogSync
import garminview.models  # noqa: registers all models
from garminview.core.database import Base


def make_workout_detail(workout_id: int, with_movement: bool = True) -> dict:
    detail = {
        "id": workout_id,
        "date": "2026-01-15T09:00:00Z",
        "name": "Morning Strength",
        "type": "strength",
        "duration": 3600,
        "notes": "Felt good",
        "movements": [],
        "wods": [],
    }
    if with_movement:
        detail["movements"] = [{
            "id": 101,
            "movement": {"id": 10, "name": "Back Squat", "type": "weightlifting"},
            "sets": 3, "reps": 5, "weight": 100.0,
            "time": None, "distance": None, "rpe": 8,
            "is_pr": True, "order": 1,
        }]
    return detail


def test_upsert_idempotent(engine, session):
    sync = ActalogSync(session, weight_unit="kg")
    detail = make_workout_detail(1)

    sync._upsert_workout(detail)
    sync._upsert_workout(detail)  # second call must not raise or duplicate
    session.commit()

    from garminview.models.actalog import ActalogWorkout
    count = session.query(ActalogWorkout).count()
    assert count == 1


def test_weight_conversion_lbs(engine, session):
    sync = ActalogSync(session, weight_unit="lbs")
    detail = make_workout_detail(2)
    sync._upsert_workout(detail)
    session.commit()

    from garminview.models.actalog import ActalogWorkoutMovement
    wm = session.query(ActalogWorkoutMovement).first()
    assert wm is not None
    # 100 lbs → 45.359 kg
    assert abs(wm.weight_kg - 45.359) < 0.01


def test_weight_kg_unchanged(engine, session):
    sync = ActalogSync(session, weight_unit="kg")
    detail = make_workout_detail(3)
    sync._upsert_workout(detail)
    session.commit()

    from garminview.models.actalog import ActalogWorkoutMovement
    wm = session.query(ActalogWorkoutMovement).first()
    assert wm.weight_kg == 100.0


def test_pr_aggregation(engine, session):
    """After upsert, _refresh_prs should create one PR row per movement."""
    sync = ActalogSync(session, weight_unit="kg")
    detail = make_workout_detail(4)
    sync._upsert_workout(detail)
    session.commit()

    pr_summaries = [{"movement_id": 10, "best_weight": 100.0, "best_reps": 5, "last_pr_date": "2026-01-15"}]
    sync._refresh_prs(pr_summaries)
    session.commit()

    from garminview.models.actalog import ActalogPersonalRecord
    pr = session.query(ActalogPersonalRecord).filter_by(movement_id=10).first()
    assert pr is not None
    assert pr.max_weight_kg == 100.0
    # best_time_s derived from workout_movements — movement has time=None so NULL
    assert pr.best_time_s is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/ingestion/test_actalog_sync.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Write `backend/garminview/ingestion/actalog_sync.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from garminview.models.actalog import (
    ActalogWorkout, ActalogMovement, ActalogWod,
    ActalogWorkoutMovement, ActalogWorkoutWod, ActalogPersonalRecord,
)
from garminview.ingestion.actalog_client import ActalogClient
from garminview.ingestion.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

LBS_TO_KG = 0.453592


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def _parse_time_score(score: str | None) -> int | None:
    """Parse a mm:ss score string to seconds."""
    if not score:
        return None
    parts = score.split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass
    return None


class ActalogSync:
    def __init__(self, session: Session, weight_unit: str = "kg") -> None:
        self._session = session
        self._weight_unit = weight_unit

    def _to_kg(self, raw: float | None) -> float | None:
        if raw is None:
            return None
        if self._weight_unit == "lbs":
            return round(raw * LBS_TO_KG, 3)
        return raw

    def _upsert(self, model, pk_col: str, pk_val, data: dict) -> None:
        """Generic single-row upsert by integer PK."""
        row = self._session.get(model, pk_val)
        if row is None:
            row = model(**{pk_col: pk_val})
            self._session.add(row)
        for k, v in data.items():
            setattr(row, k, v)

    def _upsert_workout(self, detail: dict) -> None:
        """Upsert one full workout including embedded movements and WODs."""
        wid = detail["id"]
        duration = detail.get("duration") or detail.get("total_time_s")

        self._upsert(ActalogWorkout, "id", wid, {
            "workout_date": _parse_dt(detail.get("date")),
            "workout_name": detail.get("name"),
            "workout_type": detail.get("type"),
            "total_time_s": duration,
            "notes": detail.get("notes"),
            "synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })

        for m in detail.get("movements", []):
            mov = m.get("movement") or {}
            mid = mov.get("id") or m.get("movement_id")
            if mid:
                self._upsert(ActalogMovement, "id", mid, {
                    "name": mov.get("name"),
                    "movement_type": mov.get("type"),
                })
            raw_w = m.get("weight")
            self._upsert(ActalogWorkoutMovement, "id", m["id"], {
                "workout_id": wid,
                "movement_id": mid,
                "sets": m.get("sets"),
                "reps": m.get("reps"),
                "weight_kg": self._to_kg(raw_w),
                "time_s": m.get("time"),
                "distance_m": m.get("distance"),
                "rpe": m.get("rpe"),
                "is_pr": bool(m.get("is_pr", False)),
                "order_index": m.get("order"),
            })

        for w in detail.get("wods", []):
            wod = w.get("wod") or {}
            wodid = wod.get("id") or w.get("wod_id")
            if wodid:
                self._upsert(ActalogWod, "id", wodid, {
                    "name": wod.get("name"),
                    "regime": wod.get("regime"),
                    "score_type": wod.get("score_type"),
                })
            score_val = w.get("score") or w.get("score_value")
            raw_w = w.get("weight")
            self._upsert(ActalogWorkoutWod, "id", w["id"], {
                "workout_id": wid,
                "wod_id": wodid,
                "score_value": score_val,
                "time_s": _parse_time_score(score_val),
                "rounds": w.get("rounds"),
                "reps": w.get("reps"),
                "weight_kg": self._to_kg(raw_w),
                "rpe": w.get("rpe"),
                "is_pr": bool(w.get("is_pr", False)),
                "order_index": w.get("order"),
            })

    def _garmin_duration_fallback(self, workout_id: int) -> None:
        """Try to fill total_time_s from a same-day Garmin activity if null."""
        workout = self._session.get(ActalogWorkout, workout_id)
        if not workout or workout.total_time_s is not None or not workout.workout_date:
            return
        from garminview.models.activities import Activity
        day = workout.workout_date.date()
        matches = (
            self._session.query(Activity)
            .filter(Activity.start_time >= datetime.combine(day, datetime.min.time()))
            .filter(Activity.start_time < datetime.combine(day + timedelta(days=1), datetime.min.time()))
            .filter(Activity.elapsed_time_s.isnot(None))
            .all()
        )
        if len(matches) == 1:
            workout.total_time_s = matches[0].elapsed_time_s
            logger.info("Filled total_time_s from Garmin activity for workout %d", workout_id)

    def _refresh_prs(self, pr_summaries: list[dict]) -> None:
        """DELETE + INSERT actalog_personal_records from pr-movements data."""
        self._session.query(ActalogPersonalRecord).delete()

        for pr in pr_summaries:
            mid = pr.get("movement_id")
            if not mid:
                continue

            # Derive best_time_s from PR-flagged workout_movements
            best_time_row = self._session.execute(
                text(
                    "SELECT MIN(time_s) FROM actalog_workout_movements "
                    "WHERE movement_id = :mid AND is_pr = 1 AND time_s IS NOT NULL"
                ),
                {"mid": mid},
            ).fetchone()
            best_time_s = best_time_row[0] if best_time_row else None

            # Derive workout_id and workout_date from most recent PR movement
            best_workout_row = self._session.execute(
                text(
                    "SELECT wm.workout_id, w.workout_date "
                    "FROM actalog_workout_movements wm "
                    "JOIN actalog_workouts w ON w.id = wm.workout_id "
                    "WHERE wm.movement_id = :mid AND wm.is_pr = 1 "
                    "ORDER BY w.workout_date DESC LIMIT 1"
                ),
                {"mid": mid},
            ).fetchone()

            raw_w = pr.get("best_weight")
            self._session.add(ActalogPersonalRecord(
                movement_id=mid,
                max_weight_kg=self._to_kg(raw_w),
                max_reps=pr.get("best_reps"),
                best_time_s=best_time_s,
                workout_id=best_workout_row[0] if best_workout_row else None,
                workout_date=_parse_dt(str(best_workout_row[1])) if best_workout_row else _parse_dt(pr.get("last_pr_date")),
            ))

    async def run(self, client: ActalogClient, sync_log: SyncLogger) -> dict:
        """Execute a full sync. Returns counts dict."""
        counts = {"workouts": 0, "movements": 0, "wods": 0, "prs": 0, "errors": 0}
        try:
            await client.authenticate()
            workout_list = await client.list_workouts()

            for item in workout_list:
                try:
                    detail = await client.get_workout(item["id"])
                    self._upsert_workout(detail)
                    self._garmin_duration_fallback(item["id"])
                    self._session.flush()
                    counts["workouts"] += 1
                    sync_log.increment()
                except Exception as exc:
                    logger.warning("Failed to sync workout %s: %s", item.get("id"), exc)
                    counts["errors"] += 1

            self._session.commit()

            pr_summaries = await client.list_pr_movements()
            self._refresh_prs(pr_summaries)
            self._session.commit()
            counts["prs"] = len(pr_summaries)

        except Exception as exc:
            self._session.rollback()
            sync_log.fail(str(exc))
            raise

        sync_log.success()
        return counts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/ingestion/test_actalog_sync.py -v
```

Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
cd backend && git add garminview/ingestion/actalog_sync.py tests/ingestion/test_actalog_sync.py
git commit -m "feat: actalog sync orchestrator with upsert, PR aggregation, and Garmin fallback"
```

---

## Chunk 4: FastAPI Routes + Scheduler + Admin Endpoints

### File Map
- Create: `backend/garminview/api/schemas/actalog.py`
- Create: `backend/garminview/api/routes/actalog.py` — exports `router` (data, `/actalog/*`) and `admin_router` (admin, `/admin/actalog/*`)
- Modify: `backend/garminview/api/main.py` — register both routers, use lifespan for scheduler
- Create: `backend/tests/api/test_actalog.py`

---

### Task 5: Pydantic schemas for actalog responses

**Files:**
- Create: `backend/garminview/api/schemas/actalog.py`

> **Note on admin route paths:** The spec defines admin endpoints as `/admin/actalog/...`. `actalog.py` exports a second `admin_router = APIRouter()` for these routes (paths: `/config`, `/sync`, `/sync/status`, `/test-connection`). In `main.py` this is registered separately at prefix `/admin/actalog`, giving URLs `/admin/actalog/config` etc. The data router stays at prefix `/actalog`.

- [ ] **Step 1: Write `backend/garminview/api/schemas/actalog.py`**

No test needed for schemas alone — they are exercised by the route tests in Task 6.

```python
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, model_config


class WorkoutListItem(BaseModel):
    model_config = model_config(from_attributes=True)
    id: int
    workout_date: datetime | None
    workout_name: str | None
    workout_type: str | None
    total_time_s: int | None


class MovementItem(BaseModel):
    model_config = model_config(from_attributes=True)
    id: int
    workout_id: int | None
    movement_id: int | None
    sets: int | None
    reps: int | None
    weight_kg: float | None
    time_s: int | None
    distance_m: float | None
    rpe: int | None
    is_pr: bool
    order_index: int | None


class WodItem(BaseModel):
    model_config = model_config(from_attributes=True)
    id: int
    workout_id: int | None
    wod_id: int | None
    score_value: str | None
    time_s: int | None
    rounds: int | None
    reps: int | None
    weight_kg: float | None
    rpe: int | None
    is_pr: bool
    order_index: int | None


class WorkoutDetail(BaseModel):
    model_config = model_config(from_attributes=True)
    id: int
    workout_date: datetime | None
    workout_name: str | None
    workout_type: str | None
    total_time_s: int | None
    notes: str | None
    movements: list[MovementItem]
    wods: list[WodItem]


class SessionVitals(BaseModel):
    workout: WorkoutDetail
    has_vitals: bool
    hr_series: list[dict] = []
    body_battery: list[dict] = []
    stress: list[dict] = []


class MovementRef(BaseModel):
    model_config = model_config(from_attributes=True)
    id: int
    name: str | None
    movement_type: str | None


class MovementHistoryItem(BaseModel):
    model_config = model_config(from_attributes=True)
    id: int
    workout_id: int | None
    sets: int | None
    reps: int | None
    weight_kg: float | None
    time_s: int | None
    rpe: int | None
    is_pr: bool
    workout_date: datetime | None  # joined from workout


class PRItem(BaseModel):
    model_config = model_config(from_attributes=True)
    movement_id: int
    movement_name: str | None
    movement_type: str | None
    max_weight_kg: float | None
    max_reps: int | None
    best_time_s: int | None
    workout_date: datetime | None


class CrossRefItem(BaseModel):
    workout_date: datetime | None
    workout_name: str | None
    workout_type: str | None
    total_volume_kg: float | None
    body_battery_max: int | None
    hr_resting: int | None
    sleep_score: int | None
    stress_avg: int | None


class ActalogConfigOut(BaseModel):
    url: str | None
    email: str | None
    weight_unit: str | None
    sync_interval_hours: int | None
    sync_enabled: bool
    last_sync: str | None


class ActalogSyncStatus(BaseModel):
    last_sync: str | None
    status: str | None
    records_upserted: int | None
    error_message: str | None
```

- [ ] **Step 2: Commit**

```bash
cd backend && git add garminview/api/schemas/actalog.py
git commit -m "feat: actalog Pydantic response schemas"
```

---

### Task 6: FastAPI routes for actalog data and admin endpoints

**Files:**
- Create: `backend/garminview/api/routes/actalog.py`

- [ ] **Step 1: Write failing API tests**

```python
# backend/tests/api/test_actalog.py
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from garminview.api.main import create_app
from garminview.models.actalog import (
    ActalogWorkout, ActalogMovement, ActalogWorkoutMovement,
    ActalogWorkoutWod, ActalogWod,
)


def seed_workout(session, workout_id: int = 1) -> None:
    session.add(ActalogWorkout(
        id=workout_id,
        workout_date=datetime(2026, 1, 15, 9, 0),
        workout_name="Test",
        workout_type="strength",
        total_time_s=3600,
        synced_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    session.add(ActalogMovement(id=10, name="Back Squat", movement_type="weightlifting"))
    session.add(ActalogWorkoutMovement(
        id=101, workout_id=workout_id, movement_id=10,
        sets=3, reps=5, weight_kg=100.0, is_pr=True, order_index=1,
    ))
    session.commit()


@pytest.mark.asyncio
async def test_list_workouts_empty(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_workouts_returns_rows(engine, session):
    seed_workout(session)
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == 1


@pytest.mark.asyncio
async def test_workout_detail(engine, session):
    seed_workout(session)
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts/1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert len(body["movements"]) == 1
    assert body["movements"][0]["is_pr"] is True


@pytest.mark.asyncio
async def test_workout_not_found(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts/999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_session_vitals_no_duration(engine, session):
    """Workout with null total_time_s must return has_vitals=false."""
    session.add(ActalogWorkout(
        id=2, workout_date=datetime(2026, 1, 16, 9, 0),
        workout_name="No Duration", workout_type="metcon",
        total_time_s=None,
        synced_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    session.commit()
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts/2/session-vitals")
    assert r.status_code == 200
    assert r.json()["has_vitals"] is False
    assert r.json()["workout"]["id"] == 2


@pytest.mark.asyncio
async def test_admin_config_get(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/admin/actalog/config")
    assert r.status_code == 200
    body = r.json()
    assert "url" in body
    assert "password" not in body  # must be masked/omitted
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_actalog.py -v
```

Expected: FAIL — router not registered.

- [ ] **Step 3: Write `backend/garminview/api/routes/actalog.py`**

```python
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from garminview.api.deps import get_db
from garminview.models.actalog import (
    ActalogWorkout, ActalogMovement, ActalogWorkoutMovement,
    ActalogWorkoutWod, ActalogWod, ActalogPersonalRecord,
)
from garminview.models.config import AppConfig
from garminview.models.sync import SyncLog
from garminview.api.schemas.actalog import (
    WorkoutListItem, WorkoutDetail, MovementItem, WodItem,
    SessionVitals, MovementRef, MovementHistoryItem,
    PRItem, CrossRefItem, ActalogConfigOut, ActalogSyncStatus,
)

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────

def _get_cfg(session: Session, key: str) -> str | None:
    row = session.get(AppConfig, key)
    return row.value if row else None


def _movement_items(session: Session, workout_id: int) -> list[MovementItem]:
    rows = (
        session.query(ActalogWorkoutMovement)
        .filter(ActalogWorkoutMovement.workout_id == workout_id)
        .order_by(ActalogWorkoutMovement.order_index)
        .all()
    )
    return [MovementItem.model_validate(r) for r in rows]


def _wod_items(session: Session, workout_id: int) -> list[WodItem]:
    rows = (
        session.query(ActalogWorkoutWod)
        .filter(ActalogWorkoutWod.workout_id == workout_id)
        .order_by(ActalogWorkoutWod.order_index)
        .all()
    )
    return [WodItem.model_validate(r) for r in rows]


def _workout_detail(session: Session, workout: ActalogWorkout) -> WorkoutDetail:
    return WorkoutDetail(
        id=workout.id,
        workout_date=workout.workout_date,
        workout_name=workout.workout_name,
        workout_type=workout.workout_type,
        total_time_s=workout.total_time_s,
        notes=workout.notes,
        movements=_movement_items(session, workout.id),
        wods=_wod_items(session, workout.id),
    )


# ── Data endpoints ──────────────────────────────────────────────────────

@router.get("/workouts", response_model=list[WorkoutListItem])
def list_workouts(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0),
):
    q = session.query(ActalogWorkout)
    if start:
        q = q.filter(ActalogWorkout.workout_date >= datetime.combine(start, datetime.min.time()))
    if end:
        q = q.filter(ActalogWorkout.workout_date < datetime.combine(end + timedelta(days=1), datetime.min.time()))
    return q.order_by(ActalogWorkout.workout_date.desc()).offset(offset).limit(limit).all()


@router.get("/workouts/{workout_id}", response_model=WorkoutDetail)
def get_workout(workout_id: int, session: Annotated[Session, Depends(get_db)]):
    w = session.get(ActalogWorkout, workout_id)
    if not w:
        raise HTTPException(404, "Workout not found")
    return _workout_detail(session, w)


@router.get("/workouts/{workout_id}/session-vitals", response_model=SessionVitals)
def session_vitals(workout_id: int, session: Annotated[Session, Depends(get_db)]):
    w = session.get(ActalogWorkout, workout_id)
    if not w:
        raise HTTPException(404, "Workout not found")

    detail = _workout_detail(session, w)
    has_vitals = w.total_time_s is not None and w.workout_date is not None

    if not has_vitals:
        return SessionVitals(workout=detail, has_vitals=False)

    window_start = w.workout_date
    window_end = w.workout_date + timedelta(seconds=w.total_time_s)

    from garminview.models.monitoring import MonitoringHeartRate
    from garminview.models.supplemental import BodyBatteryEvent
    from garminview.models.health import Stress

    hr_rows = (
        session.query(MonitoringHeartRate)
        .filter(MonitoringHeartRate.timestamp >= window_start)
        .filter(MonitoringHeartRate.timestamp <= window_end)
        .order_by(MonitoringHeartRate.timestamp)
        .all()
    )
    bb_rows = (
        session.query(BodyBatteryEvent)
        .filter(BodyBatteryEvent.start >= window_start)
        .filter(BodyBatteryEvent.start <= window_end)
        .order_by(BodyBatteryEvent.start)
        .all()
    )
    stress_rows = (
        session.query(Stress)
        .filter(Stress.timestamp >= window_start)
        .filter(Stress.timestamp <= window_end)
        .order_by(Stress.timestamp)
        .all()
    )

    return SessionVitals(
        workout=detail,
        has_vitals=True,
        hr_series=[{"ts": r.timestamp.isoformat(), "hr": r.hr} for r in hr_rows],
        body_battery=[{"ts": r.start.isoformat(), "value": r.value, "type": r.event_type} for r in bb_rows],
        stress=[{"ts": r.timestamp.isoformat(), "level": r.stress_level} for r in stress_rows],
    )


@router.get("/movements", response_model=list[MovementRef])
def list_movements(session: Annotated[Session, Depends(get_db)]):
    return session.query(ActalogMovement).order_by(ActalogMovement.name).all()


@router.get("/movements/{movement_id}/history", response_model=list[MovementHistoryItem])
def movement_history(
    movement_id: int,
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = (
        session.query(
            ActalogWorkoutMovement,
            ActalogWorkout.workout_date,
        )
        .join(ActalogWorkout, ActalogWorkoutMovement.workout_id == ActalogWorkout.id)
        .filter(ActalogWorkoutMovement.movement_id == movement_id)
    )
    if start:
        q = q.filter(ActalogWorkout.workout_date >= datetime.combine(start, datetime.min.time()))
    if end:
        q = q.filter(ActalogWorkout.workout_date < datetime.combine(end + timedelta(days=1), datetime.min.time()))
    rows = q.order_by(ActalogWorkout.workout_date).all()
    result = []
    for wm, wdate in rows:
        item = MovementHistoryItem.model_validate(wm)
        item.workout_date = wdate
        result.append(item)
    return result


@router.get("/prs", response_model=list[PRItem])
def list_prs(session: Annotated[Session, Depends(get_db)]):
    rows = (
        session.query(ActalogPersonalRecord, ActalogMovement.name, ActalogMovement.movement_type)
        .join(ActalogMovement, ActalogPersonalRecord.movement_id == ActalogMovement.id)
        .order_by(ActalogMovement.name)
        .all()
    )
    result = []
    for pr, name, mtype in rows:
        result.append(PRItem(
            movement_id=pr.movement_id,
            movement_name=name,
            movement_type=mtype,
            max_weight_kg=pr.max_weight_kg,
            max_reps=pr.max_reps,
            best_time_s=pr.best_time_s,
            workout_date=pr.workout_date,
        ))
    return result


@router.get("/wods", response_model=list[dict])
def list_wods(session: Annotated[Session, Depends(get_db)]):
    """Return all WODs seen in logged workouts."""
    rows = session.query(ActalogWod).order_by(ActalogWod.name).all()
    return [{"id": r.id, "name": r.name, "regime": r.regime, "score_type": r.score_type} for r in rows]


@router.get("/wods/{wod_id}/history", response_model=list[dict])
def wod_history(
    wod_id: int,
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    q = (
        session.query(ActalogWorkoutWod, ActalogWorkout.workout_date)
        .join(ActalogWorkout, ActalogWorkoutWod.workout_id == ActalogWorkout.id)
        .filter(ActalogWorkoutWod.wod_id == wod_id)
    )
    if start:
        q = q.filter(ActalogWorkout.workout_date >= datetime.combine(start, datetime.min.time()))
    if end:
        q = q.filter(ActalogWorkout.workout_date < datetime.combine(end + timedelta(days=1), datetime.min.time()))
    return [
        {
            "id": ww.id, "workout_id": ww.workout_id, "wod_id": ww.wod_id,
            "score_value": ww.score_value, "time_s": ww.time_s,
            "rounds": ww.rounds, "reps": ww.reps, "rpe": ww.rpe,
            "is_pr": ww.is_pr, "workout_date": wdate.isoformat() if wdate else None,
        }
        for ww, wdate in q.order_by(ActalogWorkout.workout_date).all()
    ]


@router.get("/cross-reference", response_model=list[CrossRefItem])
def cross_reference(
    session: Annotated[Session, Depends(get_db)],
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    from garminview.models.health import DailySummary
    from sqlalchemy import cast, Date as SADate

    q = (
        session.query(
            ActalogWorkout.workout_date,
            ActalogWorkout.workout_name,
            ActalogWorkout.workout_type,
            func.sum(
                ActalogWorkoutMovement.sets * ActalogWorkoutMovement.reps * ActalogWorkoutMovement.weight_kg
            ).label("total_volume_kg"),
            DailySummary.body_battery_max,
            DailySummary.hr_resting,
            DailySummary.sleep_score,
            DailySummary.stress_avg,
        )
        .outerjoin(ActalogWorkoutMovement, ActalogWorkoutMovement.workout_id == ActalogWorkout.id)
        .outerjoin(
            DailySummary,
            cast(ActalogWorkout.workout_date, SADate) == DailySummary.date,
        )
        .group_by(
            ActalogWorkout.id, ActalogWorkout.workout_date, ActalogWorkout.workout_name,
            ActalogWorkout.workout_type, DailySummary.body_battery_max,
            DailySummary.hr_resting, DailySummary.sleep_score, DailySummary.stress_avg,
        )
    )
    if start:
        q = q.filter(ActalogWorkout.workout_date >= datetime.combine(start, datetime.min.time()))
    if end:
        q = q.filter(ActalogWorkout.workout_date < datetime.combine(end + timedelta(days=1), datetime.min.time()))

    return [
        CrossRefItem(
            workout_date=r[0], workout_name=r[1], workout_type=r[2],
            total_volume_kg=r[3], body_battery_max=r[4],
            hr_resting=r[5], sleep_score=r[6], stress_avg=r[7],
        )
        for r in q.order_by(ActalogWorkout.workout_date.desc()).all()
    ]


# ── Admin router — registered separately at prefix /admin/actalog ────────
# Resulting URLs: /admin/actalog/config, /admin/actalog/sync, etc.
# (spec §API Routes, Admin endpoints)

admin_router = APIRouter()


def _set_cfg(session: Session, key: str, value: str) -> None:
    row = session.get(AppConfig, key)
    if row is None:
        row = AppConfig(key=key, category="actalog", data_type="string")
        session.add(row)
    row.value = value
    row.updated_at = datetime.now()


@admin_router.get("/config", response_model=ActalogConfigOut)
def get_admin_config(session: Annotated[Session, Depends(get_db)]):
    return ActalogConfigOut(
        url=_get_cfg(session, "actalog_url"),
        email=_get_cfg(session, "actalog_email"),
        weight_unit=_get_cfg(session, "actalog_weight_unit") or "kg",
        sync_interval_hours=int(_get_cfg(session, "actalog_sync_interval_hours") or 24),
        sync_enabled=(_get_cfg(session, "actalog_sync_enabled") or "false").lower() == "true",
        last_sync=_get_cfg(session, "actalog_last_sync"),
    )


@admin_router.put("/config")
def update_admin_config(
    session: Annotated[Session, Depends(get_db)],
    url: str | None = None,
    email: str | None = None,
    password: str | None = None,
    weight_unit: str | None = None,
    sync_interval_hours: int | None = None,
    sync_enabled: bool | None = None,
):
    now = datetime.now()
    updates = {
        "actalog_url": url,
        "actalog_email": email,
        "actalog_password": password,
        "actalog_weight_unit": weight_unit,
        "actalog_sync_interval_hours": str(sync_interval_hours) if sync_interval_hours is not None else None,
        "actalog_sync_enabled": str(sync_enabled).lower() if sync_enabled is not None else None,
    }
    for key, val in updates.items():
        if val is None:
            continue
        row = session.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, category="actalog", data_type="string")
            session.add(row)
        row.value = val
        row.updated_at = now
    session.commit()
    return {"ok": True}


@admin_router.post("/sync")
async def trigger_sync(session: Annotated[Session, Depends(get_db)]):
    url = _get_cfg(session, "actalog_url")
    email = _get_cfg(session, "actalog_email")
    password = _get_cfg(session, "actalog_password")
    if not url or not email or not password:
        raise HTTPException(400, "Actalog not configured — set url, email, and password first")

    from garminview.ingestion.actalog_client import ActalogClient
    from garminview.ingestion.actalog_sync import ActalogSync
    from garminview.ingestion.sync_logger import SyncLogger

    weight_unit = _get_cfg(session, "actalog_weight_unit") or "kg"
    refresh_token = _get_cfg(session, "actalog_refresh_token")

    client = ActalogClient(
        base_url=url, email=email, password=password,
        refresh_token=refresh_token, weight_unit=weight_unit,
    )
    sync_log = SyncLogger(session, source="actalog", mode="full")
    orchestrator = ActalogSync(session, weight_unit=weight_unit)

    counts = await orchestrator.run(client, sync_log)

    if client.refresh_token and client.refresh_token != refresh_token:
        _set_cfg(session, "actalog_refresh_token", client.refresh_token)
    _set_cfg(session, "actalog_last_sync", datetime.now().isoformat())
    session.commit()

    return counts


@admin_router.post("/test-connection")
async def test_connection(
    session: Annotated[Session, Depends(get_db)],
    url: str | None = None,
    email: str | None = None,
    password: str | None = None,
):
    """Backend-side connection test — credentials stay on the server, no CORS issues."""
    target_url = url or _get_cfg(session, "actalog_url")
    target_email = email or _get_cfg(session, "actalog_email")
    target_password = password or _get_cfg(session, "actalog_password")
    if not target_url or not target_email or not target_password:
        raise HTTPException(400, "URL, email, and password required")
    from garminview.ingestion.actalog_client import ActalogClient
    client = ActalogClient(base_url=target_url, email=target_email, password=target_password)
    try:
        await client._login()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(400, f"Connection failed: {exc}")


@admin_router.get("/sync/status", response_model=ActalogSyncStatus)
def sync_status(session: Annotated[Session, Depends(get_db)]):
    log = (
        session.query(SyncLog)
        .filter(SyncLog.source == "actalog")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if not log:
        return ActalogSyncStatus(last_sync=None, status=None, records_upserted=None, error_message=None)
    return ActalogSyncStatus(
        last_sync=log.started_at.isoformat() if log.started_at else None,
        status=log.status,
        records_upserted=log.records_upserted,
        error_message=log.error_message,
    )
```

- [ ] **Step 4: Register both routers in `backend/garminview/api/main.py`**

In the `create_app` function, add after the existing `app.include_router` calls:

```python
    from garminview.api.routes import actalog as actalog_routes
    app.include_router(actalog_routes.router, prefix="/actalog", tags=["actalog"])
    app.include_router(actalog_routes.admin_router, prefix="/admin/actalog", tags=["actalog-admin"])
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/api/test_actalog.py -v
```

Expected: PASS (all 7 tests)

- [ ] **Step 6: Commit**

```bash
cd backend && git add garminview/api/schemas/actalog.py garminview/api/routes/actalog.py garminview/api/main.py tests/api/test_actalog.py
git commit -m "feat: actalog FastAPI routes and admin endpoints"
```

---

### Task 7: Wire APScheduler interval job for actalog sync

**Files:**
- Modify: `backend/garminview/core/startup.py`

- [ ] **Step 1: Read existing `startup.py`**

```bash
cat backend/garminview/core/startup.py
```

- [ ] **Step 2: Add actalog scheduler job**

In `startup.py`, add the following function and call it from wherever the app starts up. If `startup.py` doesn't yet wire a scheduler, create the pattern:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def start_scheduler(session_factory) -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()

    async def _actalog_job():
        with session_factory() as session:
            from garminview.models.config import AppConfig
            def cfg(key):
                row = session.get(AppConfig, key)
                return row.value if row else None

            if (cfg("actalog_sync_enabled") or "false").lower() != "true":
                return
            url = cfg("actalog_url")
            email = cfg("actalog_email")
            password = cfg("actalog_password")
            if not url or not email or not password:
                return

            from garminview.ingestion.actalog_client import ActalogClient
            from garminview.ingestion.actalog_sync import ActalogSync
            from garminview.ingestion.sync_logger import SyncLogger

            weight_unit = cfg("actalog_weight_unit") or "kg"
            refresh_token = cfg("actalog_refresh_token")
            client = ActalogClient(base_url=url, email=email, password=password,
                                   refresh_token=refresh_token, weight_unit=weight_unit)
            sync_log = SyncLogger(session, source="actalog", mode="full")
            orchestrator = ActalogSync(session, weight_unit=weight_unit)
            try:
                await orchestrator.run(client, sync_log)
                if client.refresh_token and client.refresh_token != refresh_token:
                    _set_actalog_cfg(session, "actalog_refresh_token", client.refresh_token)
                _set_actalog_cfg(session, "actalog_last_sync", __import__("datetime").datetime.now().isoformat())
                session.commit()
                logger.info("Actalog scheduled sync complete")
            except Exception as exc:
                logger.error("Actalog scheduled sync failed: %s", exc)


    def _set_actalog_cfg(session, key, value):
        from garminview.models.config import AppConfig
        row = session.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, category="actalog", data_type="string")
            session.add(row)
        row.value = value

    hours = 24  # default; overridden at runtime by app_config
    _scheduler.add_job(_actalog_job, IntervalTrigger(hours=hours), id="sync_actalog", replace_existing=True)
    _scheduler.start()
    logger.info("APScheduler started with actalog interval job (%dh)", hours)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
```

- [ ] **Step 3: Wire scheduler into `create_app` via lifespan in `main.py`**

Replace the `create_app` function signature and body to use FastAPI's lifespan context manager (the `@app.on_event` API was deprecated in FastAPI 0.93):

```python
from contextlib import asynccontextmanager

def create_app(engine: Engine | None = None) -> FastAPI:
    config = get_config()
    configure_logging(config.log_level)

    if engine is None:
        from garminview.core.database import create_db_engine
        engine = create_db_engine(config)

    factory = get_session_factory(engine)

    def get_db():
        with factory() as session:
            yield session

    from garminview.core.startup import start_scheduler, stop_scheduler

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        start_scheduler(factory)
        yield
        stop_scheduler()

    app = FastAPI(title="GarminView API", version="0.4.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from garminview.api.routes import (
        health_check, activities, training, body, admin, sync,
        assessments, export, nutrition,
    )
    from garminview.api.routes import actalog as actalog_routes

    app.include_router(health_check.router, prefix="/health", tags=["health"])
    app.include_router(activities.router, prefix="/activities", tags=["activities"])
    app.include_router(training.router, prefix="/training", tags=["training"])
    app.include_router(body.router, prefix="/body", tags=["body"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(sync.router, prefix="/sync", tags=["sync"])
    app.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
    app.include_router(export.router)
    app.include_router(nutrition.router, prefix="/nutrition", tags=["nutrition"])
    app.include_router(actalog_routes.router, prefix="/actalog", tags=["actalog"])
    app.include_router(actalog_routes.admin_router, prefix="/admin/actalog", tags=["actalog-admin"])

    app.dependency_overrides[deps.get_db] = get_db

    @app.get("/")
    def root():
        return {"status": "ok", "version": "0.4.0"}

    return app
```

> **Note on scheduler interval:** The job fires every 24 hours (fixed at startup). The `actalog_sync_interval_hours` config value is respected inside the job as a "skip if disabled" check. Changing the interval in the Admin UI takes effect on the next server restart. Hotly reconfiguring APScheduler triggers is a future enhancement.

- [ ] **Step 4: Run full test suite to confirm nothing is broken**

```bash
cd backend && uv run pytest -q
```

Expected: all existing tests pass + actalog tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend && git add garminview/core/startup.py garminview/api/main.py
git commit -m "feat: APScheduler interval job for actalog sync"
```

---

## Chunk 5: Vue Frontend

### File Map
- Create: `frontend/src/stores/actalog.ts`
- Create: `frontend/src/views/ActalogDashboard.vue`
- Modify: `frontend/src/router/index.ts` — add `/actalog` route
- Modify: `frontend/src/App.vue` — add sidebar nav entry

---

### Task 8: Actalog Pinia store

**Files:**
- Create: `frontend/src/stores/actalog.ts`

- [ ] **Step 1: Write `frontend/src/stores/actalog.ts`**

```typescript
import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { api } from "@/api/client"

export interface WorkoutListItem {
  id: number
  workout_date: string | null
  workout_name: string | null
  workout_type: string | null
  total_time_s: number | null
}

export interface MovementItem {
  id: number
  workout_id: number | null
  movement_id: number | null
  sets: number | null
  reps: number | null
  weight_kg: number | null
  time_s: number | null
  rpe: number | null
  is_pr: boolean
  order_index: number | null
}

export interface WodItem {
  id: number
  workout_id: number | null
  wod_id: number | null
  score_value: string | null
  time_s: number | null
  rounds: number | null
  reps: number | null
  weight_kg: number | null
  rpe: number | null
  is_pr: boolean
  order_index: number | null
}

export interface WorkoutDetail extends WorkoutListItem {
  notes: string | null
  movements: MovementItem[]
  wods: WodItem[]
}

export interface SessionVitals {
  workout: WorkoutDetail
  has_vitals: boolean
  hr_series: { ts: string; hr: number }[]
  body_battery: { ts: string; value: number; type: string }[]
  stress: { ts: string; level: number }[]
}

export interface PRItem {
  movement_id: number
  movement_name: string | null
  movement_type: string | null
  max_weight_kg: number | null
  max_reps: number | null
  best_time_s: number | null
  workout_date: string | null
}

export interface CrossRefItem {
  workout_date: string | null
  workout_name: string | null
  workout_type: string | null
  total_volume_kg: number | null
  body_battery_max: number | null
  hr_resting: number | null
  sleep_score: number | null
  stress_avg: number | null
}

export interface ActalogConfig {
  url: string | null
  email: string | null
  weight_unit: string | null
  sync_interval_hours: number | null
  sync_enabled: boolean
  last_sync: string | null
}

export const useActalogStore = defineStore("actalog", () => {
  const workouts = ref<WorkoutListItem[]>([])
  const selectedWorkout = ref<WorkoutDetail | null>(null)
  const sessionVitals = ref<SessionVitals | null>(null)
  const prs = ref<PRItem[]>([])
  const crossRef = ref<CrossRefItem[]>([])
  const config = ref<ActalogConfig | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchWorkouts(start?: string, end?: string) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = {}
      if (start) params.start = start
      if (end) params.end = end
      const { data } = await api.get("/actalog/workouts", { params })
      workouts.value = data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkoutDetail(id: number) {
    const { data } = await api.get(`/actalog/workouts/${id}`)
    selectedWorkout.value = data
  }

  async function fetchSessionVitals(id: number) {
    const { data } = await api.get(`/actalog/workouts/${id}/session-vitals`)
    sessionVitals.value = data
  }

  async function fetchPRs() {
    const { data } = await api.get("/actalog/prs")
    prs.value = data
  }

  async function fetchCrossRef(start?: string, end?: string) {
    const params: Record<string, string> = {}
    if (start) params.start = start
    if (end) params.end = end
    const { data } = await api.get("/actalog/cross-reference", { params })
    crossRef.value = data
  }

  async function fetchConfig() {
    const { data } = await api.get("/admin/actalog/config")
    config.value = data
  }

  async function saveConfig(updates: Partial<ActalogConfig> & { password?: string }) {
    await api.put("/admin/actalog/config", null, { params: updates })
    await fetchConfig()
  }

  async function triggerSync() {
    const { data } = await api.post("/admin/actalog/sync")
    return data
  }

  const workoutsByDate = computed(() => {
    const map = new Map<string, WorkoutListItem[]>()
    for (const w of workouts.value) {
      if (!w.workout_date) continue
      const day = w.workout_date.slice(0, 10)
      const existing = map.get(day) ?? []
      existing.push(w)
      map.set(day, existing)
    }
    return map
  })

  return {
    workouts, selectedWorkout, sessionVitals, prs, crossRef, config,
    loading, error, workoutsByDate,
    fetchWorkouts, fetchWorkoutDetail, fetchSessionVitals,
    fetchPRs, fetchCrossRef, fetchConfig, saveConfig, triggerSync,
  }
})
```

- [ ] **Step 2: Add route to `frontend/src/router/index.ts`**

```typescript
// Add to routes array:
{ path: "/actalog", component: () => import("@/views/ActalogDashboard.vue") },
```

- [ ] **Step 3: Add sidebar nav entry to `frontend/src/App.vue`**

In the `nav` array, add after the `/correlations` entry:

```typescript
  { to: "/actalog", label: "Workouts", icon: "M3 6h18M3 12h18M3 18h18" },
```

- [ ] **Step 4: Commit store + routing**

```bash
cd frontend && git add src/stores/actalog.ts src/router/index.ts src/App.vue
git commit -m "feat: actalog Pinia store and router entry"
```

---

### Task 9: Actalog Dashboard view — 6 tabs

**Files:**
- Create: `frontend/src/views/ActalogDashboard.vue`

The file is large but structured as six tab components inlined — the tab system is native CSS, no UI framework. Each tab renders independently using data from `useActalogStore`.

- [ ] **Step 1: Create `frontend/src/views/ActalogDashboard.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted, computed, watch } from "vue"
import VChart from "vue-echarts"
import { use } from "echarts/core"
import { LineChart, BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import { useActalogStore, type WorkoutListItem } from "@/stores/actalog"
import { useDateRangeStore } from "@/stores/dateRange"
import DateRangePicker from "@/components/ui/DateRangePicker.vue"
import DualAxisChart from "@/components/charts/DualAxisChart.vue"

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent, CanvasRenderer])

const store = useActalogStore()
const dateRange = useDateRangeStore()

const activeTab = ref<"workouts" | "movements" | "wods" | "prs" | "cross" | "calendar">("workouts")

// ── Tab 1: Workouts ─────────────────────────────────────────────────
const expandedWorkout = ref<number | null>(null)

async function toggleExpand(id: number) {
  if (expandedWorkout.value === id) {
    expandedWorkout.value = null
    return
  }
  expandedWorkout.value = id
  await store.fetchWorkoutDetail(id)
}

function fmtDuration(s: number | null): string {
  if (!s) return "—"
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function typeColor(t: string | null): string {
  return { strength: "#3B82F6", metcon: "#F97316", cardio: "#22C55E", mixed: "#A855F7" }[t ?? ""] ?? "#9A9690"
}

// ── Tab 2: Movement Progress ────────────────────────────────────────
const movements = ref<{ id: number; name: string | null; movement_type: string | null }[]>([])
const selectedMovement = ref<number | null>(null)
const movementHistory = ref<any[]>([])

async function loadMovements() {
  const { data } = await import("@/api/client").then(m => m.api.get("/actalog/movements"))
  movements.value = data
}

async function selectMovement(id: number) {
  selectedMovement.value = id
  const { data } = await import("@/api/client").then(m => m.api.get(`/actalog/movements/${id}/history`))
  movementHistory.value = data
}

const movementChartOption = computed(() => ({
  tooltip: { trigger: "axis" },
  xAxis: { type: "time" },
  yAxis: { type: "value", name: "kg" },
  series: [{
    type: "line",
    data: movementHistory.value
      .filter(r => r.weight_kg != null)
      .map(r => [r.workout_date, r.weight_kg]),
    smooth: true,
    symbol: "none",
    lineStyle: { color: "#3B82F6", width: 2 },
    markPoint: {
      data: movementHistory.value
        .filter(r => r.is_pr)
        .map(r => ({ xAxis: r.workout_date, yAxis: r.weight_kg, symbol: "circle", symbolSize: 8, itemStyle: { color: "#F97316" } })),
    },
  }],
}))

// ── Tab 3: WOD Progress ─────────────────────────────────────────────
const wods = ref<{ id: number; name: string | null; regime: string | null; score_type: string | null }[]>([])
const selectedWod = ref<number | null>(null)
const wodHistory = ref<any[]>([])
const selectedWodMeta = computed(() => wods.value.find(w => w.id === selectedWod.value) ?? null)

async function loadWods() {
  const { data } = await import("@/api/client").then(m => m.api.get("/actalog/wods"))
  wods.value = data
}

async function selectWod(id: number) {
  selectedWod.value = id
  const { data } = await import("@/api/client").then(m => m.api.get(`/actalog/wods/${id}/history`))
  wodHistory.value = data
}

const wodChartOption = computed(() => {
  const meta = selectedWodMeta.value
  if (!meta || !wodHistory.value.length) return null
  const isTime = meta.score_type === "Time"
  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: any[]) => {
        const p = params[0]
        if (!p) return ""
        const val = isTime
          ? `${Math.floor(p.value[1] / 60)}:${String(p.value[1] % 60).padStart(2, "0")}`
          : p.value[1]
        return `${new Date(p.value[0]).toLocaleDateString()}: ${val}`
      },
    },
    xAxis: { type: "time" },
    yAxis: {
      type: "value",
      name: isTime ? "seconds (lower=better)" : meta.score_type ?? "",
      inverse: isTime,
    },
    series: [{
      type: "line",
      // For Time WODs, use time_s (seconds). For Rounds+Reps, use rounds. For Max Weight, use weight_kg.
      data: wodHistory.value
        .filter(r => isTime ? r.time_s != null : (r.rounds != null || r.weight_kg != null))
        .map(r => {
          const y = isTime ? r.time_s : (meta?.score_type === "Max Weight" ? r.weight_kg : r.rounds)
          return [r.workout_date, y]
        }),
      smooth: true,
      symbol: "none",
      lineStyle: { color: "#F97316", width: 2 },
      markPoint: {
        data: wodHistory.value
          .filter(r => r.is_pr)
          .map(r => {
            const y = isTime ? r.time_s : (meta?.score_type === "Max Weight" ? r.weight_kg : r.rounds)
            return { xAxis: r.workout_date, yAxis: y, symbol: "circle", symbolSize: 8, itemStyle: { color: "#EF4444" } }
          }),
      },
    }],
  }
})

// ── Tab 4: PRs ──────────────────────────────────────────────────────

// ── Tab 5: Cross-reference ──────────────────────────────────────────
const crossSignal = ref<"body_battery_max" | "hr_resting" | "sleep_score" | "stress_avg">("body_battery_max")

const crossChartLeft = computed(() => ({
  name: "Volume (kg)",
  data: store.crossRef.map(r => [r.workout_date ?? "", r.total_volume_kg ?? null]) as [string, number | null][],
  color: "#3B82F6",
  unit: "kg",
}))

const crossChartRight = computed(() => {
  const labels: Record<string, string> = {
    body_battery_max: "Body Battery", hr_resting: "RHR (bpm)",
    sleep_score: "Sleep Score", stress_avg: "Stress",
  }
  const colors: Record<string, string> = {
    body_battery_max: "#22C55E", hr_resting: "#EF4444", sleep_score: "#8B5CF6", stress_avg: "#F97316",
  }
  return {
    name: labels[crossSignal.value],
    data: store.crossRef.map(r => [r.workout_date ?? "", (r as any)[crossSignal.value] ?? null]) as [string, number | null][],
    color: colors[crossSignal.value],
    unit: "",
  }
})

// ── Tab 6: Calendar ─────────────────────────────────────────────────
const calYear = ref(new Date().getFullYear())
const calMonth = ref(new Date().getMonth()) // 0-indexed
const selectedDay = ref<string | null>(null)

function calDays(): Array<{ date: string; day: number; workouts: WorkoutListItem[] } | null> {
  const first = new Date(calYear.value, calMonth.value, 1)
  const totalDays = new Date(calYear.value, calMonth.value + 1, 0).getDate()
  const startPad = first.getDay() // Sunday = 0
  const cells: Array<{ date: string; day: number; workouts: WorkoutListItem[] } | null> = []
  for (let i = 0; i < startPad; i++) cells.push(null)
  for (let d = 1; d <= totalDays; d++) {
    const dateStr = `${calYear.value}-${String(calMonth.value + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`
    cells.push({ date: dateStr, day: d, workouts: store.workoutsByDate.get(dateStr) ?? [] })
  }
  return cells
}

function prevMonth() {
  if (calMonth.value === 0) { calYear.value--; calMonth.value = 11 } else calMonth.value--
}
function nextMonth() {
  if (calMonth.value === 11) { calYear.value++; calMonth.value = 0 } else calMonth.value++
}

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"]

async function selectDay(dateStr: string) {
  selectedDay.value = dateStr
  const dayWorkouts = store.workoutsByDate.get(dateStr)
  if (dayWorkouts?.length) {
    await store.fetchSessionVitals(dayWorkouts[0].id)
  }
}

const hrChartOption = computed(() => {
  const vitals = store.sessionVitals
  if (!vitals?.has_vitals || !vitals.hr_series.length) return null
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "time", axisLabel: { color: "#9A9690", fontSize: 10 } },
    yAxis: { type: "value", name: "bpm", axisLabel: { color: "#9A9690", fontSize: 10 } },
    series: [{
      type: "line",
      data: vitals.hr_series.map(p => [p.ts, p.hr]),
      smooth: false,
      symbol: "none",
      lineStyle: { color: "#EF4444", width: 1.5 },
      areaStyle: { color: "rgba(239,68,68,0.08)" },
    }],
  }
})

// ── Lifecycle ────────────────────────────────────────────────────────
onMounted(async () => {
  await store.fetchWorkouts(dateRange.start, dateRange.end)
  await store.fetchPRs()
  await store.fetchCrossRef(dateRange.start, dateRange.end)
  await loadMovements()
  await loadWods()
})

watch([() => dateRange.start, () => dateRange.end], async () => {
  await store.fetchWorkouts(dateRange.start, dateRange.end)
  await store.fetchCrossRef(dateRange.start, dateRange.end)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Actalog</h1>
      <DateRangePicker />
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar">
      <button v-for="tab in ['workouts','movements','wods','prs','cross','calendar']" :key="tab"
        :class="['tab-btn', { active: activeTab === tab }]"
        @click="activeTab = tab as any">
        {{ { workouts: 'Workouts', movements: 'Movements', wods: 'WODs', prs: 'Personal Records', cross: 'Cross-Reference', calendar: 'Calendar' }[tab] }}
      </button>
    </div>

    <!-- ── Tab 1: Workouts ──────────────────────────────────────── -->
    <div v-if="activeTab === 'workouts'" class="tab-content">
      <div v-if="store.loading" class="muted">Loading…</div>
      <div v-else-if="!store.workouts.length" class="muted">No workouts found. Run a sync from Admin → Actalog.</div>
      <table v-else class="data-table">
        <thead><tr><th>Date</th><th>Name</th><th>Type</th><th>Duration</th><th>Actions</th></tr></thead>
        <tbody>
          <template v-for="w in store.workouts" :key="w.id">
            <tr class="workout-row">
              <td>{{ w.workout_date?.slice(0, 10) ?? "—" }}</td>
              <td>{{ w.workout_name ?? "—" }}</td>
              <td><span class="type-badge" :style="{ background: typeColor(w.workout_type) + '20', color: typeColor(w.workout_type) }">{{ w.workout_type ?? "—" }}</span></td>
              <td>{{ fmtDuration(w.total_time_s) }}</td>
              <td><button class="link-btn" @click="toggleExpand(w.id)">{{ expandedWorkout === w.id ? 'Collapse' : 'Expand' }}</button></td>
            </tr>
            <tr v-if="expandedWorkout === w.id && store.selectedWorkout?.id === w.id" class="expand-row">
              <td colspan="5">
                <div class="expand-body">
                  <div v-if="store.selectedWorkout.movements.length">
                    <p class="section-label">Movements</p>
                    <table class="inner-table">
                      <thead><tr><th>#</th><th>Movement</th><th>Sets</th><th>Reps</th><th>Weight</th><th>RPE</th><th>PR</th></tr></thead>
                      <tbody>
                        <tr v-for="m in store.selectedWorkout.movements" :key="m.id">
                          <td>{{ m.order_index ?? "—" }}</td>
                          <td>{{ m.movement_id }}</td>
                          <td>{{ m.sets ?? "—" }}</td>
                          <td>{{ m.reps ?? "—" }}</td>
                          <td>{{ m.weight_kg != null ? m.weight_kg + ' kg' : '—' }}</td>
                          <td>{{ m.rpe ?? "—" }}</td>
                          <td>{{ m.is_pr ? '★' : '' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="store.selectedWorkout.wods.length" style="margin-top:12px">
                    <p class="section-label">WODs</p>
                    <table class="inner-table">
                      <thead><tr><th>Score</th><th>RPE</th><th>PR</th></tr></thead>
                      <tbody>
                        <tr v-for="w in store.selectedWorkout.wods" :key="w.id">
                          <td>{{ w.score_value ?? "—" }}</td>
                          <td>{{ w.rpe ?? "—" }}</td>
                          <td>{{ w.is_pr ? '★' : '' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p v-if="store.selectedWorkout.notes" class="notes-text">{{ store.selectedWorkout.notes }}</p>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- ── Tab 2: Movements ─────────────────────────────────────── -->
    <div v-if="activeTab === 'movements'" class="tab-content">
      <div class="split-layout">
        <div class="split-sidebar">
          <p class="section-label">Select Movement</p>
          <div class="movement-list">
            <button v-for="m in movements" :key="m.id"
              :class="['movement-item', { active: selectedMovement === m.id }]"
              @click="selectMovement(m.id)">
              {{ m.name }}
            </button>
          </div>
        </div>
        <div class="split-main">
          <div v-if="!selectedMovement" class="muted">Select a movement to see its history.</div>
          <template v-else>
            <v-chart v-if="movementHistory.some(r => r.weight_kg)" :option="movementChartOption" autoresize style="height:240px" />
            <table v-if="movementHistory.length" class="data-table" style="margin-top:16px">
              <thead><tr><th>Date</th><th>Sets</th><th>Reps</th><th>Weight</th><th>RPE</th><th>PR</th></tr></thead>
              <tbody>
                <tr v-for="r in movementHistory" :key="r.id">
                  <td>{{ r.workout_date?.slice(0,10) ?? "—" }}</td>
                  <td>{{ r.sets ?? "—" }}</td>
                  <td>{{ r.reps ?? "—" }}</td>
                  <td>{{ r.weight_kg != null ? r.weight_kg + ' kg' : '—' }}</td>
                  <td>{{ r.rpe ?? "—" }}</td>
                  <td>{{ r.is_pr ? '★' : '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </div>
    </div>

    <!-- ── Tab 3: WOD Progress ────────────────────────────────── -->
    <div v-if="activeTab === 'wods'" class="tab-content">
      <div class="split-layout">
        <div class="split-sidebar">
          <p class="section-label">Select WOD</p>
          <div class="movement-list">
            <button v-for="w in wods" :key="w.id"
              :class="['movement-item', { active: selectedWod === w.id }]"
              @click="selectWod(w.id)">
              {{ w.name }}<span v-if="w.regime" class="wod-regime"> · {{ w.regime }}</span>
            </button>
          </div>
        </div>
        <div class="split-main">
          <div v-if="!selectedWod" class="muted">Select a WOD to see its performance history.</div>
          <template v-else>
            <div class="wod-meta" v-if="selectedWodMeta">
              Score type: <strong>{{ selectedWodMeta.score_type ?? "—" }}</strong>
              <span v-if="selectedWodMeta.score_type === 'Time'" class="muted"> (lower is better)</span>
              <span v-else class="muted"> (higher is better)</span>
            </div>
            <v-chart v-if="wodChartOption" :option="wodChartOption" autoresize style="height:240px;margin-top:12px" />
            <table v-if="wodHistory.length" class="data-table" style="margin-top:16px">
              <thead><tr><th>Date</th><th>Score</th><th>RPE</th><th>PR</th></tr></thead>
              <tbody>
                <tr v-for="r in wodHistory" :key="r.id">
                  <td>{{ r.workout_date?.slice(0,10) ?? "—" }}</td>
                  <td>{{ r.score_value ?? "—" }}</td>
                  <td>{{ r.rpe ?? "—" }}</td>
                  <td>{{ r.is_pr ? '★' : '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </div>
    </div>

    <!-- ── Tab 4: PRs ──────────────────────────────────────────── -->
    <div v-if="activeTab === 'prs'" class="tab-content">
      <div v-if="!store.prs.length" class="muted">No PRs yet. Sync data first.</div>
      <table v-else class="data-table">
        <thead><tr><th>Movement</th><th>Type</th><th>Best Weight</th><th>Best Reps</th><th>Best Time</th><th>Date</th></tr></thead>
        <tbody>
          <tr v-for="pr in store.prs" :key="pr.movement_id">
            <td>{{ pr.movement_name ?? "—" }}</td>
            <td>{{ pr.movement_type ?? "—" }}</td>
            <td>{{ pr.max_weight_kg != null ? pr.max_weight_kg + ' kg' : '—' }}</td>
            <td>{{ pr.max_reps ?? "—" }}</td>
            <td>{{ pr.best_time_s != null ? Math.floor(pr.best_time_s/60) + ':' + String(pr.best_time_s%60).padStart(2,'0') : '—' }}</td>
            <td>{{ pr.workout_date?.slice(0,10) ?? "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Tab 5: Cross-Reference ──────────────────────────────── -->
    <div v-if="activeTab === 'cross'" class="tab-content">
      <div class="toolbar">
        <label>Garmin signal:</label>
        <select v-model="crossSignal" class="select-sm">
          <option value="body_battery_max">Body Battery</option>
          <option value="hr_resting">Resting HR</option>
          <option value="sleep_score">Sleep Score</option>
          <option value="stress_avg">Stress</option>
        </select>
      </div>
      <div v-if="!store.crossRef.length" class="muted">No cross-reference data. Sync Actalog and Garmin data first.</div>
      <DualAxisChart v-else :left="crossChartLeft" :right="crossChartRight" height="300px" />
    </div>

    <!-- ── Tab 6: Calendar ─────────────────────────────────────── -->
    <div v-if="activeTab === 'calendar'" class="tab-content">
      <div class="cal-nav">
        <button class="link-btn" @click="prevMonth">◀</button>
        <span class="cal-title">{{ MONTH_NAMES[calMonth] }} {{ calYear }}</span>
        <button class="link-btn" @click="nextMonth">▶</button>
      </div>
      <div class="cal-grid">
        <div v-for="d in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']" :key="d" class="cal-header">{{ d }}</div>
        <div
          v-for="(cell, i) in calDays()"
          :key="i"
          :class="['cal-cell', { empty: !cell, active: cell?.date === selectedDay, 'has-workout': cell && cell.workouts.length > 0 }]"
          @click="cell && cell.workouts.length && selectDay(cell.date)"
        >
          <template v-if="cell">
            <span class="cal-day-num">{{ cell.day }}</span>
            <div class="cal-dots">
              <span v-for="w in cell.workouts.slice(0,3)" :key="w.id"
                class="cal-dot" :style="{ background: typeColor(w.workout_type) }" />
            </div>
          </template>
        </div>
      </div>

      <!-- Session Vitals Panel -->
      <div v-if="selectedDay && store.sessionVitals" class="vitals-panel">
        <h3>{{ selectedDay }} — {{ store.sessionVitals.workout.workout_name }}</h3>
        <div class="vitals-meta">
          <span>Type: {{ store.sessionVitals.workout.workout_type ?? "—" }}</span>
          <span>Duration: {{ fmtDuration(store.sessionVitals.workout.total_time_s) }}</span>
        </div>

        <!-- Movements -->
        <div v-if="store.sessionVitals.workout.movements.length">
          <p class="section-label">Movements</p>
          <table class="inner-table">
            <thead><tr><th>Sets</th><th>Reps</th><th>Weight</th><th>RPE</th><th>PR</th></tr></thead>
            <tbody>
              <tr v-for="m in store.sessionVitals.workout.movements" :key="m.id">
                <td>{{ m.sets ?? "—" }}</td><td>{{ m.reps ?? "—" }}</td>
                <td>{{ m.weight_kg != null ? m.weight_kg + ' kg' : '—' }}</td>
                <td>{{ m.rpe ?? "—" }}</td><td>{{ m.is_pr ? '★' : '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- HR chart (only when has_vitals) -->
        <template v-if="store.sessionVitals.has_vitals">
          <p class="section-label" style="margin-top:16px">Heart Rate During Workout</p>
          <v-chart v-if="hrChartOption" :option="hrChartOption" autoresize style="height:200px" />
        </template>
        <p v-else class="muted vitals-none">No duration recorded — heart rate window unavailable.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { font-size: 1.4rem; font-weight: 700; color: var(--text); }

.tab-bar { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
.tab-btn { padding: 8px 14px; font-size: 0.82rem; font-weight: 500; color: var(--muted); background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; transition: color 0.12s, border-color 0.12s; }
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

.muted { color: var(--muted); font-size: 0.85rem; padding: 24px 0; }
.section-label { font-size: 0.75rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }

.data-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.data-table th { text-align: left; padding: 6px 10px; color: var(--muted); font-weight: 600; font-size: 0.75rem; border-bottom: 1px solid var(--border); }
.data-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text); }
.workout-row:hover { background: var(--bg); }

.type-badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 0.75rem; font-weight: 600; }

.expand-row td { padding: 0; }
.expand-body { padding: 12px 16px; background: var(--bg); border-bottom: 1px solid var(--border); }
.inner-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.inner-table th, .inner-table td { padding: 4px 8px; border-bottom: 1px solid var(--border); }

.notes-text { font-size: 0.82rem; color: var(--muted); margin-top: 8px; font-style: italic; }
.link-btn { background: none; border: none; color: var(--accent); font-size: 0.82rem; cursor: pointer; padding: 2px 4px; }

.split-layout { display: flex; gap: 20px; }
.split-sidebar { width: 200px; flex-shrink: 0; }
.split-main { flex: 1; min-width: 0; }
.movement-list { display: flex; flex-direction: column; gap: 2px; max-height: 400px; overflow-y: auto; }
.movement-item { text-align: left; padding: 6px 10px; border-radius: 6px; font-size: 0.82rem; color: var(--text); background: none; border: none; cursor: pointer; }
.movement-item:hover { background: var(--bg); }
.movement-item.active { background: var(--accent-light); color: var(--accent); font-weight: 600; }

.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; font-size: 0.83rem; color: var(--muted); }
.select-sm { padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); font-size: 0.82rem; color: var(--text); background: var(--surface); }

.cal-nav { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.cal-title { font-size: 1rem; font-weight: 600; color: var(--text); }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-header { font-size: 0.72rem; font-weight: 600; color: var(--muted); text-align: center; padding: 4px; }
.cal-cell { min-height: 60px; border-radius: 8px; border: 1px solid var(--border); padding: 6px; background: var(--surface); }
.cal-cell.empty { border: none; background: none; }
.cal-cell.has-workout { cursor: pointer; }
.cal-cell.has-workout:hover { background: var(--bg); }
.cal-cell.active { border-color: var(--accent); background: var(--accent-light); }
.cal-day-num { font-size: 0.8rem; color: var(--muted); }
.cal-dots { display: flex; gap: 3px; margin-top: 4px; }
.cal-dot { width: 7px; height: 7px; border-radius: 50%; }

.vitals-panel { margin-top: 24px; padding: 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }
.vitals-panel h3 { font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 8px; }
.vitals-meta { display: flex; gap: 20px; font-size: 0.83rem; color: var(--muted); margin-bottom: 12px; }
.vitals-none { font-style: italic; margin-top: 12px; }
</style>
```

- [ ] **Step 2: Verify the app compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/views/ActalogDashboard.vue
git commit -m "feat: actalog dashboard view (6 tabs)"
```

---

### Task 10: Admin UI — Actalog config section

**Files:**
- Modify: `frontend/src/views/Admin.vue`

- [ ] **Step 1: Read `frontend/src/views/Admin.vue` first**

```bash
cat frontend/src/views/Admin.vue
```

- [ ] **Step 2: Add Actalog section at end of the admin page template**

Add a new section to the Admin view. Locate the last `</section>` tag and insert after it:

```vue
<!-- Actalog Integration -->
<section class="admin-section">
  <h2>Actalog Integration</h2>
  <div v-if="actalogLoading" class="muted">Loading config…</div>
  <template v-else>
    <div class="field-row">
      <label>Base URL</label>
      <input v-model="actalogForm.url" class="input-sm" placeholder="https://al.example.com" />
    </div>
    <div class="field-row">
      <label>Email</label>
      <input v-model="actalogForm.email" class="input-sm" type="email" />
    </div>
    <div class="field-row">
      <label>Password</label>
      <input v-model="actalogForm.password" class="input-sm" :type="showPw ? 'text' : 'password'" />
      <button class="link-btn" @click="showPw = !showPw">{{ showPw ? 'Hide' : 'Show' }}</button>
    </div>
    <div class="field-row">
      <label>Weight Unit</label>
      <select v-model="actalogForm.weight_unit" class="select-sm">
        <option value="kg">kg</option>
        <option value="lbs">lbs</option>
      </select>
    </div>
    <div class="field-row">
      <label>Sync Interval (hours)</label>
      <input v-model.number="actalogForm.sync_interval_hours" class="input-sm" type="number" min="1" max="168" />
    </div>
    <div class="field-row">
      <label>Sync Enabled</label>
      <input v-model="actalogForm.sync_enabled" type="checkbox" />
    </div>
    <div class="action-row">
      <button class="btn-primary" @click="saveActalog">Save</button>
      <button class="btn-secondary" @click="testActalogConnection">Test Connection</button>
      <button class="btn-secondary" @click="syncActalog" :disabled="actalogSyncing">
        {{ actalogSyncing ? 'Syncing…' : 'Sync Now' }}
      </button>
    </div>
    <div v-if="actalogMsg" :class="['status-msg', actalogMsgOk ? 'ok' : 'err']">{{ actalogMsg }}</div>
    <div v-if="actalogConfig?.last_sync" class="muted" style="font-size:0.78rem;margin-top:4px">
      Last sync: {{ actalogConfig.last_sync?.slice(0, 19).replace('T', ' ') }}
    </div>
  </template>
</section>
```

- [ ] **Step 3: Add reactive data and methods to Admin.vue's `<script setup>`**

Insert the following block **after** the existing `import { api } from "@/api/client"` line and **after** all existing `const` declarations. The existing `onMounted` on line 229 becomes:

```typescript
// ADD after existing imports at top of <script setup>:
import { computed } from "vue"
import { useActalogStore } from "@/stores/actalog"

// ADD after existing const declarations (after `const historyBox = ref...` block):
const actalogStore = useActalogStore()
const actalogLoading = ref(true)
const actalogConfig = computed(() => actalogStore.config)
const actalogForm = ref({
  url: "", email: "", password: "", weight_unit: "kg",
  sync_interval_hours: 24, sync_enabled: false,
})
const showPw = ref(false)
const actalogSyncing = ref(false)
const actalogMsg = ref("")
const actalogMsgOk = ref(true)

async function _loadActalogConfig() {
  await actalogStore.fetchConfig()
  if (actalogStore.config) {
    actalogForm.value.url = actalogStore.config.url ?? ""
    actalogForm.value.email = actalogStore.config.email ?? ""
    actalogForm.value.weight_unit = actalogStore.config.weight_unit ?? "kg"
    actalogForm.value.sync_interval_hours = actalogStore.config.sync_interval_hours ?? 24
    actalogForm.value.sync_enabled = actalogStore.config.sync_enabled
  }
  actalogLoading.value = false
}

async function saveActalog() {
  await actalogStore.saveConfig(actalogForm.value)
  actalogMsg.value = "Saved."
  actalogMsgOk.value = true
}

async function testActalogConnection() {
  actalogMsg.value = ""
  try {
    await api.post("/admin/actalog/test-connection", null, {
      params: {
        url: actalogForm.value.url,
        email: actalogForm.value.email,
        password: actalogForm.value.password,
      },
    })
    actalogMsg.value = "Connection successful."
    actalogMsgOk.value = true
  } catch (e: any) {
    actalogMsg.value = `Connection failed: ${e.response?.data?.detail ?? e.message}`
    actalogMsgOk.value = false
  }
}

async function syncActalog() {
  actalogSyncing.value = true
  actalogMsg.value = ""
  try {
    const counts = await actalogStore.triggerSync()
    actalogMsg.value = `Sync complete: ${counts.workouts} workouts, ${counts.prs} PRs.`
    actalogMsgOk.value = true
    await actalogStore.fetchConfig()
  } catch (e: any) {
    actalogMsg.value = `Sync failed: ${e.message}`
    actalogMsgOk.value = false
  } finally {
    actalogSyncing.value = false
  }
}
```

**REPLACE** the existing `onMounted` block (currently lines 229–233 of Admin.vue):

```typescript
// REPLACE existing onMounted:
onMounted(() => {
  connectSSE()
  api.get("/admin/schedules").then((r) => { schedules.value = r.data.schedules ?? []; schedulesLoading.value = false })
  api.get("/admin/config").then((r) => { config.value = r.data.config ?? []; configLoading.value = false })
  _loadActalogConfig()
})
```

- [ ] **Step 4: Verify frontend build**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/views/Admin.vue
git commit -m "feat: actalog admin config section"
```

---

## Chunk 5 End — Final Verification

- [ ] **Run full backend test suite**

```bash
cd backend && uv run pytest -q
```

Expected: All tests pass.

- [ ] **Run frontend build**

```bash
cd frontend && npm run build
```

Expected: No errors.

- [ ] **Smoke test against live Actalog**

```bash
# Start backend in dev
cd backend && uv run uvicorn garminview.api.main:app --reload

# Trigger manual sync (replace with real creds first via Admin UI)
curl -X POST http://localhost:8000/admin/actalog/sync
```

Expected: Returns `{"workouts": N, "prs": M, "errors": 0}`

- [ ] **Final commit — version bump**

```bash
cd backend
# Bump version in pyproject.toml from current to next minor (e.g., 0.3.0 → 0.4.0)
git add pyproject.toml
git commit -m "chore: bump version for actalog integration"
```
