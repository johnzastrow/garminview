# Actalog Review Workflow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Actalog pipeline: auto-parse after sync, review queue UI with editable Markdown, write-back to Actalog API, and consolidate all Actalog UI into a tabbed screen.

**Architecture:** Hook the parser into the existing sync job. Add a write-back service that authenticates with Actalog's JWT API. Build a ReviewQueue Vue component with list/detail/edit/preview. Restructure ActalogDashboard.vue into tabs, moving parser and connection config from Admin.vue.

**Tech Stack:** Python/FastAPI, httpx (Actalog API client), Vue 3 Composition API, marked (Markdown rendering)

**Spec:** `docs/superpowers/specs/2026-04-12-actalog-review-workflow-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/garminview/core/startup.py` | Modify | Add parser trigger after sync |
| `backend/garminview/ingestion/actalog_writeback.py` | Create | Actalog API write-back client |
| `backend/garminview/api/routes/actalog.py` | Modify | Add queue filters, write-back on approve |
| `backend/tests/ingestion/test_actalog_writeback.py` | Create | Write-back unit tests |
| `frontend/src/components/actalog/ReviewQueue.vue` | Create | Review queue list + detail + edit |
| `frontend/src/views/ActalogDashboard.vue` | Modify | Restructure into tabs |
| `frontend/src/views/Admin.vue` | Modify | Comment out parser/actalog sections |

---

### Task 1: Auto-parse after sync

**Files:**
- Modify: `backend/garminview/core/startup.py`

- [ ] **Step 1: Add parser call after sync completes**

In `_actalog_job()`, after the sync success log line (line ~82), add the parser trigger:

```python
            _log.info("Actalog scheduled sync complete")

            # Auto-parse any new workout notes through the LLM
            try:
                from garminview.ingestion.notes_parser import NotesParser
                from garminview.api.routes.actalog import seed_default_config
                seed_default_config(session)
                parser = NotesParser(session)
                parsed_count = parser.parse_all_pending()
                session.commit()
                if parsed_count > 0:
                    _log.info("Auto-parsed %d workout notes after sync", parsed_count)
            except Exception as exc:
                _log.warning("Auto-parse after sync failed (non-fatal): %s", exc)
```

The parser already skips workouts with existing parse records. The `try/except` ensures a parser failure (e.g., Ollama down) doesn't break the sync job.

- [ ] **Step 2: Verify parse_all_pending exists**

Check if `NotesParser` has a `parse_all_pending()` method. If it only has `parse_workout(workout_id)`, we need to add a batch method. Read the parser class:

```bash
grep -n "def parse" backend/garminview/ingestion/notes_parser.py
```

If `parse_all_pending` doesn't exist, add it — it should query all workouts with notes that don't have a parse record, and call `parse_workout` for each.

- [ ] **Step 3: Test**

```bash
cd backend && uv run pytest -q
```

Verify existing tests still pass. The auto-parse is tested by running a sync manually and checking for new parse records.

- [ ] **Step 4: Commit**

```bash
git add backend/garminview/core/startup.py backend/garminview/ingestion/notes_parser.py
git commit -m "feat: auto-parse workout notes after scheduled Actalog sync"
```

---

### Task 2: Queue API — add filters, sorting, and search

**Files:**
- Modify: `backend/garminview/api/routes/actalog.py`

- [ ] **Step 1: Update get_parser_queue endpoint**

Replace the existing `get_parser_queue` function (around line 617) with enhanced filtering:

```python
@parser_router.get("/queue", response_model=NoteParseQueue)
def get_parser_queue(
    status: str | None = Query(None, description="Filter by parse_status"),
    content_class: str | None = Query(None, description="Filter by content_class"),
    q: str | None = Query(None, description="Keyword search in workout name and notes"),
    sort: str = Query("date", description="Sort field: date"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    session: Session = Depends(get_db),
):
    """List staged parse records with filtering, sorting, and search."""
    query = session.query(ActalogNoteParse)

    # Filter by status
    if status:
        query = query.filter(ActalogNoteParse.parse_status == status)

    # Filter by content class
    if content_class:
        query = query.filter(ActalogNoteParse.content_class == content_class)

    # Keyword search across workout name and raw notes
    if q:
        search_term = f"%{q}%"
        query = query.join(
            ActalogWorkout, ActalogNoteParse.workout_id == ActalogWorkout.id
        ).filter(
            or_(
                ActalogWorkout.name.ilike(search_term),
                ActalogNoteParse.raw_notes.ilike(search_term),
            )
        )

    # Sorting
    if sort == "date":
        sort_col = ActalogNoteParse.parsed_at
    else:
        sort_col = ActalogNoteParse.parsed_at

    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    rows = query.all()
    return NoteParseQueue(
        total=len(rows),
        items=[_parse_item(r, session) for r in rows],
    )
```

Add the `or_` import at the top of the file if not already present:

```python
from sqlalchemy import or_
```

- [ ] **Step 2: Test**

```bash
cd backend && uv run pytest -q
```

- [ ] **Step 3: Commit**

```bash
git add backend/garminview/api/routes/actalog.py
git commit -m "feat: add filters, sorting, and keyword search to parser queue API"
```

---

### Task 3: Actalog write-back service

**Files:**
- Create: `backend/garminview/ingestion/actalog_writeback.py`
- Create: `backend/tests/ingestion/test_actalog_writeback.py`

- [ ] **Step 1: Create the write-back client**

Create `backend/garminview/ingestion/actalog_writeback.py`:

```python
"""
Actalog API write-back client.

Authenticates with the Actalog API (JWT), pushes approved workout data:
- Updated Markdown notes via PUT /workouts/{id}
- New WODs via POST /wods
- New movements via POST /movements
"""
import json
import logging
from datetime import datetime

import httpx

from garminview.models.actalog import ActalogNoteParse, ActalogWorkout
from garminview.models.config import AppConfig

_log = logging.getLogger(__name__)


class ActalogWritebackClient:
    """HTTP client for writing data back to the Actalog API."""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.token: str | None = None
        self.client = httpx.Client(timeout=30)

    def login(self) -> None:
        """Authenticate with Actalog API and store JWT token."""
        resp = self.client.post(
            f"{self.base_url}/auth/login",
            json={"email": self.email, "password": self.password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data.get("token") or data.get("access_token")
        if not self.token:
            raise ValueError("No token in login response")
        _log.info("Authenticated with Actalog API")

    def _headers(self) -> dict:
        if not self.token:
            self.login()
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request, retry once on 401."""
        resp = self.client.request(
            method, f"{self.base_url}{path}",
            headers=self._headers(), **kwargs,
        )
        if resp.status_code == 401:
            self.login()
            resp = self.client.request(
                method, f"{self.base_url}{path}",
                headers=self._headers(), **kwargs,
            )
        resp.raise_for_status()
        return resp

    def update_workout_notes(self, workout_id: int, notes: str) -> dict:
        """Update workout notes via PUT /workouts/{id}."""
        resp = self._request("PUT", f"/api/workouts/{workout_id}", json={"notes": notes})
        return resp.json()

    def get_wods(self) -> list[dict]:
        """Fetch all WODs from Actalog."""
        resp = self._request("GET", "/api/wods")
        return resp.json()

    def create_wod(self, name: str, regime: str = "", score_type: str = "") -> dict:
        """Create a new WOD in Actalog."""
        resp = self._request("POST", "/api/wods", json={
            "name": name,
            "regime": regime,
            "score_type": score_type,
        })
        return resp.json()

    def get_movements(self) -> list[dict]:
        """Fetch all movements from Actalog."""
        resp = self._request("GET", "/api/movements")
        return resp.json()

    def create_movement(self, name: str, movement_type: str = "") -> dict:
        """Create a new movement in Actalog."""
        resp = self._request("POST", "/api/movements", json={
            "name": name,
            "type": movement_type,
        })
        return resp.json()

    def close(self):
        self.client.close()


def _get_client_from_config(session) -> ActalogWritebackClient:
    """Create an ActalogWritebackClient from app_config settings."""
    def cfg(key: str) -> str | None:
        row = session.get(AppConfig, key)
        return row.value if row else None

    url = cfg("actalog_url")
    email = cfg("actalog_email")
    password = cfg("actalog_password")

    if not url or not email or not password:
        raise ValueError("Actalog connection not configured (URL, email, or password missing)")

    return ActalogWritebackClient(base_url=url, email=email, password=password)


def write_back_approved(session, parse_id: int) -> str:
    """
    Push an approved parse record to the Actalog API.

    Returns "sent" on success, "approved" on failure (stays approved locally).
    """
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise ValueError(f"Parse record {parse_id} not found")
    if record.parse_status not in ("approved",):
        raise ValueError(f"Parse {parse_id} has status '{record.parse_status}', expected 'approved'")

    workout = session.get(ActalogWorkout, record.workout_id)
    if not workout:
        raise ValueError(f"Workout {record.workout_id} not found")

    try:
        client = _get_client_from_config(session)

        # 1. Update workout notes with approved Markdown
        markdown = workout.formatted_notes or workout.notes
        if markdown:
            client.update_workout_notes(workout.id, markdown)
            _log.info("Updated notes for workout %d on Actalog", workout.id)

        # 2. Create WODs from parsed JSON if present
        if record.parsed_json:
            parsed = json.loads(record.parsed_json)
            wods = parsed.get("wods", [])

            if wods:
                # Fetch existing WODs for dedup (case-insensitive name match)
                existing_wods = {w["name"].lower() for w in client.get_wods()}

                for wod in wods:
                    wod_name = wod.get("name", "")
                    if wod_name and wod_name.lower() not in existing_wods:
                        client.create_wod(
                            name=wod_name,
                            regime=wod.get("regime", ""),
                            score_type=wod.get("score_type", ""),
                        )
                        _log.info("Created WOD '%s' on Actalog", wod_name)
                    else:
                        _log.debug("WOD '%s' already exists, skipping", wod_name)

        # 3. Mark as sent
        record.parse_status = "sent"
        record.reviewed_at = datetime.now()
        session.commit()
        client.close()
        return "sent"

    except Exception as exc:
        _log.error("Write-back to Actalog failed for parse %d: %s", parse_id, exc)
        # Stay approved locally — user can retry
        record.error_message = str(exc)
        session.commit()
        return "approved"
```

- [ ] **Step 2: Create unit test**

Create `backend/tests/ingestion/test_actalog_writeback.py`:

```python
"""Tests for Actalog write-back client."""
from unittest.mock import MagicMock, patch
import pytest

from garminview.ingestion.actalog_writeback import ActalogWritebackClient


def test_login_stores_token():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    with patch.object(client.client, "post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"token": "jwt123"},
            raise_for_status=lambda: None,
        )
        client.login()
    assert client.token == "jwt123"


def test_update_workout_notes():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    client.token = "jwt123"
    with patch.object(client.client, "request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 1, "notes": "updated"},
            raise_for_status=lambda: None,
        )
        result = client.update_workout_notes(1, "# WOD\nFran")
    mock_req.assert_called_once()
    assert "PUT" in str(mock_req.call_args)


def test_create_wod():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    client.token = "jwt123"
    with patch.object(client.client, "request") as mock_req:
        mock_req.return_value = MagicMock(
            status_code=201,
            json=lambda: {"id": 42, "name": "Fran"},
            raise_for_status=lambda: None,
        )
        result = client.create_wod("Fran", "FOR_TIME", "TIME")
    assert result["name"] == "Fran"


def test_retry_on_401():
    client = ActalogWritebackClient("http://test", "a@b.com", "pass")
    client.token = "expired"

    call_count = 0
    def mock_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = MagicMock(status_code=401)
            return resp
        return MagicMock(
            status_code=200,
            json=lambda: {"ok": True},
            raise_for_status=lambda: None,
        )

    with patch.object(client.client, "request", side_effect=mock_request):
        with patch.object(client, "login"):
            result = client._request("GET", "/api/test")
    assert call_count == 2
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/ingestion/test_actalog_writeback.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/garminview/ingestion/actalog_writeback.py backend/tests/ingestion/test_actalog_writeback.py
git commit -m "feat: Actalog write-back client with JWT auth and dedup"
```

---

### Task 4: Wire write-back into approve endpoint

**Files:**
- Modify: `backend/garminview/api/routes/actalog.py`

- [ ] **Step 1: Update approve_parse to trigger write-back**

Replace the `approve_parse` function (around line 654):

```python
@parser_router.post("/approve/{parse_id}", response_model=NoteParseItem)
def approve_parse(
    parse_id: int,
    body: NoteParseApproveIn,
    session: Session = Depends(get_db),
):
    """Approve a parse record. Writes Markdown to workout.notes, then pushes to Actalog API."""
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise HTTPException(status_code=404, detail="Parse record not found")

    workout = session.get(ActalogWorkout, record.workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Apply any human edits supplied in the request body
    markdown = body.formatted_markdown or workout.formatted_notes
    perf_notes = body.performance_notes or workout.performance_notes

    # Write approved Markdown to the canonical notes field
    workout.notes = markdown
    workout.formatted_notes = markdown
    workout.performance_notes = perf_notes

    record.parse_status = "approved"
    record.reviewed_at = datetime.now()
    session.commit()

    # Trigger write-back to Actalog API (non-blocking — failure keeps status=approved)
    from garminview.ingestion.actalog_writeback import write_back_approved
    final_status = write_back_approved(session, parse_id)
    _log.info("Parse %d: approve → %s", parse_id, final_status)

    # Refresh record after potential status change
    session.refresh(record)
    return _parse_item(record, session)
```

- [ ] **Step 2: Add a retry endpoint for approved-but-not-sent items**

Add after `approve_parse`:

```python
@parser_router.post("/push/{parse_id}", response_model=NoteParseItem)
def push_to_actalog(
    parse_id: int,
    session: Session = Depends(get_db),
):
    """Retry pushing an approved parse to Actalog API."""
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise HTTPException(status_code=404, detail="Parse record not found")
    if record.parse_status != "approved":
        raise HTTPException(status_code=400, detail="Only approved (not yet sent) records can be pushed")

    from garminview.ingestion.actalog_writeback import write_back_approved
    final_status = write_back_approved(session, parse_id)
    session.refresh(record)
    return _parse_item(record, session)
```

- [ ] **Step 3: Test**

```bash
cd backend && uv run pytest -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/garminview/api/routes/actalog.py
git commit -m "feat: trigger Actalog write-back on approve, add retry push endpoint"
```

---

### Task 5: ReviewQueue.vue component

**Files:**
- Create: `frontend/src/components/actalog/ReviewQueue.vue`

- [ ] **Step 1: Install marked for Markdown rendering**

```bash
cd frontend && npm install marked
```

- [ ] **Step 2: Create the ReviewQueue component**

Create `frontend/src/components/actalog/ReviewQueue.vue`. This is a large component with:

**Template structure:**
- Filter bar: status dropdown, content_class dropdown, keyword search input, sort toggle button
- Table of parse records: date, workout name, content_class badge, status badge, model
- Expandable detail row (or modal) when clicking a row:
  - Left panel: original raw notes (pre tag, read-only)
  - Right panel: edit/preview toggle
    - Edit mode: textarea with Markdown
    - Preview mode: rendered Markdown via `marked`
  - Structured data: WODs list with name/regime/score_type
  - Action buttons: Save, Approve, Reject, Reparse
  - Keyboard hints shown at bottom
- Empty state when no pending items

**Script (Composition API):**
- `ref`s: items, filters (status, content_class, q), sortOrder, selectedItem, editMode, editedMarkdown
- `fetchQueue()` — calls `GET /admin/actalog/parser/queue` with filter params
- `approveItem(id)` — calls `POST /admin/actalog/parser/approve/{id}` with `{ formatted_markdown: editedMarkdown }`
- `rejectItem(id)` — calls `POST /admin/actalog/parser/reject/{id}`
- `reparseItem(workoutId)` — calls `POST /admin/actalog/parser/reparse/{workoutId}` with confirm dialog
- `pushItem(id)` — calls `POST /admin/actalog/parser/push/{id}` (retry for approved-not-sent)
- `onKeydown` handler: a=approve, r=reject, n=next, e=toggle edit
- Watch filters → re-fetch

**Styling:**
- Use existing garminview CSS patterns (cards, tables, badges)
- Side-by-side panels for raw notes vs parsed
- Status badges: pending=yellow, approved=green, rejected=red, sent=blue
- Content class badges: WORKOUT=blue, MIXED=purple, PERFORMANCE=orange, SKIP=gray

The component should be self-contained — it calls the API directly and manages its own state.

- [ ] **Step 3: Test in browser**

Start the dev server and navigate to wherever we mount the component (Task 6 integrates it into ActalogDashboard tabs).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/actalog/ReviewQueue.vue frontend/package.json frontend/package-lock.json
git commit -m "feat: ReviewQueue component with edit/preview, filters, keyboard shortcuts"
```

---

### Task 6: Consolidate ActalogDashboard into tabs

**Files:**
- Modify: `frontend/src/views/ActalogDashboard.vue`
- Modify: `frontend/src/views/Admin.vue`

- [ ] **Step 1: Add tabs to ActalogDashboard.vue**

Restructure `ActalogDashboard.vue` to use a tab system. Add a `ref activeTab = 'workouts'` and tab bar at the top.

Tabs:
- **Workouts** (default) — the existing workout list/detail content
- **Review** — mount `<ReviewQueue />`
- **Analytics** — existing analytics content (PRs, movement history, WOD history)
- **Settings** — connection config + parser config (copied from Admin.vue)

Support `?tab=review` query parameter so the Tasks Panel link works.

```vue
<template>
  <div class="dashboard">
    <div class="tab-bar">
      <button v-for="tab in tabs" :key="tab.key"
        :class="['tab', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key">
        {{ tab.label }}
        <span v-if="tab.key === 'review' && pendingCount > 0" class="badge">{{ pendingCount }}</span>
      </button>
    </div>

    <div v-if="activeTab === 'workouts'">
      <!-- existing workout list/detail content -->
    </div>

    <div v-if="activeTab === 'review'">
      <ReviewQueue />
    </div>

    <div v-if="activeTab === 'analytics'">
      <!-- existing analytics content -->
    </div>

    <div v-if="activeTab === 'settings'">
      <!-- connection config + parser config moved from Admin.vue -->
    </div>
  </div>
</template>
```

- [ ] **Step 2: Move settings from Admin.vue**

Copy the parser config section and actalog connection config from `Admin.vue` into the Settings tab of `ActalogDashboard.vue`. Include the associated script logic (parserForm, saveParserConfig, runParser, etc).

- [ ] **Step 3: Comment out moved sections in Admin.vue**

In `Admin.vue`, wrap the parser tab section in HTML comments:

```html
<!-- MOVED TO /actalog Settings tab
<div v-if="activeTab === 'parser'" class="parser-panel">
  ... entire parser section ...
</div>
-->
```

Also comment out the parser tab button in the tab bar.

Remove the parser-related data/methods from Admin.vue's script section — or leave them (they're harmless commented out in template).

- [ ] **Step 4: Update Tasks Panel link**

In `Admin.vue` or wherever the Tasks Panel generates the actalog review link, update from `/actalog` to `/actalog?tab=review`.

- [ ] **Step 5: Read tab from URL query param**

In ActalogDashboard.vue setup:

```js
import { useRoute } from 'vue-router'
const route = useRoute()
const activeTab = ref(route.query.tab || 'workouts')
```

- [ ] **Step 6: Test in browser**

- Navigate to `/actalog` — should show Workouts tab
- Navigate to `/actalog?tab=review` — should show Review Queue
- Navigate to `/actalog?tab=settings` — should show parser config + connection settings
- Click Tasks Panel "N workout notes awaiting review" — should land on Review tab

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/ActalogDashboard.vue frontend/src/views/Admin.vue frontend/src/components/actalog/
git commit -m "feat: consolidate Actalog UI into tabbed screen, move parser config from Admin"
```

---

### Task 7: Version bump + final integration test

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `TODO.md`

- [ ] **Step 1: Bump version**

Update version in `backend/pyproject.toml` to `0.10.0`.

- [ ] **Step 2: Update TODO.md**

Move Feature C from "Upcoming" to "Completed":

```markdown
### Actalog Review Workflow (2026-04-13)

- [x] Auto-parse workout notes after scheduled sync
- [x] Review queue UI with editable Markdown + preview toggle
- [x] Sortable/filterable queue with keyword search
- [x] Write-back to Actalog API (JWT auth, WOD/movement creation)
- [x] Retry push for approved-not-sent items
- [x] Consolidated Actalog screen with tabs (Workouts, Review, Analytics, Settings)
- [x] Parser and connection config moved from Admin to Actalog Settings tab
```

- [ ] **Step 3: Run full test suite**

```bash
cd backend && uv run pytest -q
```

- [ ] **Step 4: End-to-end test**

1. Trigger an Actalog sync (Admin or schedule)
2. Verify new workout notes are auto-parsed (check Review tab for pending items)
3. Open a pending parse in Review tab
4. Edit the Markdown, toggle preview
5. Approve — verify it writes to Actalog (check workout notes on albeta.fluigrid.site)
6. Verify status changes to "sent"

- [ ] **Step 5: Commit and tag**

```bash
git add -A
git commit -m "chore: bump version to v0.10.0 (Actalog review workflow)"
git tag v0.10.0
git push && git push --tags
```
