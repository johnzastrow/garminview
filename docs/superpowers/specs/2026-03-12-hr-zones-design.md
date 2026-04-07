# HR Zones + Daily Overview Chart — Design Spec

**Date:** 2026-03-12
**Sub-project:** A of 3 (B = Data Management Tasks Panel, C = Actalog Review Workflow)

---

## Goal

Add a stacked bar + max HR line chart to the Daily Overview dashboard showing how much time per day is spent in each heart rate zone (2–5), with outlier readings visually distinguished from valid readings.

---

## Architecture

Three layers:

1. **Analysis** (`hr_zones.py`) — Karvonen zone computation from `user_profile`, outlier filtering of minute-level `monitoring_heart_rate` data, daily aggregation into `daily_hr_zones` table.
2. **API** (`GET /health/hr-zones`) — serves stored daily zone data to the frontend.
3. **Frontend** (`HrZonesChart.vue`) — stacked bar + dual-line chart rendered with vue-echarts, added to `DailyOverview.vue`.

---

## Database Schema

### New table: `daily_hr_zones`

| Column | Type | Notes |
|--------|------|-------|
| `date` | DATE (PK) | One row per day |
| `z1_min` | SMALLINT | Zone 1 minutes (stored, not charted) |
| `z2_min` | SMALLINT | Zone 2 minutes |
| `z3_min` | SMALLINT | Zone 3 minutes |
| `z4_min` | SMALLINT | Zone 4 minutes |
| `z5_min` | SMALLINT | Zone 5 minutes |
| `valid_max_hr` | SMALLINT NULLABLE | 97th percentile of non-outlier readings |
| `raw_max_hr` | SMALLINT NULLABLE | Absolute max including outliers |
| `rejected_count` | SMALLINT | Readings filtered out as outliers |
| `total_count` | SMALLINT | Total readings that day |
| `zone_method` | VARCHAR(20) | `"karvonen"` (for future extensibility) |
| `computed_at` | DATETIME | Staleness tracking |

Zone thresholds are derived at compute time from `user_profile` — not stored here. The table is fully recomputed when `user_profile.max_hr` or `user_profile.resting_hr` changes.

### Migration

New Alembic migration `0006_daily_hr_zones.py` creates this table.

---

## Backend

### Analysis module: `backend/garminview/analysis/hr_zones.py`

**`compute_zone_thresholds(max_hr: int, resting_hr: int) → dict[int, tuple[int, int]]`**
- Karvonen formula: zone boundary = resting_hr + (pct × (max_hr − resting_hr))
- Zone 1: 0–50%, Zone 2: 50–60%, Zone 3: 60–70%, Zone 4: 70–80%, Zone 5: 80–100%
- Returns `{1: (lo, hi), 2: (lo, hi), ..., 5: (lo, hi)}`

**`filter_outliers(readings: list[int], resting_hr: int, max_hr: int) → tuple[list[int], int]`**
- Valid range: `[resting_hr − 5, max_hr + 10]`
- Returns `(valid_readings, rejected_count)`

**`classify_readings(valid_readings: list[int], thresholds: dict) → dict[int, int]`**
- Counts readings per zone
- Returns `{1: count, 2: count, ..., 5: count}` (counts = minutes since readings are 1/min)

**`compute_daily_hr_zones(session: Session, dates: list[date]) → None`**
- Loads `user_profile` max_hr, resting_hr — raises `ValueError` if missing
- For each date: queries `monitoring_heart_rate` for all readings, runs filter + classify, upserts into `daily_hr_zones`
- Called on: scheduler startup (backfills any missing dates in last 90 days), and when `user_profile` max_hr or resting_hr is saved

### API endpoint

**`GET /health/hr-zones?days=N`** (added to `backend/garminview/api/routes/health.py`)

Response schema (array):
```json
[
  {
    "date": "2026-03-11",
    "z2_min": 42,
    "z3_min": 28,
    "z4_min": 15,
    "z5_min": 8,
    "valid_max_hr": 162,
    "raw_max_hr": 189,
    "rejected_count": 3,
    "total_count": 1440
  }
]
```

Default `days=30`. Zone 1 minutes are intentionally excluded from the response (resting/idle, not useful for training view).

---

## Frontend

### New component: `frontend/src/components/HrZonesChart.vue`

**Chart configuration (ECharts):**
- X-axis: dates
- Left Y-axis: minutes (for stacked bars)
- Right Y-axis: BPM (for HR lines)
- Series:
  - `bar` stacked: Z2 `#22c55e`, Z3 `#f59e0b`, Z4 `#f97316`, Z5 `#ef4444`
  - `line` solid blue `#60a5fa`: `valid_max_hr` (yAxisIndex: 1)
  - `line` dashed red `#f87171`: `raw_max_hr` (yAxisIndex: 1)
- Diamond markers on days where `raw_max_hr − valid_max_hr > 10` BPM
- Tooltip: zone breakdown in minutes + "N readings rejected (raw max: X bpm)"
- Empty state: "Set your max HR and resting HR in Profile to enable zone analysis" (shown when API returns empty array)

### Integration: `frontend/src/views/DailyOverview.vue`

`<HrZonesChart />` added below existing charts. Uses the same `days` prop as other charts on the page.

---

## Trigger logic

| Event | Action |
|-------|--------|
| App startup | Backfill missing `daily_hr_zones` rows for last 90 days |
| `user_profile` max_hr or resting_hr updated | Recompute all rows in last 90 days |
| New monitoring HR data synced | Compute for newly synced dates only |

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No `user_profile` rows | `compute_daily_hr_zones` skips silently; API returns `[]`; chart shows empty state |
| Day has zero HR readings | Row written with all zone minutes = 0, `valid_max_hr = null`, `raw_max_hr = null` |
| All readings are outliers | `valid_max_hr = null`, bars show zero, `rejected_count = total_count` |
| Profile update | Full recompute for 90-day window |

---

## Testing

- Unit tests for `compute_zone_thresholds`, `filter_outliers`, `classify_readings` with known inputs
- Integration test: `compute_daily_hr_zones` with seeded `monitoring_heart_rate` rows → asserts correct zone counts in `daily_hr_zones`
- API test: `GET /health/hr-zones?days=7` returns expected shape
- Frontend: manual smoke test — chart renders with mock data, empty state shown when no data
