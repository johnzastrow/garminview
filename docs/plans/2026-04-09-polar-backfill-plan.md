# Polar → Core Tables Backfill Plan

**Created:** 2026-04-09  
**Status:** DRAFT — ready for review  
**Depends on:** Polar staging import (complete, 3,271 files / 26 tables)

## Overview

Backfill core garminview tables from `polar_*` staging tables. Follows the established "source wins" pattern: **Garmin data always takes priority**, Polar fills gaps only.

## Key Findings

| Fact | Value |
|------|-------|
| Polar activities pre-dating Garmin | **674 sessions** (2015-12-25 to 2021-03-28) |
| Polar sleep nights with empty Garmin data | **647 nights** (Garmin has rows but total_sleep_min=NULL) |
| Garmin sleep rows in Polar period (2019–2022) with real data | **0** |
| Polar weight snapshots | 816/820 training sessions have weight_kg |
| Polar resting HR snapshots | 816/820 training sessions have resting_hr |
| Polar VO2max snapshots | 816/820 training sessions have vo2max |

## Conflict Resolution: "Garmin Wins"

Existing pattern from `mfp_backfill.py`:
1. **No row exists** → insert with `source='polar'`
2. **Row exists with `source='polar'`** → update (re-import safe)
3. **Row exists with `source='garmin'` or `source='garmin_api'`** → **skip** (never overwrite Garmin)

Tables that need a `source` column added: `sleep`, `resting_heart_rate`  
Tables that already have `source`: `activities`, `weight`

## Phase 1: High ROI, Low Complexity

### 1A. Activities backfill

**Source:** `polar_training_sessions` + `polar_exercises` + `polar_exercise_statistics`  
**Target:** `activities`  
**Scope:** 674 pre-Garmin sessions (before 2021-03-29), plus ~146 in overlap period if no Garmin match  
**New rows:** ~674–820

**Column mapping:**

| Polar | Core `activities` | Transform |
|-------|-------------------|-----------|
| `session_id` (string) | `activity_id` (BigInteger) | Use Polar numeric ID directly (all are numeric strings) |
| `name` | `name` | Direct |
| — | `type` | `'polar'` |
| `sport_id` + `name` | `sport` | Map via lookup table (see below) |
| — | `sub_sport` | NULL |
| `start_time` | `start_time` | Direct |
| `duration_ms` | `elapsed_time_s` | `duration_ms // 1000` |
| `distance_m` | `distance_m` | Direct |
| `calories` | `calories` | Direct |
| exercise stat `HEART_RATE.avg` | `avg_hr` | From `polar_exercise_statistics` |
| exercise stat `HEART_RATE.max` | `max_hr` | From `polar_exercise_statistics` |
| exercise stat `CADENCE.avg` | `avg_cadence` | From `polar_exercise_statistics` |
| exercise stat `SPEED.avg` | `avg_speed` | From `polar_exercise_statistics` |
| `training_load` | `training_load` | Direct |
| — | `source` | `'polar'` |

**Sport ID mapping:**

| Polar sport_id | Polar name | → Core sport |
|----------------|------------|-------------|
| 1 | Running | `running` |
| 2 | Cycling | `cycling` |
| 15 | Strength tr. | `strength_training` |
| 16 | Other outdoor | `other` |
| 17 | Treadmill runn. | `treadmill_running` |
| 18 | Indoor cycling | `indoor_cycling` |
| 20 | Circuit training | `hiit` |
| 34 | HIIT | `hiit` |
| 55 | Cross-trainer | `fitness_equipment` |
| 58 | Bootcamp | `hiit` |
| 83 | Other indoor | `other` |
| 103 | Pool swimm. | `lap_swimming` |
| 111 | Mobility (dyn.) | `yoga` |
| 113 | Backcountry skiing | `backcountry_skiing` |
| 117 | Indoor rowing | `indoor_rowing` |
| 118 | Spinning | `indoor_cycling` |
| 126 | Core | `strength_training` |
| 127 | Mobility (stat.) | `yoga` |

**Dedup in overlap period:** Match on `start_time` within ±5 minutes. If a Garmin activity exists for the same time window, skip the Polar one.

### 1B. Sleep backfill

**Source:** `polar_sleep` + `polar_sleep_states`  
**Target:** `sleep`, `sleep_events`  
**Scope:** 647 nights (2019-02-04 to 2022-06-13) — all have empty Garmin rows  
**New rows:** 647 sleep + thousands of sleep_events

**Column mapping (sleep):**

| Polar | Core `sleep` | Transform |
|-------|-------------|-----------|
| `night` | `date` | Direct |
| `sleep_start` | `start` | Direct |
| `sleep_end` | `end` | Direct |
| `asleep_duration` | `total_sleep_min` | Parse ISO duration `PT6H53M30S` → minutes |
| hypnogram states | `deep_sleep_min` | Sum NONREM3 state durations |
| hypnogram states | `light_sleep_min` | Sum NONREM1+NONREM2 state durations |
| hypnogram states | `rem_sleep_min` | Sum REM state durations |
| hypnogram states | `awake_min` | Sum WAKE state durations |
| `efficiency_pct` | `score` | Scale: `round(efficiency_pct)` as rough score (0–100) |
| — | `qualifier` | Map efficiency: ≥90→'GOOD', ≥75→'FAIR', else 'POOR' |
| — | `source` | `'polar'` (new column) |

**Sleep duration calculation from hypnogram:**
Each `polar_sleep_states` row has an `offset_from_start` (ISO duration). Duration of each state = next state's offset − this state's offset. Last state runs until `sleep_end − sleep_start`.

**Sleep events mapping:**

| Polar state | Core `sleep_events.event_type` |
|-------------|-------------------------------|
| NONREM3 | `deep` |
| NONREM1, NONREM2 | `light` |
| REM | `rem` |
| WAKE | `awake` |

**Approach:** Since Garmin rows exist but are empty (total_sleep_min=NULL), **update** existing rows rather than insert. Set `source='polar'` to mark them.

### ~~1C. Weight backfill~~ — EXCLUDED

**Reason:** Polar export contains only 4 distinct weight values (70.0–73.0 kg) across 2,357 rows. These are the user's profile weight setting in Polar Flow, not actual scale measurements. Backfilling would pollute the weight table with low-fidelity data alongside real Garmin/MFP scale measurements.

## Phase 2: Medium Complexity

### 2A. Resting heart rate backfill

**Source:** `polar_training_sessions`  
**Target:** `resting_heart_rate`  
**Scope:** ~816 sessions with resting_hr, aggregate per day  
**Approach:** For each date that has Polar sessions, take the resting_hr from the earliest session that day. Only write where no Garmin row exists.

Requires adding `source` column to `resting_heart_rate`.

| Polar | Core `resting_heart_rate` | Transform |
|-------|--------------------------|-----------|
| `resting_hr` | `resting_hr` | Min per day from sessions |
| `start_time::date` | `date` | Group by date |
| — | `source` | `'polar'` (new column) |

### 2B. VO2max backfill

**Source:** `polar_training_sessions` + `polar_fitness_tests`  
**Target:** `vo2max` (supplemental table, currently empty)  
**Scope:** 816 sessions + 3 fitness tests

| Polar | Core `vo2max` | Transform |
|-------|-------------|-----------|
| `start_time::date` | `date` | Group by date |
| `vo2max` | `vo2max_running` | Direct (Polar reports overall VO2max) |
| — | `source` | `'polar'` |

### 2C. Activity records (GPS waypoints)

**Source:** `polar_exercise_routes`  
**Target:** `activity_records`  
**Scope:** 248 routes with GPS waypoints  
**Transform:** Parse `waypoints_json` array → one `activity_records` row per waypoint  
**Note:** Only for activities that were backfilled in Phase 1A (Polar-sourced)

## Phase 3: Lower ROI / Higher Complexity (deferred)

| Target | Source | Why deferred |
|--------|--------|-------------|
| `monitoring_heart_rate` | `polar_247ohr` | 229 device-days, sparse coverage, high row count from JSON expansion |
| `daily_summary` | Multiple | Complex aggregation across activity_samples + 247ohr, sparse Polar daily data |
| `daily_hr_zones` | `polar_exercise_zones` | Requires per-day zone time summing, only for activity days |
| `activity_hr_zones` | `polar_exercise_zones` | Only valuable for Phase 1A backfilled activities |

## Schema Changes Required

### New `source` column on existing tables

```sql
ALTER TABLE sleep ADD COLUMN source VARCHAR(32);
ALTER TABLE resting_heart_rate ADD COLUMN source VARCHAR(32);
```

These should be added via Alembic migration (0009). Existing rows get `source=NULL` (implicitly Garmin).

## Implementation Architecture

```
backend/garminview/ingestion/
├── polar_backfill.py          # All backfill functions
```

### Functions

```python
def backfill_polar_activities(session) -> dict      # Phase 1A
def backfill_polar_sleep(session) -> dict            # Phase 1B
def backfill_polar_weight(session) -> dict           # Phase 1C
def backfill_polar_resting_hr(session) -> dict       # Phase 2A
def backfill_polar_vo2max(session) -> dict           # Phase 2B
def backfill_polar_activity_records(session) -> dict # Phase 2C

def backfill_all_polar(session) -> dict              # Orchestrator
```

### API Endpoint

```
POST /admin/backfill/polar          → runs all phases
POST /admin/backfill/polar/sleep    → runs sleep only (etc.)
```

### Execution Order

1. Add `source` column migration (0009)
2. Activities (1A) — must run before activity_records (2C)
3. Sleep (1B)
4. Weight (1C)
5. Resting HR (2A)
6. VO2max (2B)
7. Activity records (2C) — depends on 1A

## Testing Strategy

- Run each backfill function independently
- Verify idempotency (re-run produces same counts)
- Spot-check: compare Polar sleep durations against hypnogram state totals
- Verify Garmin data untouched: `SELECT COUNT(*) FROM activities WHERE source='garmin_api'` unchanged
- Verify overlap handling: no duplicate activities within ±5 min window

## Future Work (not in this plan)

- Frontend "Polar Data" dashboard showing imported data summary
- Merge quality report: compare Polar vs Garmin for overlapping dates
- Phase 3 backfills (monitoring HR, daily summary, HR zones)
