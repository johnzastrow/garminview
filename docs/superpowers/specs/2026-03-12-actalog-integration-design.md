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
- Seven backend API endpoints (data + admin)
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
| `total_time_s` | INTEGER | nullable; start + duration = workout window |
| `notes` | TEXT | nullable |
| `synced_at` | DATETIME | |

### `actalog_movements`
Reference table. Populated from workout details, not bulk catalog pull.

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `name` | TEXT |
| `movement_type` | TEXT | weightlifting, bodyweight, cardio, gymnastics |

### `actalog_wods`
Reference table. Populated from workout details, not bulk catalog pull.

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `name` | TEXT |
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
| `weight_kg` | FLOAT | nullable |
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
| `weight_kg` | FLOAT | nullable |
| `rpe` | INTEGER | nullable |
| `is_pr` | BOOLEAN | |

### `actalog_personal_records`
One row per movement. Fully replaced on every sync from `GET /api/prs`.

| Column | Type | Notes |
|--------|------|-------|
| `movement_id` | FK → actalog_movements PK | |
| `max_weight_kg` | FLOAT | nullable |
| `max_reps` | INTEGER | nullable |
| `best_time_s` | INTEGER | nullable |
| `workout_id` | INTEGER | Actalog workout ID where PR was set |
| `workout_date` | DATETIME | |

### Auth & sync config (in existing `app_config` table)

| key | description |
|-----|-------------|
| `actalog_url` | Base URL, e.g. `https://al.fluidgrid.site` |
| `actalog_email` | Login email |
| `actalog_password` | Password (plaintext; same trust level as DB) |
| `actalog_refresh_token` | Stored after first successful login |
| `actalog_last_sync` | ISO timestamp of last successful sync |
| `actalog_sync_enabled` | `true` / `false` |
| `actalog_sync_interval_hours` | Default `24` |

---

## Ingestion & Sync

### Authentication flow

1. Read `actalog_refresh_token` from `app_config`
2. If present → `POST /api/auth/refresh` → get new access token
3. If refresh fails (expired/revoked) → `POST /api/auth/login` with stored credentials → save new refresh token to `app_config`
4. Access token held in memory only, never persisted

### Sync sequence

```
1.  Authenticate → access token
2.  GET /api/workouts  (paginated, all pages)
3.  For each workout → GET /api/workouts/{id}  (full detail)
4.  Upsert actalog_movements from embedded movement data
5.  Upsert actalog_wods from embedded WOD data
6.  Upsert actalog_workouts
7.  Upsert actalog_workout_movements
8.  Upsert actalog_workout_wods
9.  GET /api/prs → DELETE + INSERT actalog_personal_records
10. Update actalog_last_sync in app_config
11. Write to sync_log (source="actalog", status, counts, errors)
```

All upserts are idempotent by Actalog's stable integer IDs. A full re-fetch on every sync is safe for a personal dataset; incremental sync (skip known IDs) can be added later if needed.

### Scheduling

A new APScheduler job `sync_actalog` registered at startup alongside the Garmin sync job. Reads `actalog_sync_interval_hours` and `actalog_sync_enabled` from `app_config` at runtime — same hot-reload pattern as `sync_schedule`. Skips silently if disabled.

### Error handling

| Condition | Behaviour |
|-----------|-----------|
| Auth failure | Log to sync_log, surface in Admin, do not wipe existing data |
| Individual workout fetch fails | Log, skip that workout, continue |
| HTTP 429 | `tenacity` exponential backoff (existing pattern) |
| Network timeout | Fail sync cleanly, retry on next scheduled run |

### New files

```
backend/garminview/ingestion/actalog_client.py   — HTTP client: auth, pagination, token refresh
backend/garminview/ingestion/actalog_sync.py     — sync orchestrator
backend/garminview/models/actalog.py             — SQLAlchemy models (six tables)
backend/garminview/api/routes/actalog.py         — REST endpoints
alembic/versions/XXXX_add_actalog_tables.py      — Alembic migration
```

---

## API Routes

### Data endpoints (accept `start` / `end` date query params)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/actalog/workouts` | Paginated session list: id, workout_date, name, type, total_time_s, movement_count |
| `GET` | `/actalog/workouts/{id}` | Full session detail: workout + all movements + all WODs |
| `GET` | `/actalog/movements` | Movements seen in logged workouts |
| `GET` | `/actalog/movements/{id}/history` | All performances for one movement: date, sets, reps, weight_kg, rpe, is_pr |
| `GET` | `/actalog/prs` | All personal records with movement name and date set |
| `GET` | `/actalog/cross-reference` | Workouts joined with same-day Garmin data (body_battery, hr_resting, sleep_score, stress_avg) via `LEFT JOIN daily_summary ON DATE(workout_date) = date` |
| `GET` | `/actalog/workouts/{id}/session-vitals` | Garmin intraday data sliced to workout window `[workout_date, workout_date + total_time_s]`: minute-level HR from `monitoring_heart_rate`, body battery events, stress samples |

### Admin endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/actalog/config` | Return config (password masked) |
| `PUT` | `/admin/actalog/config` | Update URL, email, password, interval, enabled |
| `POST` | `/admin/actalog/sync` | Trigger immediate sync, return job status |
| `GET` | `/admin/actalog/sync/status` | Last sync result: timestamp, counts, errors |

---

## Frontend

### Admin panel additions

New "Actalog" section in the existing `/admin` view:

- Base URL, email, password (masked, show/hide toggle) fields
- Sync interval selector + enabled toggle
- **Test Connection** button — attempts login, reports success/failure, does not save
- **Save** button
- **Sync Now** button — calls `POST /admin/actalog/sync`, shows live status
- Last synced timestamp + summary line ("342 workouts · 87 movements · 124 PRs")

### New view: `/actalog` — Actalog Dashboard

Added to sidebar nav. Six tabs:

#### Tab 1: Workouts
Date-filtered list of sessions. Columns: date, name, type, duration, movement count. Each row expands inline to show:
- Movement table: sets × reps × weight, RPE, PR flag
- WOD scores: WOD name, score, RPE, PR flag

#### Tab 2: Movement Progress
Dropdown to select a movement → `TimeSeriesChart` of max weight over time. Performance table below with all sessions. PR dates marked with a dot annotation.

#### Tab 3: WOD Progress
Dropdown to select a WOD → chart of performance over time. Y-axis direction and label adapt to `score_type`:
- Time → lower is better, label "mm:ss"
- Rounds+Reps → higher is better
- Max Weight → higher is better

Performance table with score, RPE, notes. PR dates marked.

#### Tab 4: Personal Records
Unified PR table covering both movement PRs (max weight, max reps, best time) and WOD PRs (best score per WOD). Columns: name, type, best value, date achieved. Sortable.

#### Tab 5: Cross-Reference
Date-range view. Training load (total volume = Σ sets × reps × weight_kg per day) plotted against Garmin wellness signals using `DualAxisChart`. User can toggle which Garmin signal to compare (body battery, sleep score, stress, resting HR). Lets the user see whether hard training days predict recovery dips the following day.

#### Tab 6: Calendar
Month-grid calendar. Days with logged workouts are highlighted; cell color encodes workout type (strength = blue, metcon = orange, cardio = green, mixed = purple). Navigation arrows for previous/next month.

Clicking a workout day opens a **Session Vitals panel** below the calendar showing:
- Workout metadata: name, type, duration, notes
- Movements table and WOD scores (same as Tab 1 inline expansion)
- High-resolution HR chart: minute-level `monitoring_heart_rate` data for the workout window `[workout_date, workout_date + total_time_s]`, rendered as a dense `TimeSeriesChart`. Reveals warmup, working sets, rest periods, and cooldown in the HR response.
- Body battery and stress readings for the same window plotted on the same time axis

---

## Cross-Source Join Strategy

All joins between Actalog and Garmin data happen at query time in SQL or Python — no data is duplicated across tables.

| Join type | Key | Used in |
|-----------|-----|---------|
| Daily | `DATE(actalog_workouts.workout_date) = daily_summary.date` | Cross-reference tab |
| Intraday window | `monitoring_heart_rate.timestamp BETWEEN workout_date AND workout_date + total_time_s` | Session vitals |
| Intraday window | `body_battery_events.start BETWEEN ...` | Session vitals |

---

## Testing

- Unit tests for `actalog_client.py`: mock HTTP responses for login, refresh, pagination, 429 retry
- Unit tests for `actalog_sync.py`: verify upsert idempotency, PR replace behaviour, sync_log entry
- Integration test: spin up a test DB, run full sync against recorded API fixtures, assert row counts
- API tests: each endpoint returns correct shape and respects date filters
- Manual smoke test: `POST /admin/actalog/sync` against live `https://al.fluidgrid.site`
