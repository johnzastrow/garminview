# Data Management Tasks Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "System Activity" panel to the top of Daily Overview showing recent sync history and pending human action items (profile setup, anomaly review, Actalog note review) in a single interleaved list.

**Architecture:** A new `GET /admin/tasks` endpoint aggregates sync_log entries, profile completeness, data quality flags, and Actalog pending parse count into one sorted response. A new `TasksPanel.vue` component fetches this endpoint on mount and renders the list at the top of `DailyOverview.vue`.

**Tech Stack:** FastAPI + Pydantic v2 (backend), Vue 3 Composition API + TypeScript + axios (frontend), SQLAlchemy 2.x (ORM), dayjs (date formatting), pytest + TestClient (tests)

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `backend/garminview/api/schemas/admin.py` | Create | `TaskItem` Pydantic response schema |
| `backend/garminview/api/routes/admin.py` | Modify | Add `GET /admin/tasks` endpoint |
| `backend/tests/api/test_admin_tasks.py` | Create | 7 API tests for the new endpoint |
| `frontend/src/components/ui/TasksPanel.vue` | Create | Renders interleaved task list |
| `frontend/src/views/DailyOverview.vue` | Modify | Mount `<TasksPanel />` after page header |

---

## Task 1: TaskItem Pydantic Schema

**Files:**
- Create: `backend/garminview/api/schemas/admin.py`

- [ ] **Step 1: Create the schema file**

```python
# backend/garminview/api/schemas/admin.py
from pydantic import BaseModel
from datetime import datetime


class TaskItem(BaseModel):
    type: str               # "sync" | "action"
    action_key: str | None = None   # "profile_setup" | "anomalies" | "actalog_review"
    title: str
    detail: str | None = None
    link: str | None = None         # frontend route, action items only
    count: int | None = None        # for action items with a count
    timestamp: datetime | None = None   # sync start time; null for action items
    duration_s: float | None = None     # finished_at - started_at
    records: int | None = None          # records_upserted from sync_log
    status: str | None = None           # "success" | "error" | "running"
```

- [ ] **Step 2: Verify file is importable**

```bash
cd backend
uv run python -c "from garminview.api.schemas.admin import TaskItem; print(TaskItem.model_fields.keys())"
```

Expected output: `dict_keys(['type', 'action_key', 'title', 'detail', 'link', 'count', 'timestamp', 'duration_s', 'records', 'status'])`

- [ ] **Step 3: Commit**

```bash
git add backend/garminview/api/schemas/admin.py
git commit -m "feat: add TaskItem schema for admin tasks endpoint"
```

---

## Task 2: GET /admin/tasks Endpoint

**Files:**
- Modify: `backend/garminview/api/routes/admin.py`

The existing `admin.py` already imports `UserProfile`, `DataQualityFlag`, `SyncLog`, and `AppConfig` at the top. Add the `TaskItem` import and the new endpoint.

- [ ] **Step 1: Add import at the top of `backend/garminview/api/routes/admin.py`**

Add this line alongside the existing schema imports (after the existing `from garminview.models.sync import SyncLog, SchemaVersion` line):

```python
from garminview.api.schemas.admin import TaskItem
```

- [ ] **Step 2: Add the source label mapping and endpoint**

Append to the end of `backend/garminview/api/routes/admin.py`:

```python
_SOURCE_LABELS: dict[str, str] = {
    "garmin_daily": "Garmin daily sync",
    "garmin_monitoring": "Garmin monitoring sync",
    "actalog": "Actalog sync",
    "hr_zones": "HR zones recompute",
}


@router.get("/tasks", response_model=list[TaskItem])
def get_tasks(
    session: Annotated[Session, Depends(get_db)],
    limit: int = 10,
):
    items: list[TaskItem] = []

    # --- Action items ---

    # Profile setup: alert if resting_hr or max_hr_override is missing
    p = session.query(UserProfile).first()
    if not p or p.resting_hr is None or p.max_hr_override is None:
        items.append(TaskItem(
            type="action",
            action_key="profile_setup",
            title="Set resting HR and max HR",
            detail="Required for heart rate zone analysis",
            link="/admin",
        ))

    # Anomalies: count system-generated flags not yet user-excluded
    anomaly_count = session.query(DataQualityFlag).filter(
        DataQualityFlag.flag_type.in_(["missing", "implausible", "duplicate", "gap"]),
        DataQualityFlag.excluded == False,  # noqa: E712
    ).count()
    if anomaly_count > 0:
        items.append(TaskItem(
            type="action",
            action_key="anomalies",
            title=f"{anomaly_count} unreviewed data anomalies",
            link="/admin",
            count=anomaly_count,
        ))

    # Actalog review: only shown when actalog sync is enabled
    actalog_row = session.get(AppConfig, "actalog_sync_enabled")
    if actalog_row and actalog_row.value and actalog_row.value.lower() in ("1", "true", "yes"):
        from garminview.models.actalog import ActalogNoteParse
        pending = session.query(ActalogNoteParse).filter(
            ActalogNoteParse.parse_status == "pending"
        ).count()
        if pending > 0:
            items.append(TaskItem(
                type="action",
                action_key="actalog_review",
                title=f"{pending} workout notes awaiting review",
                link="/actalog",
                count=pending,
            ))

    # --- Sync history ---
    sync_rows = (
        session.query(SyncLog)
        .order_by(SyncLog.started_at.desc())
        .limit(limit)
        .all()
    )
    for row in sync_rows:
        duration_s = None
        if row.started_at and row.finished_at:
            duration_s = (row.finished_at - row.started_at).total_seconds()
        items.append(TaskItem(
            type="sync",
            title=_SOURCE_LABELS.get(row.source, row.source),
            detail=row.error_message[:80] if row.error_message else row.source,
            timestamp=row.started_at,
            duration_s=duration_s,
            records=row.records_upserted,
            status=row.status,
        ))

    return items
```

- [ ] **Step 3: Smoke test the endpoint manually**

```bash
cd backend
uv run uvicorn garminview.api.main:app --reload &
sleep 2
curl -s http://localhost:8000/admin/tasks | python3 -m json.tool
```

Expected: JSON array (may be empty or have profile_setup action if profile not set). Kill the server after (`fg` then Ctrl-C).

- [ ] **Step 4: Commit**

```bash
git add backend/garminview/api/routes/admin.py
git commit -m "feat: add GET /admin/tasks endpoint aggregating sync history and action items"
```

---

## Task 3: API Tests

**Files:**
- Create: `backend/tests/api/test_admin_tasks.py`

Follow the same pattern as `backend/tests/api/test_hr_zones_api.py`: in-memory SQLite, TestClient, per-test seeding via a factory fixture.

- [ ] **Step 1: Write all tests**

```python
# backend/tests/api/test_admin_tasks.py
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import garminview.models  # noqa: registers all models with Base.metadata
from garminview.core.database import Base
from garminview.api.main import create_app
from garminview.api import deps
from garminview.models.sync import SyncLog
from garminview.models.config import UserProfile, AppConfig
from garminview.models.assessments import DataQualityFlag
from garminview.models.actalog import ActalogNoteParse, ActalogWorkout


@pytest.fixture()
def make_client():
    """Factory: creates a TestClient backed by a fresh in-memory SQLite DB.
    Pass a seed function to populate the DB before the client is returned."""
    def _factory(seed=None):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        app = create_app(engine=engine)

        def override_db():
            with Session() as s:
                yield s

        app.dependency_overrides[deps.get_db] = override_db

        if seed:
            with Session() as s:
                seed(s)
                s.commit()

        return TestClient(app)
    return _factory


def _sync_row(**kwargs) -> SyncLog:
    """Build a SyncLog with sensible defaults, overridden by kwargs."""
    defaults = dict(
        started_at=datetime(2026, 3, 12, 10, 0, 0),
        finished_at=datetime(2026, 3, 12, 10, 0, 10),
        source="garmin_daily",
        mode="full",
        records_upserted=100,
        status="success",
    )
    defaults.update(kwargs)
    return SyncLog(**defaults)


def test_profile_missing_shows_profile_action(make_client):
    # No user_profile row → profile_setup action item must appear
    client = make_client()
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    action_keys = [i["action_key"] for i in resp.json() if i["type"] == "action"]
    assert "profile_setup" in action_keys


def test_complete_profile_no_profile_action(make_client):
    # Profile with both fields set → no profile_setup action item
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    action_keys = [i["action_key"] for i in resp.json() if i["type"] == "action"]
    assert "profile_setup" not in action_keys


def test_sync_history_appears(make_client):
    # Seeded sync_log row appears as a sync item with correct fields
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(_sync_row(source="garmin_daily", records_upserted=147))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    syncs = [i for i in resp.json() if i["type"] == "sync"]
    assert len(syncs) == 1
    assert syncs[0]["title"] == "Garmin daily sync"
    assert syncs[0]["records"] == 147
    assert syncs[0]["status"] == "success"


def test_sync_duration_computed(make_client):
    # duration_s = finished_at - started_at in seconds
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(_sync_row(
            started_at=datetime(2026, 3, 12, 10, 0, 0),
            finished_at=datetime(2026, 3, 12, 10, 0, 10),
        ))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    syncs = [i for i in resp.json() if i["type"] == "sync"]
    assert syncs[0]["duration_s"] == pytest.approx(10.0)


def test_running_sync_has_null_duration(make_client):
    # finished_at = None → duration_s = None, status = "running"
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(_sync_row(finished_at=None, status="running", records_upserted=None))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    syncs = [i for i in resp.json() if i["type"] == "sync"]
    assert syncs[0]["duration_s"] is None
    assert syncs[0]["status"] == "running"


def test_actalog_review_when_pending_and_enabled(make_client):
    # Actalog enabled + 1 pending parse → actalog_review action with count=1
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(AppConfig(key="actalog_sync_enabled", value="true", category="actalog", data_type="string"))
        workout = ActalogWorkout(workout_name="Test WOD")
        s.add(workout)
        s.flush()
        s.add(ActalogNoteParse(workout_id=workout.id, parse_status="pending", raw_notes="squat 5x5"))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    action_keys = [i["action_key"] for i in resp.json() if i["type"] == "action"]
    assert "actalog_review" in action_keys
    review = next(i for i in resp.json() if i.get("action_key") == "actalog_review")
    assert review["count"] == 1
    assert review["link"] == "/actalog"


def test_no_actalog_review_when_disabled(make_client):
    # Actalog disabled → actalog_review never shown, even if parses are pending
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(AppConfig(key="actalog_sync_enabled", value="false", category="actalog", data_type="string"))
        workout = ActalogWorkout(workout_name="Test WOD")
        s.add(workout)
        s.flush()
        s.add(ActalogNoteParse(workout_id=workout.id, parse_status="pending", raw_notes="squat 5x5"))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    action_keys = [i["action_key"] for i in resp.json() if i["type"] == "action"]
    assert "actalog_review" not in action_keys
```

- [ ] **Step 2: Run the tests to verify they fail (endpoint not built yet — skip if Task 2 already done)**

```bash
cd backend
uv run pytest tests/api/test_admin_tasks.py -v
```

Expected: all 7 tests pass if Task 2 is already complete. If running before Task 2, expect failures on import or 404.

- [ ] **Step 3: Run full test suite to check for regressions**

```bash
cd backend
uv run pytest -q
```

Expected: all tests pass, no regressions.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/api/test_admin_tasks.py
git commit -m "test: add API tests for GET /admin/tasks endpoint"
```

---

## Task 4: TasksPanel.vue Component

**Files:**
- Create: `frontend/src/components/ui/TasksPanel.vue`

Uses `api` from `@/api/client` (axios instance) directly — not `useMetricData`, which is tied to date-range params this endpoint doesn't need. Fetches on `onMounted`. Silently suppresses fetch errors since the panel is supplementary.

- [ ] **Step 1: Create the component**

```vue
<!-- frontend/src/components/ui/TasksPanel.vue -->
<template>
  <div v-if="items.length" class="tasks-panel">
    <h2 class="tasks-title">System Activity</h2>
    <div class="tasks-list">
      <component
        :is="item.link ? 'router-link' : 'div'"
        v-for="item in items"
        :key="item.type + (item.action_key ?? item.timestamp ?? '')"
        :to="item.link ?? undefined"
        :class="['task-row', item.type === 'action' ? 'task-action' : 'task-sync']"
      >
        <span :class="['dot', dotClass(item)]" />
        <div class="task-body">
          <span class="task-title">{{ item.title }}</span>
          <span v-if="item.detail" class="task-detail">{{ item.detail }}</span>
        </div>
        <div v-if="item.type === 'sync'" class="task-meta">
          <span v-if="item.timestamp" class="task-time">{{ relativeTime(item.timestamp) }}</span>
          <span v-if="item.duration_s != null" class="task-dur">{{ formatDuration(item.duration_s) }}</span>
          <span v-if="item.records" class="task-records">{{ item.records.toLocaleString() }} records</span>
        </div>
      </component>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { api } from '@/api/client'

interface TaskItem {
  type: 'sync' | 'action'
  action_key: string | null
  title: string
  detail: string | null
  link: string | null
  count: number | null
  timestamp: string | null
  duration_s: number | null
  records: number | null
  status: string | null
}

const items = ref<TaskItem[]>([])

onMounted(async () => {
  try {
    const res = await api.get('/admin/tasks', { params: { limit: 10 } })
    items.value = res.data
  } catch {
    // Panel is supplementary — don't surface fetch errors to the user
  }
})

function dotClass(item: TaskItem): string {
  if (item.type === 'action') return 'dot-action'
  return `dot-${item.status ?? 'unknown'}`
}

function relativeTime(ts: string): string {
  const d = dayjs(ts)
  const diffH = dayjs().diff(d, 'hour')
  if (diffH < 1) return `${dayjs().diff(d, 'minute')}m ago`
  if (diffH < 24) return `${diffH}h ago`
  const diffD = dayjs().diff(d, 'day')
  if (diffD < 7) return `${diffD}d ago`
  return d.format('MMM D')
}

function formatDuration(s: number): string {
  if (s < 60) return `${Math.round(s)}s`
  return `${Math.round(s / 60)}m`
}
</script>

<style scoped>
.tasks-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
}

.tasks-title {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted);
  margin: 0 0 8px;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 0.82rem;
  text-decoration: none;
  color: inherit;
}

.task-action {
  border-left: 3px solid #D97706;
  background: #FFFBEB;
  cursor: pointer;
}

.task-action:hover { background: #FEF3C7; }

.task-sync { border-left: 3px solid transparent; }

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-success { background: #16A34A; }
.dot-error   { background: #DC2626; }
.dot-running { background: #D97706; }
.dot-unknown { background: #9A9690; }
.dot-action  { background: #D97706; }

.task-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.task-title { font-weight: 600; color: var(--text); }
.task-detail { font-size: 0.75rem; color: var(--muted); }

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--muted);
}
</style>
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend
npm run type-check
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/TasksPanel.vue
git commit -m "feat: add TasksPanel component for system activity feed"
```

---

## Task 5: DailyOverview.vue Integration

**Files:**
- Modify: `frontend/src/views/DailyOverview.vue`

Add `TasksPanel` import and insert `<TasksPanel />` immediately after `<header class="page-header">` and before `<div class="stat-grid">`.

- [ ] **Step 1: Add the import**

In `frontend/src/views/DailyOverview.vue`, in the `<script setup lang="ts">` block, add this import alongside the existing UI component imports:

```typescript
import TasksPanel from '@/components/ui/TasksPanel.vue'
```

The existing imports block looks like:
```typescript
import DateRangePicker from '@/components/ui/DateRangePicker.vue'
import MetricCard from '@/components/ui/MetricCard.vue'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart.vue'
import HrZonesChart from '@/components/charts/HrZonesChart.vue'
```

Add `TasksPanel` after `MetricCard`.

- [ ] **Step 2: Insert the component in the template**

In the template, locate this structure:

```html
    </header>

    <div v-if="loading" class="loading">
```

Insert `<TasksPanel />` between the closing `</header>` tag and the `v-if="loading"` div:

```html
    </header>

    <TasksPanel />

    <div v-if="loading" class="loading">
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npm run type-check
```

Expected: no errors.

- [ ] **Step 4: Manual smoke test**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Navigate to Daily Overview. Verify:
- "System Activity" panel appears above the stat cards
- Sync history rows show with colored dots, timestamp, duration, and record count
- If profile is incomplete, an amber action item row appears with link to /admin
- Clicking an action item navigates correctly

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/DailyOverview.vue
git commit -m "feat: mount TasksPanel in DailyOverview above stat cards"
```

---

## Post-Implementation: Version Bump

- [ ] **Bump version to 0.8.0 in `backend/pyproject.toml`**

```toml
version = "0.8.0"
```

- [ ] **Update version string in `backend/garminview/api/main.py`**

Find the two occurrences of `"0.7.0"` and change both to `"0.8.0"`.

- [ ] **Commit, tag, push**

```bash
git add backend/pyproject.toml backend/garminview/api/main.py
git commit -m "chore: bump version to v0.8.0"
git tag v0.8.0
git push && git push --tags
```
