# Actalog Integration — Design Spec

**Date:** 2026-03-12
**Status:** Approved
**Project:** garminview
**Feature:** Pull workout data from a self-hosted Actalog instance into garminview for storage, analysis, and cross-referencing with Garmin biometric data.

---

## Overview

Actalog is a CrossFit-focused workout logging PWA with a JWT-authenticated REST API. This integration pulls logged workout sessions (movements, WOD scores, personal records) from a user-configured Actalog instance into garminview's own database. Data is stored in dedicated `actalog_*` tables and cross-referenced with Garmin biometric data dynamically at query time — no schema merging.

**Live instance:** `https://al.fluidgrid.site` (API version 1.2.0-beta)
**Reference project:** `/home/jcz/Github/actionlog/`

---

## Scope

### In scope
- Admin UI to configure Actalog URL, credentials, sync interval
- JWT authentication with automatic token refresh
- Scheduled + manual sync of logged workouts, movement/WOD references, and personal records
- Six dedicated SQLAlchemy models with Alembic migration
- Eight backend API endpoints (data + admin)
- Frontend dashboard with six tabs including a month calendar and session vitals drill-down

### Out of scope
- Bulk catalog sync of unused movements or WODs
- Writing data back to Actalog
- Apple Health or other third-party source integrations (separate specs)

---

## Data Model

Six new tables. All use Actalog's own stable integer IDs as primary keys for idempotent upserts.

### `actalog_workouts`
One row per logged session.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Actalog's UserWorkout.ID |
| `workout_date` | DATETIME | Full timestamp — used to window Garmin intraday data |
| `workout_name` | TEXT | |
| `workout_type` | TEXT | strength, metcon, cardio, mixed |
| `total_time_s` | INTEGER | nullable; start + duration = workout window for session-vitals |
| `notes` | TEXT | nullable |
| `synced_at` | DATETIME | |

### `actalog_movements`
Reference table. Populated from workout details, not bulk catalog pull.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | TEXT | |
| `movement_type` | TEXT | weightlifting, bodyweight, cardio, gymnastics |

### `actalog_wods`
Reference table. Populated from workout details, not bulk catalog pull.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | TEXT | |
| `regime` | TEXT | EMOM, AMRAP, Fastest Time, … |
| `score_type` | TEXT | Time, Rounds+Reps, Max Weight |

### `actalog_workout_movements`
Movement performance data per session.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Actalog's UserWorkoutMovement.ID |
| `workout_id` | FK → actalog_workouts | |
| `movement_id` | FK → actalog_movements | |
| `sets` | INTEGER | nullable |
| `reps` | INTEGER | nullable |
| `weight_kg` | FLOAT | nullable; converted from user's unit at ingest (see weight unit note) |
| `time_s` | INTEGER | nullable |
| `distance_m` | FLOAT | nullable |
| `rpe` | INTEGER | nullable; 2–10 scale |
| `is_pr` | BOOLEAN | |
| `order_index` | INTEGER | display order within session |

### `actalog_workout_wods`
WOD performance data per session.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Actalog's UserWorkoutWOD.ID |
| `workout_id` | FK → actalog_workouts | |
| `wod_id` | FK → actalog_wods | |
| `score_value` | TEXT | raw formatted: "12:34", "10+15", "225.5" |
| `time_s` | INTEGER | nullable; parsed from score_value for Time WODs |
| `rounds` | INTEGER | nullable |
| `reps` | INTEGER | nullable |
| `weight_kg` | FLOAT | nullable; converted at ingest |
| `rpe` | INTEGER | nullable |
| `is_pr` | BOOLEAN | |
| `order_index` | INTEGER | display order within session |

### `actalog_personal_records`
One row per movement. Aggregated from PR-flagged instances returned by `GET /api/prs` and re-derived on every sync (see PR sync note). Nothing references this table, so DELETE + INSERT is safe.

| Column | Type | Notes |
|--------|------|-------|
| `movement_id` | INTEGER PK, FK → actalog_movements | |
| `max_weight_kg` | FLOAT | nullable |
| `max_reps` | INTEGER | nullable |
| `best_time_s` | INTEGER | nullable |
| `workout_id` | INTEGER, FK → actalog_workouts | workout where the best was set |
| `workout_date` | DATETIME | denormalised for fast display |

### Auth & sync config (in existing `app_config` table)

| key | description |
|-----|-------------|
| `actalog_url` | Base URL, e.g. `https://al.fluidgrid.site` |
| `actalog_email` | Login email |
| `actalog_password` | Password (plaintext; same trust level as DB) |
| `actalog_weight_unit` | `kg` or `lbs`; default `kg`. Must match user's Actalog settings. Used at ingest to convert to kg. |
| `actalog_refresh_token` | Stored after first successful login |
| `actalog_last_sync` | ISO timestamp of last successful sync |
| `actalog_sync_enabled` | `true` / `false` |
| `actalog_sync_interval_hours` | Default `24`. Uses APScheduler interval trigger directly rather than the `sync_schedule` cron table — a simpler mechanism appropriate for a single external source. |

---

## Ingestion & Sync

### Authentication flow

Actalog issues refresh tokens only when `"remember_me": true` is included in the login request body. The client must always set this flag.

1. Read `actalog_refresh_token` from `app_config`
2. If present → `POST /api/auth/refresh` → get new access token
3. If refresh fails (expired/revoked) → `POST /api/auth/login` with `{"email": ..., "password": ..., "remember_me": true}` → save new `refresh_token` to `app_config`
4. Access token held in memory only, never persisted

### Sync sequence

Steps 3–8 are nested inside the per-workout loop so reference tables (movements, WODs) are populated before the FK-referencing rows are inserted.

```
1.  Authenticate → access token
2.  GET /api/workouts  (paginated, all pages)
3.  For each workout in the list:
    a. GET /api/workouts/{id}  (full detail with embedded movements + WODs)
    b. Upsert actalog_movements from embedded movement records
    c. Upsert actalog_wods from embedded WOD records
    d. Upsert actalog_workouts row
    e. Upsert actalog_workout_movements rows
    f. Upsert actalog_workout_wods rows
4.  GET /api/pr-movements → returns pre-aggregated MovementPRSummary rows
    (fields: movement_id, movement_name, best_weight, best_reps, last_pr_date)
    → DELETE all actalog_personal_records → INSERT aggregated rows
    (DELETE is safe: nothing has a FK into actalog_personal_records)
    Note: do NOT use GET /api/prs — that endpoint returns individual flagged
    junction-row instances without a movement_id field and cannot be grouped.
5.  Update actalog_last_sync in app_config
6.  Write to sync_log (source="actalog", status, counts, errors)
```

All upserts are idempotent by Actalog's stable integer IDs. A full re-fetch on every sync is safe for a personal dataset; incremental sync (skip known IDs) can be added later if needed.

### PR aggregation detail

Use `GET /api/pr-movements` (not `GET /api/prs`). The `pr-movements` endpoint returns pre-aggregated `MovementPRSummary` rows, each with a `movement_id` field and best values. `GET /api/prs` returns individual flagged junction-row instances that do not include `movement_id` and cannot be reliably grouped.

`actalog_sync.py` maps `MovementPRSummary` fields as follows:
- `movement_id` → FK into `actalog_movements`
- `best_weight` → `max_weight_kg` (converted from `actalog_weight_unit` if needed)
- `best_reps` → `max_reps`
- `last_pr_date` → `workout_date`

`MovementPRSummary` has **no time field**. `best_time_s` is therefore derived after the `actalog_workout_movements` upsert completes (step 3f), by querying:
`SELECT MIN(time_s) FROM actalog_workout_movements WHERE movement_id = ? AND is_pr = true AND time_s IS NOT NULL`
for each movement. If no PR time exists, `best_time_s` is stored as NULL (column is nullable).

`workout_id` is derived similarly from `actalog_workout_movements WHERE movement_id = ? AND is_pr = true ORDER BY workout_date DESC LIMIT 1`.

### Weight unit conversion

Actalog stores weights in the user's chosen unit (lbs or kg) without tagging the unit in API responses. The `actalog_weight_unit` config key (set by the user in the Admin panel to match their Actalog settings) is read at sync time. If `lbs`, all `weight` values are multiplied by `0.453592` before storing. All `weight_kg` columns in the schema always contain kg.

### Session vitals window

`total_time_s` is nullable. When `GET /actalog/workouts/{id}/session-vitals` is called for a workout with `total_time_s IS NULL`, the endpoint returns HTTP 422 with message `"Workout has no recorded duration; session vitals unavailable"`. The frontend Session Vitals panel must handle this gracefully and show a descriptive empty state.

### Scheduling

A new APScheduler `IntervalTrigger` job `sync_actalog` registered at startup. Reads `actalog_sync_interval_hours` and `actalog_sync_enabled` from `app_config` at runtime. Skips silently if `actalog_sync_enabled` is `false`. This uses APScheduler's interval mechanism directly rather than the `sync_schedule` cron table, which is appropriate for a simple fixed-interval external source.

### Error handling

| Condition | Behaviour |
|-----------|-----------|
| Auth failure | Log to sync_log, surface in Admin, do not wipe existing data |
| Individual workout fetch fails | Log, skip that workout, continue |
| HTTP 429 | `tenacity` exponential backoff (existing pattern) |
| Network timeout | Fail sync cleanly, retry on next scheduled run |
| `total_time_s` NULL on session-vitals request | Return HTTP 422 with descriptive message |

### New files

```
backend/garminview/ingestion/actalog_client.py   — HTTP client: auth, pagination, token refresh
backend/garminview/ingestion/actalog_sync.py     — sync orchestrator + PR aggregation
backend/garminview/models/actalog.py             — SQLAlchemy models (six tables)
backend/garminview/api/routes/actalog.py         — REST endpoints
alembic/versions/XXXX_add_actalog_tables.py      — Alembic migration
```

---

## API Routes

### Data endpoints

`start` / `end` date query params accepted by workout and history endpoints. Not applicable to `movements` (reference table with no date column) or `prs`.

| Method | Path | Date params | Description |
|--------|------|------------|-------------|
| `GET` | `/actalog/workouts` | yes | Paginated session list: id, workout_date, name, type, total_time_s, movement_count |
| `GET` | `/actalog/workouts/{id}` | — | Full session detail: workout + all movements + all WODs |
| `GET` | `/actalog/workouts/{id}/session-vitals` | — | Garmin intraday data for workout window: minute-level HR, body battery events, stress samples. Returns 422 if `total_time_s` is NULL. |
| `GET` | `/actalog/movements` | — | Reference list of movements seen in logged workouts |
| `GET` | `/actalog/movements/{id}/history` | yes | All performances for one movement: date, sets, reps, weight_kg, rpe, is_pr |
| `GET` | `/actalog/prs` | — | Movement PRs (from `actalog_personal_records`) + WOD PRs (derived from `actalog_workout_wods WHERE is_pr = true` grouped by `wod_id`, taking best score per score_type) |
| `GET` | `/actalog/cross-reference` | yes | Workout days joined with same-day Garmin data (body_battery_max, hr_resting, sleep_score, stress_avg) via `LEFT JOIN daily_summary ON DATE(workout_date) = date` |

### Admin endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/actalog/config` | Return config (password masked, refresh token omitted) |
| `PUT` | `/admin/actalog/config` | Update URL, email, password, weight_unit, interval, enabled |
| `POST` | `/admin/actalog/sync` | Trigger immediate sync, return job status |
| `GET` | `/admin/actalog/sync/status` | Last sync result: timestamp, counts, errors |

---

## Frontend

### Admin panel additions

New "Actalog" section in the existing `/admin` view:

- Base URL, email, password (masked, show/hide toggle), weight unit (kg/lbs selector) fields
- Sync interval selector + enabled toggle
- **Test Connection** button — sends `POST /api/auth/login` with `remember_me: true` to the configured URL, reports success/failure, does not save credentials or token
- **Save** button
- **Sync Now** button — calls `POST /admin/actalog/sync`, shows live status
- Last synced timestamp + summary line ("342 workouts · 87 movements · 124 PRs")

### New view: `/actalog` — Actalog Dashboard

Added to sidebar nav. Six tabs:

#### Tab 1: Workouts
Date-filtered list of sessions. Columns: date, name, type, duration, movement count. Each row expands inline to show:
- Movement table: sets × reps × weight, RPE, PR flag, in `order_index` order
- WOD scores: WOD name, score, RPE, PR flag, in `order_index` order

#### Tab 2: Movement Progress
Dropdown to select a movement → `TimeSeriesChart` of max weight over time. Performance table below with all sessions. PR dates marked with a dot annotation.

#### Tab 3: WOD Progress
Dropdown to select a WOD → chart of performance over time. Y-axis direction and label adapt to `score_type`:
- `Time` → lower is better, values formatted as mm:ss
- `Rounds+Reps` → higher is better
- `Max Weight` → higher is better, values in kg

Performance table with score, RPE, notes. PR dates marked.

#### Tab 4: Personal Records
Unified PR table sourced from `GET /actalog/prs`:
- Movement PRs: name, movement type, max weight, max reps, best time, date achieved
- WOD PRs: WOD name, regime, score type, best score, date achieved
Both sections in one table, distinguished by a "type" column (Movement / WOD). Sortable by date or name.

#### Tab 5: Cross-Reference
Date-range view. Training load (total volume = Σ sets × reps × weight_kg per day, from `actalog_workout_movements`) plotted against a user-selected Garmin wellness signal using `DualAxisChart`. Toggle options: body battery, sleep score, stress, resting HR. Shows whether hard training days predict recovery dips the following day.

#### Tab 6: Calendar
Month-grid calendar. Days with logged workouts highlighted; cell color encodes workout type (strength = blue, metcon = orange, cardio = green, mixed = purple). Previous/next month navigation.

Clicking a workout day opens a **Session Vitals panel** below the calendar:
- Workout metadata: name, type, duration, notes
- Movements table and WOD scores (same as Tab 1 inline expansion)
- If `total_time_s` is NULL: show message "No duration recorded — session vitals unavailable"
- Otherwise:
  - High-resolution HR chart: minute-level `monitoring_heart_rate` data for `[workout_date, workout_date + total_time_s]`, rendered as a dense `TimeSeriesChart`
  - Body battery and stress readings for the same window on the same time axis

---

## Cross-Source Join Strategy

All joins between Actalog and Garmin data happen at query time — no data is duplicated.

| Join type | SQL key | Used in |
|-----------|---------|---------|
| Daily | `DATE(actalog_workouts.workout_date) = daily_summary.date` | Cross-reference tab |
| Intraday window | `monitoring_heart_rate.timestamp BETWEEN workout_date AND workout_date + INTERVAL total_time_s SECOND` | Session vitals HR chart |
| Intraday window | `body_battery_events.start BETWEEN workout_date AND workout_date + INTERVAL total_time_s SECOND` | Session vitals body battery |

For SQLite compatibility in dev, the interval arithmetic uses Python: `workout_date + timedelta(seconds=total_time_s)` passed as a bound parameter rather than SQL interval syntax.

---

## Testing

- Unit tests for `actalog_client.py`: mock HTTP responses for login (`remember_me: true`), `/auth/refresh`, pagination, 429 backoff
- Unit tests for `actalog_sync.py`: upsert idempotency, PR aggregation correctness, weight unit conversion, sync_log entry format
- Integration test: test DB, full sync against recorded API fixtures, assert row counts and FK integrity
- API tests: each endpoint returns correct shape; date filters respected; session-vitals returns 422 for NULL duration
- Manual smoke test: `POST /admin/actalog/sync` against live `https://al.fluidgrid.site`
