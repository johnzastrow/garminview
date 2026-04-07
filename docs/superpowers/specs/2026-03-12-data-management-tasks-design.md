# Data Management Tasks Panel — Design Spec

**Date:** 2026-03-12
**Sub-project:** B of 3 (A = HR Zones chart ✅, C = Actalog Review Workflow)

---

## Goal

Add a "System Activity" panel to the top of Daily Overview that shows recent completed sync tasks (with timing and record counts) interleaved with pending human action items (profile setup, anomaly review, Actalog note review queue). Surfaces both what the system has done and what the user needs to do, in one place.

---

## Architecture

Two layers:

1. **API** (`GET /admin/tasks`) — single endpoint in `admin.py` that aggregates sync history, profile check, anomaly count, and Actalog pending count into one sorted list.
2. **Frontend** (`TasksPanel.vue`) — renders the interleaved list at the top of `DailyOverview.vue`, above the stat cards.

No new database tables. All data comes from existing tables: `sync_log`, `user_profile`, `data_quality_flags`, `actalog_note_parses`, `app_config`.

---

## API

### `GET /admin/tasks?limit=N`

Added to `backend/garminview/api/routes/admin.py`.

Default `limit=10`. Controls how many sync_log entries are included (action items are always included when relevant and do not count against the limit).

**Response:** `list[TaskItem]` — action items first, then sync history newest-first.

#### Response schema

```python
class TaskItem(BaseModel):
    type: str              # "sync" | "action"
    action_key: str | None  # "profile_setup" | "actalog_review" | "anomalies" | None
    title: str
    detail: str | None
    link: str | None       # frontend route, for action items only
    count: int | None      # for action items with a count (e.g., pending notes)
    timestamp: datetime | None  # sync start time; null for action items
    duration_s: float | None    # finished_at - started_at; null if still running
    records: int | None    # records_upserted from sync_log
    status: str | None     # "success" | "error" | "running"; null for action items
```

#### Backend logic

Action items (included only when condition is true):

| `action_key` | Condition | `title` | `link` |
|---|---|---|---|
| `profile_setup` | `user_profile.resting_hr IS NULL OR user_profile.max_hr_override IS NULL` | `"Set resting HR and max HR"` | `"/admin"` |
| `anomalies` | `COUNT(data_quality_flags WHERE flag_type IN ('missing','implausible','duplicate','gap') AND excluded = 0) > 0` | `"N unreviewed data anomalies"` | `"/admin"` |
| `actalog_review` | Actalog enabled (`actalog_sync_enabled = "true"` in app_config) AND `COUNT(actalog_note_parses WHERE parse_status = 'pending') > 0` | `"N workout notes awaiting review"` | `"/actalog"` |

Sync items: query `sync_log ORDER BY started_at DESC LIMIT N`. For each row:
- `duration_s` = `(finished_at - started_at).total_seconds()` if `finished_at` is not null, else null
- `status` = row's `status` field (`"success"` | `"error"` | `"running"`)
- `detail` = `row.source`
- `title` = human-readable source label (see mapping below)

Source label mapping:
| `source` | `title` |
|---|---|
| `"garmin_daily"` | `"Garmin daily sync"` |
| `"garmin_monitoring"` | `"Garmin monitoring sync"` |
| `"actalog"` | `"Actalog sync"` |
| `"hr_zones"` | `"HR zones recompute"` |
| anything else | source value as-is |

#### Example response

```json
[
  {
    "type": "action",
    "action_key": "profile_setup",
    "title": "Set resting HR and max HR",
    "detail": "Required for heart rate zone analysis",
    "link": "/admin",
    "count": null,
    "timestamp": null,
    "duration_s": null,
    "records": null,
    "status": null
  },
  {
    "type": "action",
    "action_key": "actalog_review",
    "title": "5 workout notes awaiting review",
    "detail": null,
    "link": "/actalog",
    "count": 5,
    "timestamp": null,
    "duration_s": null,
    "records": null,
    "status": null
  },
  {
    "type": "sync",
    "action_key": null,
    "title": "Garmin daily sync",
    "detail": "garmin_daily",
    "link": null,
    "count": null,
    "timestamp": "2026-03-12T10:30:00",
    "duration_s": 10.4,
    "records": 147,
    "status": "success"
  }
]
```

---

## Frontend

### New component: `frontend/src/components/ui/TasksPanel.vue`

Fetches `GET /admin/tasks` on mount using `fetch` (not `useMetricData` — this endpoint has no date-range params).

**Visual treatment:**

- **Action items** — amber left border (`#D97706`), bold title, detail line, entire row is a `<router-link>` to `link`
- **Sync items** — neutral style, left-aligned icon area with colored status dot:
  - Green dot: `status = "success"`
  - Red dot: `status = "error"`, show `detail` as error excerpt (truncated to 80 chars)
  - Yellow dot: `status = "running"`
- Sync item shows: title, relative timestamp ("2 hours ago" via dayjs), duration (`10s` or `"in progress"` if null), record count (`147 records` or omitted if null/zero)
- Panel title: `"System Activity"`
- If array is empty: render nothing (no empty state — this only happens before first sync and with a complete profile)

### Integration: `frontend/src/views/DailyOverview.vue`

`<TasksPanel />` inserted immediately after `<header class="page-header">` and before `<div class="stat-grid">`.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No sync_log rows | Panel shows action items only; if none, renders nothing |
| Sync still running (`finished_at = null`) | `duration_s = null`, `status = "running"`, yellow dot |
| Sync failed | Red dot, `detail` shows truncated `error_message` |
| Actalog not configured | `actalog_review` action item skipped entirely |
| Profile fully set, queues empty | No action items; panel shows sync history only |
| All syncs successful, no pending actions | Panel shows sync history with green dots |

---

## Testing

- Unit test: `GET /admin/tasks` with seeded `sync_log` rows → correct count, shape, and ordering
- Unit test: profile missing `max_hr_override` → `profile_setup` action item present
- Unit test: profile complete → no `profile_setup` action item
- Unit test: `actalog_note_parses` has 3 pending rows AND actalog enabled → `actalog_review` action item with `count=3`
- Unit test: `actalog_sync_enabled = "false"` → no `actalog_review` action item
- Unit test: sync with `finished_at = null` → `duration_s = null`, `status = "running"`
- Frontend: manual smoke test — action items render with amber border, sync items show relative timestamp and colored dot
