# GarminView Database Schema Reference

**Database:** MariaDB (production) / SQLite (development and test)
**ORM:** SQLAlchemy 2.x with `Mapped` / `mapped_column` declarative style
**Total tables:** ~50 application tables + `alembic_version` + 11 legacy/external tables from prior GarminDB integration

> ⚠️ **Schema accuracy note:** This document has been reconciled against the live MariaDB database as of 2026-03-12. Where the live column name differs from the original SQLAlchemy model definition, both are noted with the actual live name shown first and the original model name flagged with ⚠️. The Python models should be updated in a future migration to align with the live column names.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Flow](#data-flow)
3. [Schema Groups](#schema-groups)
   - [Daily Health](#1-daily-health)
   - [Minute Monitoring](#2-minute-monitoring)
   - [Activities](#3-activities)
   - [Supplemental / Garmin Connect API](#4-supplemental--garmin-connect-api)
   - [Derived Metrics](#5-derived-metrics)
   - [Assessments & Goals](#6-assessments--goals)
   - [Nutrition (MyFitnessPal)](#7-nutrition-myfitnesspal)
   - [Sync & Schema Tracking](#8-sync--schema-tracking)
   - [Configuration](#9-configuration)
4. [Conventions](#conventions)
5. [Deduplication Strategy](#deduplication-strategy)
6. [Dialect Notes](#dialect-notes)
7. [Alembic Version Table](#alembic-version-table)
8. [Legacy / External Tables](#legacy--external-tables)

---

## Architecture Overview

GarminView uses a **two-database strategy**:

| Database | Role |
|---|---|
| **GarminDB** (SQLite, `/home/jcz/HealthData/`) | Disposable staging — downloads and parses raw Garmin files. Never queried by the API. |
| **garminview** (MariaDB in production, SQLite in dev/test) | Application database. All API endpoints and analysis read from here only. |

Ingestion adapters read from GarminDB's SQLite staging area and write into the garminview database via SQLAlchemy. Analysis is computed in-process after ingestion completes.

---

## Data Flow

```
Garmin Connect (cloud)
    │
    ▼ (python-garminconnect API or manual download)
GarminDB download pipeline
    │  Outputs: JSON files + FIT files under ~/HealthData/
    ▼
File Adapters
    ├── DailySummaryAdapter   → daily_summary
    ├── SleepAdapter          → sleep, sleep_events
    ├── ActivityFitAdapter    → activities, activity_laps, activity_records
    ├── ActivityJsonAdapter   → activities (metadata merge)
    ├── MonitoringFitAdapter  → monitoring_heart_rate, _intensity, _steps, _respiration, _pulse_ox, _climb
    ├── RHRAdapter            → resting_heart_rate
    ├── GarminDB adapters     → steps_activities, activity_hr_zones, body_battery_events, stress
    └── MFPNutritionAdapter   → mfp_daily_nutrition, mfp_food_diary
    │
    ▼ (IngestionOrchestrator)
MariaDB application database
    │
    ▼ (AnalysisEngine)
daily_derived, weekly_derived, max_hr_aging_year
    │
    ▼ (FastAPI)
REST API → Vue.js frontend
```

Additionally, users can upload a **MyFitnessPal export ZIP** via the Admin UI to populate `mfp_daily_nutrition`, `mfp_food_diary`, `mfp_measurements`, and `mfp_exercises`.

---

## Schema Groups

---

## 1. Daily Health

### `daily_summary`

**Source:** GarminDB JSON files at `FitFiles/Monitoring/YYYY/daily_summary_*.json` (or Garmin Connect API)
**PK:** `date` (natural key — one row per calendar day)
**Populated by:** `DailySummaryAdapter`

This is the primary daily aggregate table. Each row represents a full calendar day's summary exported from the Garmin device.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Calendar date. Primary key. |
| `steps` | INTEGER | YES | Total step count for the day. Sourced from `totalSteps` in the Garmin JSON. Garmin sentinel `-1` is converted to NULL. |
| ~~`floors_ascended`~~ | — | — | ⚠️ **Removed in live DB.** Original model had separate ascended/descended columns; live DB has a single `floors` column (see below). |
| ~~`floors_descended`~~ | — | — | ⚠️ **Removed in live DB.** See `floors`. |
| `distance_m` | FLOAT | YES | Total distance walked/run in metres. Sourced from `totalDistanceMeters`. |
| `calories_active` | INTEGER | YES | Active (movement) calories burned. Sourced from `activeKilocalories`. |
| `calories_bmr` | INTEGER | YES | Basal metabolic rate calories. Sourced from `bmrKilocalories`. |
| `calories_total` | INTEGER | YES | Sum of active + BMR calories. |
| `hr_min` | INTEGER | YES | Lowest heart rate recorded during the day. |
| `hr_max` | INTEGER | YES | Highest heart rate recorded during the day. |
| `hr_avg` | INTEGER | YES | Average heart rate over the entire day. |
| `hr_resting` | INTEGER | YES | Resting heart rate as determined by Garmin's algorithm (lowest overnight HR). ⚠️ Live column name is `hr_resting`, not `resting_hr`. |
| `stress_avg` | INTEGER | YES | Average stress level (0–100 scale). Derived by Garmin from HRV measurements throughout the day. |
| `body_battery_max` | INTEGER | YES | Maximum body battery level reached. Body battery is Garmin's energy reserve metric (0–100), charged during rest and depleted during activity. ⚠️ Live column name is `body_battery_max`, not `body_battery_high`. |
| `body_battery_min` | INTEGER | YES | Minimum body battery level reached during the day. ⚠️ Live column name is `body_battery_min`, not `body_battery_low`. |
| `spo2_avg` | FLOAT | YES | Average blood oxygen saturation (SpO2) percentage. Measured by the device's pulse oximeter. |
| `respiration_avg` | FLOAT | YES | Average respiration rate in breaths per minute. Measured via wrist-based sensor. |
| `hydration_ml` | INTEGER | YES | Fluid intake logged by the user in millilitres. User-entered data. |
| `hydration_goal_ml` | INTEGER | YES | Daily hydration goal in millilitres as set on the device. |
| `floors` | FLOAT | YES | Net floors climbed (ascended minus descended). ⚠️ Live DB has a single `floors` column; the original model had separate `floors_ascended`/`floors_descended`. |
| `sleep_score` | INTEGER | YES | Garmin's overall sleep quality score for the associated sleep session, denormalised onto the daily summary for convenience. |
| `intensity_min_moderate` | INTEGER | YES | Minutes of moderate-intensity activity (heart rate in zone 2 equivalent). Contributes to Garmin's weekly intensity minute goal. |
| `intensity_min_vigorous` | INTEGER | YES | Minutes of vigorous-intensity activity (heart rate in zone 3+). Counted as double toward the Garmin weekly intensity minute goal. |

---

### `sleep`

**Source:** GarminDB JSON files at `Sleep/*.json`
**PK:** `date` (natural key — one row per sleep session, keyed to the wake date)
**Populated by:** `SleepAdapter`

Sleep sessions are linked to the calendar date on which the person woke up. The `start` timestamp may fall the previous calendar day for late-night sleepers.

⚠️ **Live column names differ from original model names** — see notes in each row.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Wake date (calendar day the sleep session ended). Primary key. |
| `start` | DATETIME | YES | UTC timestamp when sleep began. ⚠️ Live column is `start`, not `sleep_start`. |
| `end` | DATETIME | YES | UTC timestamp when sleep ended. ⚠️ Live column is `end`, not `sleep_end`. |
| `total_sleep_min` | INTEGER | YES | Total time asleep in minutes (excludes awake periods during the night). |
| `deep_sleep_min` | INTEGER | YES | Minutes spent in deep (N3) sleep. Determined by Garmin's wrist-based algorithm. |
| `light_sleep_min` | INTEGER | YES | Minutes spent in light (N1/N2) sleep. |
| `rem_sleep_min` | INTEGER | YES | Minutes spent in REM sleep. |
| `awake_min` | INTEGER | YES | Minutes spent awake during the sleep window (between start and end). |
| `score` | INTEGER | YES | Garmin's overall sleep quality score (0–100). Composite of duration, stages, and HRV. ⚠️ Live column is `score`, not `sleep_score`. |
| `sleep_qualifier` | VARCHAR(32) | YES | Text qualifier: "EXCELLENT", "GOOD", "FAIR", "POOR". |
| `avg_spo2` | FLOAT | YES | Average blood oxygen saturation during sleep. |
| `avg_respiration` | FLOAT | YES | Average respiration rate during sleep in breaths per minute. |
| `avg_stress` | INTEGER | YES | Average stress level during sleep. Low values indicate good parasympathetic recovery. |

---

### `sleep_events`

**Source:** Derived from sleep JSON stage breakdown data
**PK:** `id` (autoincrement) + indexed on `date`
**Dedup strategy:** Delete date range then re-insert (not upsert — no natural unique key per event)
**Populated by:** `SleepAdapter`

Each row is one contiguous sleep stage episode within a sleep session. A single night typically generates 15–40 rows.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `date` | DATE | NO | Wake date of the parent sleep session. Indexed. |
| `event_type` | VARCHAR(32) | YES | Stage type: "DEEP", "LIGHT", "REM", "AWAKE". |
| `start_time` | DATETIME | YES | UTC start of this stage episode. |
| `duration_min` | INTEGER | YES | Duration of this stage episode in minutes. |

---

### `weight`

**Source:** Garmin Connect (manual entry or smart scale sync) via API or JSON export
**PK:** `date`
**Populated by:** API adapter or GarminDB weight file adapter

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date of measurement. Primary key. |
| `weight_kg` | FLOAT | YES | Body weight in kilograms. |
| `bmi` | FLOAT | YES | Body Mass Index calculated by Garmin: `weight_kg / height_m²`. |

---

### `stress`

**Source:** Continuous HRV-based stress monitoring from the Garmin device
**PK:** `timestamp`
**Populated by:** `GarminDBStressAdapter`

Stress is measured approximately every 3 minutes when the device detects HRV data. Values represent the sympathovagal balance at that moment.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp of the stress reading. Primary key. |
| `stress_level` | INTEGER | YES | Stress level 0–100. 0–25: rest/recovery; 26–50: low; 51–75: medium; 76–100: high. Negative values (-1, -2) indicate insufficient HRV data and are stored as NULL. |

---

### `resting_heart_rate`

**Source:** Garmin's overnight resting HR calculation
**PK:** `date`
**Populated by:** `RHRAdapter`

Resting heart rate is computed by Garmin's algorithm as the 5th percentile of heart rate readings taken between 2:00–6:00 AM while the user is still. Correlates with aerobic fitness — lower values indicate better cardiovascular health.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Calendar date. Primary key. |
| `resting_hr` | INTEGER | YES | Resting heart rate in beats per minute. |

---

## 2. Minute Monitoring

All monitoring tables are populated by `MonitoringFitAdapter`, which parses binary FIT (Flexible and Interoperable Data Transfer) files from `FitFiles/Monitoring/YYYY/*.fit`. Each FIT file covers approximately one day.

**Key technical note — FIT timestamp resolution:** Garmin devices write monitoring FIT messages with a 16-bit relative timestamp (`timestamp_16`) that resets every ~18 hours. The adapter resolves these to full 32-bit UTC timestamps by computing the delta from the last full `timestamp` anchor message in the file. Failing to do this results in all records having NULL timestamps.

---

### `monitoring_heart_rate`

**PK:** `timestamp`

Continuous wrist HR measurement. The device samples HR every 1–2 seconds during activity, every 2–5 minutes during rest, and every 15 minutes during sleep. Rows with NULL HR (intensity-only or steps-only records) are filtered by the orchestrator before insertion.

⚠️ Live column name is `hr`, not `heart_rate`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp. Primary key. |
| `hr` | INTEGER | YES | Instantaneous heart rate in bpm. ⚠️ Column is `hr` in the live database. |

---

### `monitoring_intensity`

**PK:** `timestamp`

Intensity minutes accumulate when HR exceeds device-computed aerobic and anaerobic thresholds. One minute of vigorous intensity counts double toward Garmin's weekly goal.

⚠️ Live column names use `_time_s` suffix (cumulative seconds), not `_min_` (minutes).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp. Primary key. |
| `moderate_time_s` | INTEGER | YES | Cumulative moderate-intensity seconds at this timestamp. ⚠️ Live column is `moderate_time_s`, not `intensity_min_moderate`. |
| `vigorous_time_s` | INTEGER | YES | Cumulative vigorous-intensity seconds at this timestamp. ⚠️ Live column is `vigorous_time_s`, not `intensity_min_vigorous`. |

---

### `monitoring_steps`

**PK:** `timestamp`

Step counts from the accelerometer. Activity type distinguishes walking, running, and cycling-detected activity.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp. Primary key. |
| `steps` | INTEGER | YES | Step count accumulated in this monitoring interval. |
| `activity_type` | VARCHAR(32) | YES | Activity type detected: "walking", "running", "cycling", "generic", etc. |

---

### `monitoring_respiration`

**PK:** `timestamp`

Respiration rate derived from the wrist's optical sensor and accelerometer, measuring chest expansion micro-movements.

⚠️ Live column name is `rr`, not `respiration_rate`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp. Primary key. |
| `rr` | FLOAT | YES | Respiration rate — breaths per minute at this timestamp. ⚠️ Live column is `rr`, not `respiration_rate`. |

---

### `monitoring_pulse_ox`

**PK:** `timestamp`

Blood oxygen saturation (SpO2) from the pulse oximeter. On Garmin devices with "All-Day Pulse Ox" enabled, readings occur every ~15 minutes. Sleep readings are more frequent.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp. Primary key. |
| `spo2` | FLOAT | YES | Blood oxygen saturation as a percentage (0–100). Values below 90% warrant medical attention. |

---

### `monitoring_climb`

**PK:** `timestamp`

Altitude and elevation change from the barometric altimeter.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `timestamp` | DATETIME | NO | UTC timestamp. Primary key. |
| `ascent_m` | FLOAT | YES | Metres ascended in this interval. |
| `descent_m` | FLOAT | YES | Metres descended in this interval. |
| `altitude_m` | FLOAT | YES | Absolute altitude in metres above sea level. |
| `cum_ascent_m` | FLOAT | YES | Cumulative ascent since the FIT file epoch (running total). Populated from the barometric altimeter's cumulative climb field in the monitoring FIT message. |
| `cum_descent_m` | FLOAT | YES | Cumulative descent since the FIT file epoch. |

---

## 3. Activities

### `activities`

**Source:** FIT activity files (`*_ACTIVITY.fit`) + JSON metadata from Garmin Connect
**PK:** `activity_id` (BIGINT — Garmin's unique activity identifier from the Connect platform)
**Indexed:** `start_time`
**Populated by:** `ActivityFitAdapter`, `ActivityJsonAdapter`

The central activity table. Each row represents one workout session. The `activity_id` is assigned by Garmin Connect and is stable across re-syncs.

⚠️ **Several column names in the live DB differ from the original model.** See notes on each row.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `activity_id` | BIGINT | NO | Garmin Connect activity ID. Primary key. |
| `name` | VARCHAR(128) | YES | User-assigned or auto-generated activity name (e.g., "Morning Run"). |
| `description` | TEXT | YES | Optional user description. |
| `sport` | VARCHAR(64) | YES | Activity sport type from FIT: "running", "cycling", "swimming", "walking", "strength_training", etc. |
| `sub_sport` | VARCHAR(64) | YES | FIT sub-sport: "road", "trail", "indoor_cycling", "treadmill", etc. |
| `type` | VARCHAR(64) | YES | High-level activity type grouping as labelled by Garmin Connect (e.g., "fitness_equipment"). Separate from `sport`. ⚠️ Live DB has `type` column; original model had `local_start_time` in this position. |
| `start_time` | DATETIME | YES | UTC start time. Indexed for date-range queries. |
| `elapsed_time_s` | FLOAT | YES | Total elapsed time (wall clock) in seconds, including pauses. |
| `moving_time_s` | FLOAT | YES | Moving time in seconds (timer-based, excludes auto-pause). ⚠️ Live column is `moving_time_s`; original model called this `duration_s`. |
| `distance_m` | FLOAT | YES | Total distance in metres. |
| `avg_hr` | INTEGER | YES | Average heart rate over the activity in bpm. |
| `max_hr` | INTEGER | YES | Peak heart rate reached during the activity. Used in max HR aging analysis. |
| `avg_cadence` | INTEGER | YES | Average step cadence (steps/min for running, rpm for cycling). |
| `avg_speed` | FLOAT | YES | Average speed in metres per second. ⚠️ Live column is `avg_speed`, not `avg_speed_ms`. |
| `max_speed` | FLOAT | YES | Peak speed in metres per second. ⚠️ Live column is `max_speed`, not `max_speed_ms`. |
| `ascent_m` | FLOAT | YES | Total elevation gain in metres (from barometric altimeter). ⚠️ Live column is `ascent_m`, not `total_ascent_m`. |
| `descent_m` | FLOAT | YES | Total elevation loss in metres. ⚠️ Live column is `descent_m`, not `total_descent_m`. |
| `calories` | INTEGER | YES | Estimated calories burned. Calculated by Garmin using HR, weight, and activity type. |
| `training_load` | FLOAT | YES | Garmin FirstBeat training load score. Based on EPOC (excess post-exercise oxygen consumption) estimation. |
| `aerobic_effect` | FLOAT | YES | Aerobic training effect (0.0–5.0). Measures improvement stimulus for aerobic base. 0.0=no benefit, 5.0=overreaching. |
| `anaerobic_effect` | FLOAT | YES | Anaerobic training effect (0.0–5.0). Measures improvement stimulus for anaerobic capacity. |
| `source` | VARCHAR(32) | YES | Import source for this activity record: "fit_file", "json_api", etc. ⚠️ Column present in live DB but absent from original model. |

---

### `activity_laps`

**PK:** `(activity_id, lap_index)`
**Populated by:** `ActivityFitAdapter` (lap FIT messages)

One row per lap within an activity. A lap can be auto (distance/time trigger) or manual (button press). Long activities may have hundreds of laps.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `activity_id` | BIGINT | NO | Foreign key to `activities`. |
| `lap_index` | INTEGER | NO | Zero-based lap number within the activity. |
| `start_time` | DATETIME | YES | UTC start of this lap. |
| `elapsed_time_s` | FLOAT | YES | Elapsed time for this lap in seconds. |
| `distance_m` | FLOAT | YES | Distance covered in this lap. |
| `avg_hr` | INTEGER | YES | Average heart rate during the lap. |
| `max_hr` | INTEGER | YES | Peak heart rate during the lap. |
| `avg_speed` | FLOAT | YES | Average speed during the lap in m/s. ⚠️ Live column is `avg_speed`, not `avg_speed_ms`. |
| `avg_cadence` | INTEGER | YES | Average cadence during the lap. |
| `ascent_m` | FLOAT | YES | Elevation gain in this lap. ⚠️ Live column is `ascent_m`, not `total_ascent_m`. |
| `calories` | INTEGER | YES | Estimated calories burned in this lap. |

---

### `activity_records`

**PK:** `(activity_id, record_index)`
**Populated by:** `ActivityFitAdapter` (record FIT messages)

One row per second (or GPS fix) within an activity. A 1-hour run generates ~3,600 rows. This is the highest-granularity activity data.

| Column | Type | Nullable | Description |
|---|---|---|---|
⚠️ Several column names use abbreviated forms in the live DB — see notes per row.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `activity_id` | BIGINT | NO | Foreign key to `activities`. |
| `record_index` | INTEGER | NO | Zero-based record sequence number. |
| `timestamp` | DATETIME | YES | UTC timestamp of this record. |
| `lat` | FLOAT | YES | GPS latitude in decimal degrees. NULL for indoor activities. ⚠️ Live column is `lat`, not `latitude`. |
| `lon` | FLOAT | YES | GPS longitude in decimal degrees. NULL for indoor activities. ⚠️ Live column is `lon`, not `longitude`. |
| `distance_m` | FLOAT | YES | Cumulative distance from activity start in metres. |
| `altitude_m` | FLOAT | YES | Barometric altitude in metres. |
| `hr` | INTEGER | YES | Heart rate at this instant in bpm. ⚠️ Live column is `hr`, not `heart_rate`. |
| `cadence` | INTEGER | YES | Cadence at this instant. |
| `speed` | FLOAT | YES | Instantaneous speed in metres per second. ⚠️ Live column is `speed`, not `speed_ms`. |
| `power` | FLOAT | YES | Instantaneous power in watts (if power meter present). ⚠️ Live column is `power`, not `power_w`. |

---

### `steps_activities`

**PK:** `activity_id`
**Source:** GarminDB steps_activities table (running-specific metrics computed by Garmin device)
**Populated by:** `GarminDBStepsActivitiesAdapter`

Running-specific biomechanics and performance data attached to activities. Only populated for run activities.

⚠️ **Many column names differ from the original model.** Running biomechanics columns use different naming conventions in the live DB.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `activity_id` | BIGINT | NO | Foreign key to `activities`. Primary key. |
| `avg_pace_min_km` | FLOAT | YES | Average pace in minutes per kilometre. |
| `pace_avg` | FLOAT | YES | Average pace (seconds per metre or min/km — confirm units from source adapter). ⚠️ Live DB has `pace_avg`; original model did not have this column. |
| `pace_moving` | FLOAT | YES | Moving pace (excludes stopped time). ⚠️ Live DB only. |
| `pace_max` | FLOAT | YES | Best (fastest) pace segment during the activity. ⚠️ Live DB only. |
| `steps_per_min` | INTEGER | YES | Average running cadence in steps per minute (typically 160–200 for recreational runners). ⚠️ Live column is `steps_per_min`, not `avg_cadence`. |
| `vertical_oscillation_mm` | FLOAT | YES | Average vertical bounce in millimetres per step. Lower is more efficient (good form: <90 mm). ⚠️ Live column is `vertical_oscillation_mm` (mm, not cm). |
| `gct_ms` | FLOAT | YES | Average ground contact time in milliseconds per step. Lower indicates better running economy (good form: <250 ms). ⚠️ Live column is `gct_ms`, not `avg_ground_contact_time_ms`. |
| `step_length_m` | FLOAT | YES | Average stride length in metres. ⚠️ Live column is `step_length_m`, not `avg_stride_length_m`. |
| `vertical_ratio_pct` | FLOAT | YES | Vertical oscillation as a percentage of stride length. Lower is more efficient. ⚠️ Live DB only column. |
| `stance_pct` | FLOAT | YES | Ground contact time as a percentage of total stride cycle. ⚠️ Live DB only column. |
| `vo2max` | FLOAT | YES | Garmin FirstBeat VO2max estimate for this activity in mL/kg/min. Computed from HR and speed using the FirstBeat algorithm. Used in the VO2max trend endpoint. |

---

### `activity_hr_zones`

**PK:** `(activity_id, zone)`
**Source:** GarminDB activity HR zone data
**Populated by:** `GarminDBHRZonesAdapter`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `activity_id` | BIGINT | NO | Foreign key to `activities`. |
| `zone` | INTEGER | NO | Zone number 1–5. |
| `time_in_zone_s` | INTEGER | YES | Seconds spent in this HR zone during the activity. |

---

## 4. Supplemental / Garmin Connect API

These tables are populated via the `python-garminconnect` API adapter. Unlike file-based tables, they require active API calls to Garmin Connect and an authenticated session.

### `hrv_data`

**PK:** `date`

HRV (Heart Rate Variability) is the variation in time between consecutive heartbeats. Higher resting RMSSD indicates better parasympathetic recovery. Garmin measures RMSSD during the first 5 minutes of sleep.

⚠️ **Live column names differ significantly from the original model.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `hrv_rmssd` | FLOAT | YES | HRV RMSSD reading in milliseconds. ⚠️ Live column is `hrv_rmssd`; original model had `last_night`. |
| `hrv_5min_high` | FLOAT | YES | Highest 5-minute RMSSD reading during the sleep session. ⚠️ Live DB only. |
| `hrv_5min_low` | FLOAT | YES | Lowest 5-minute RMSSD reading during sleep. ⚠️ Live DB only. |
| `baseline_low` | FLOAT | YES | Garmin's computed lower baseline RMSSD (based on 3-week rolling window). ⚠️ Live DB only. |
| `baseline_high` | FLOAT | YES | Garmin's computed upper baseline RMSSD. ⚠️ Live DB only. |
| `status` | VARCHAR(32) | YES | Garmin's classification relative to baseline: "BALANCED", "LOW", "HIGH", "UNBALANCED". |

---

### `training_readiness`

**PK:** `date`

Garmin's composite daily readiness score, a proprietary blend of sleep quality, HRV status, recovery time remaining, training load, and acute load.

⚠️ **Live sub-score column names differ from original model.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `score` | INTEGER | YES | Overall readiness score 0–100. ≥70 = ready for high intensity; 40–69 = moderate; <40 = recovery recommended. |
| `hrv_score` | FLOAT | YES | HRV sub-score contribution. ⚠️ Live column is `hrv_score`, not `hrv_component`. |
| `sleep_score` | FLOAT | YES | Sleep sub-score contribution. ⚠️ Live column is `sleep_score`, not `sleep_component`. |
| `recovery_score` | FLOAT | YES | Recovery time remaining sub-score. ⚠️ Live column is `recovery_score`, not `recovery_component`. |
| `training_load_score` | FLOAT | YES | Training load balance sub-score. ⚠️ Live column is `training_load_score`, not `load_component`. |

---

### `training_status`

**PK:** `date`

Garmin's assessment of whether recent training is productive (improving), maintaining, or creating stress without adaptation.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `status` | VARCHAR(32) | YES | Training status: "PRODUCTIVE", "MAINTAINING", "RECOVERY", "DETRAINING", "OVERREACHING", "PEAKING", "NO_STATUS". |
| `load_ratio` | FLOAT | YES | Ratio of current training load vs. optimal load for the athlete's fitness level. |

---

### `body_battery_events`

**PK:** `id` (autoincrement), indexed on `date`
**Source:** GarminDB via `GarminDBBodyBatteryAdapter`

Body battery changes linked to specific activities or rest periods. Each charge/drain event records the delta and cause.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `date` | DATE | NO | Calendar date. Indexed. |
| `timestamp` | DATETIME | YES | UTC timestamp of this event. |
| `body_battery` | INTEGER | YES | Body battery level at this event (0–100). |
| `event_type` | VARCHAR(32) | YES | "CHARGE" (rest/sleep) or "DRAIN" (activity/stress). |
| `activity_id` | BIGINT | YES | FK to `activities` when the event is a workout drain. NULL for rest events. |

---

### `vo2max`

**PK:** `date`

VO2max estimates from Garmin's FirstBeat algorithm, which infers VO2max from sub-maximal workouts by comparing heart rate and speed/power.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `vo2max_running` | FLOAT | YES | VO2max estimate from running activities in mL/kg/min. |
| `vo2max_cycling` | FLOAT | YES | VO2max estimate from cycling activities in mL/kg/min. Requires power meter for accuracy. |
| `fitness_age` | INTEGER | YES | Garmin's fitness age estimate — the age whose population median VO2max matches the user's current value. Lower fitness age = better fitness. |

---

### `race_predictions`

**PK:** `date`

Garmin's race time predictions derived from current VO2max, training load, and running economy.

⚠️ **Live column names use `pred_` prefix and `_s` suffix.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date of prediction. Primary key. |
| `pred_5k_s` | INTEGER | YES | Predicted 5 km race time in seconds. ⚠️ Live column is `pred_5k_s`, not `5k_sec`. |
| `pred_10k_s` | INTEGER | YES | Predicted 10 km race time in seconds. ⚠️ Live column is `pred_10k_s`, not `10k_sec`. |
| `pred_half_s` | INTEGER | YES | Predicted half marathon (21.1 km) race time in seconds. ⚠️ Live column is `pred_half_s`, not `half_marathon_sec`. |
| `pred_full_s` | INTEGER | YES | Predicted marathon (42.2 km) race time in seconds. ⚠️ Live column is `pred_full_s`, not `marathon_sec`. |

---

### `lactate_threshold`

**PK:** `date`

Lactate threshold is the exercise intensity above which blood lactate accumulates faster than it can be cleared. It predicts endurance performance more accurately than VO2max alone.

⚠️ **Live column names use `lt_` prefix.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `lt_hr` | INTEGER | YES | Heart rate at lactate threshold in bpm. ⚠️ Live column is `lt_hr`, not `hr_bpm`. |
| `lt_speed` | FLOAT | YES | Running speed at lactate threshold in m/s. ⚠️ Live column is `lt_speed`, not `speed_ms`. |
| `lt_power` | FLOAT | YES | Power output at lactate threshold in watts (cycling). ⚠️ Live DB has `lt_power`; original model had `pace_min_km` instead. |

---

### `hill_score`

**PK:** `date`

Garmin's hill climbing ability score, derived from power-to-weight ratio and heart rate performance on climbs.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `score` | FLOAT | YES | Hill score (0–100). Reflects climbing power relative to body weight. |

---

### `endurance_score`

**PK:** `date`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Date. Primary key. |
| `score` | FLOAT | YES | Endurance score (0–100). Garmin's measure of aerobic endurance capacity derived from training history and VO2max. |

---

### `personal_records`

**PK:** `id` (autoincrement)

Best-ever performances by activity type and distance/metric.

⚠️ **The live DB uses an EAV (Entity-Attribute-Value) schema for personal records**, not the multi-column model originally designed. Each PR is a single row with a `metric` name and scalar `value`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `activity_type` | VARCHAR(64) | YES | Sport type (e.g., "running", "cycling"). |
| `metric` | VARCHAR(128) | YES | What was measured, e.g., `"5k_time_s"`, `"mile_time_s"`, `"max_power_w"`. ⚠️ Live column `metric` replaces the original multi-column design. |
| `value` | FLOAT | YES | The personal record value. Units depend on `metric`. ⚠️ Live column `value` replaces `time_s`, `speed_ms`, `power_w`, `distance_m`. |
| `achieved_date` | DATE | YES | Date the PR was set. ⚠️ Live column is `achieved_date`, not `timestamp`. |

---

### `body_composition`

**PK:** `date`

Body composition data from Garmin Index smart scale or from Garmin Connect manual entry.

⚠️ Two column names differ from the original model.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Measurement date. Primary key. |
| `weight_kg` | FLOAT | YES | Body weight in kilograms. |
| `fat_pct` | FLOAT | YES | Body fat percentage. ⚠️ Live column is `fat_pct`, not `body_fat_pct`. |
| `muscle_mass_kg` | FLOAT | YES | Estimated skeletal muscle mass in kilograms. |
| `bone_mass_kg` | FLOAT | YES | Estimated bone mass in kilograms. |
| `hydration_pct` | FLOAT | YES | Body water percentage. |
| `bmi` | FLOAT | YES | Body Mass Index: weight_kg / height_m². |
| `bmr` | INTEGER | YES | Basal metabolic rate in kcal/day estimated by the scale. Uses Mifflin-St Jeor formula with body composition inputs. ⚠️ Live column is `bmr`, not `bmr_kcal`. |
| `metabolic_age` | INTEGER | YES | Scale's estimate of metabolic age based on BMR relative to population norms. |
| `physique_rating` | INTEGER | YES | Garmin Index scale physique rating (1–9 scale). ⚠️ Present in live DB; not in original model. |
| `visceral_fat` | INTEGER | YES | Visceral fat rating (1–59 scale). Values 1–9: normal; 10–14: high; 15+: very high. |

---

### `blood_pressure`

**PK:** `id` (autoincrement), indexed on `timestamp`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `timestamp` | DATETIME | YES | UTC timestamp of measurement. Indexed. |
| `systolic` | INTEGER | YES | Systolic pressure in mmHg (upper number). |
| `diastolic` | INTEGER | YES | Diastolic pressure in mmHg (lower number). |
| `pulse` | INTEGER | YES | Pulse rate at time of measurement in bpm. |

---

### `gear`

**PK:** `gear_uuid`

Equipment associated with activities (shoes, bikes, etc.).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `gear_uuid` | VARCHAR(64) | NO | Garmin Connect UUID for this gear item. Primary key. |
| `name` | VARCHAR(128) | YES | User-assigned name (e.g., "Nike Vaporfly 2"). |
| `gear_type` | VARCHAR(32) | YES | "shoes", "bike", "pedals", etc. |
| `status` | VARCHAR(16) | YES | "ACTIVE" or "RETIRED". |
| `date_begin` | DATE | YES | Date gear was put into service. |
| `date_end` | DATE | YES | Date gear was retired. NULL if still active. |

---

### `gear_stats`

**PK:** `gear_uuid`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `gear_uuid` | VARCHAR(64) | NO | FK to `gear`. Primary key. |
| `total_distance_m` | FLOAT | YES | Total distance logged with this gear in metres. |
| `activity_count` | INTEGER | YES | Number of activities recorded with this gear. |

---

## 5. Derived Metrics

Derived tables are computed in-process by `AnalysisEngine` after each sync. They are never directly ingested — all values are calculated from other tables.

### `daily_derived`

**PK:** `date`
**Computed by:** `AnalysisEngine._compute_daily_derived()`
**Dialect-aware upsert:** SQLite `ON CONFLICT DO UPDATE` / MySQL `ON DUPLICATE KEY UPDATE`

This is the primary analytics table. All training load metrics, sleep science metrics, and readiness scores live here.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Calendar date. Primary key. |
| `trimp` | FLOAT | YES | **Training Impulse (TRIMP)** — Banister (1991) formula: `duration_min × HR_fraction × exp(1.92 × HR_fraction)`, where `HR_fraction = (avg_hr − resting_hr) / (max_hr − resting_hr)`. Quantifies the physiological stress of a training session on a single dimensionless scale. Sources: `daily_summary.intensity_min_moderate/vigorous`, `daily_summary.hr_avg/max`. |
| `atl` | FLOAT | YES | **Acute Training Load** — 7-day exponentially weighted moving average of TRIMP values. Formula: `atl_today = atl_yesterday × (1 − 1/7) + trimp × (1/7)`. Represents short-term fatigue. Decay constant τ = 7 days. |
| `ctl` | FLOAT | YES | **Chronic Training Load (fitness)** — 42-day EWMA of TRIMP. Formula: `ctl_today = ctl_yesterday × (1 − 1/42) + trimp × (1/42)`. Represents long-term fitness. Decay constant τ = 42 days. |
| `tsb` | FLOAT | YES | **Training Stress Balance (form)** — `CTL − ATL`. Positive TSB means fresher/more recovered; negative TSB means fatigued. Range typically −30 to +20 for trained athletes. |
| `acwr` | FLOAT | YES | **Acute:Chronic Workload Ratio** — `ATL / CTL`. The "sweet spot" for training without elevated injury risk is 0.8–1.3. Values above 1.5 indicate high injury risk. NULL when CTL = 0. |
| `sleep_efficiency_pct` | FLOAT | YES | **Sleep Efficiency** — `total_sleep_min / (total_sleep_min + awake_min) × 100`. Healthy range: >85%. Sources: `sleep.total_sleep_min`, `sleep.awake_min`. |
| `sleep_debt_min` | FLOAT | YES | **Rolling Sleep Debt** — Cumulative shortfall relative to an 8-hour (480 min) target. Computed as a 14-day rolling deficit. |
| `sleep_sri` | FLOAT | YES | **Sleep Regularity Index (SRI)** — Probability that sleep/wake status is the same at equivalent times across consecutive days (0–100). High SRI correlates with better metabolic and cardiovascular health. Inspired by Phillips et al. (2017). ⚠️ Live column is `sleep_sri`, not `sri`. |
| `social_jet_lag_h` | FLOAT | YES | **Social Jet Lag** — Difference in hours between mid-sleep on work days vs. free days (a proxy for circadian disruption). ⚠️ Live column is `social_jet_lag_h` (hours), not `social_jet_lag_min` (minutes). |
| `lbm_kg` | FLOAT | YES | **Lean Body Mass** — `weight_kg × (1 − fat_pct / 100)`. Sourced from `body_composition` when available. |
| `ffmi` | FLOAT | YES | **Fat-Free Mass Index** — `lbm_kg / height_m²`. Normalises muscle mass for height. Values >25 in natural athletes are uncommon. |
| `body_recomp_index` | FLOAT | YES | **Body Recomposition Index** — 7-day trend combining weight change and fat% change. Positive = gaining muscle relative to fat. ⚠️ Live column is `body_recomp_index`, not `body_recomp_7d`. |
| `weight_velocity` | FLOAT | YES | **Weight Velocity** — Rate of weight change in kg/week (negative = loss, positive = gain). Computed as linear regression slope over a 14-day window. ⚠️ Live column is `weight_velocity`, not `weight_velocity_kg_wk`. |
| `readiness_composite` | FLOAT | YES | **Readiness Composite Score** — Weighted combination of HRV status, sleep efficiency, TSB, and RHR trend. Scale 0–100. Proprietary weighting derived from sports science literature. |
| `wellness_score` | FLOAT | YES | **Overall Wellness Score** — Composite of readiness, sleep, and nutrition adequacy (when MFP data available). Scale 0–100. |
| `overtraining_risk` | SMALLINT | YES | **Overtraining Risk** — Integer probability score based on ACWR, sleep debt, and HRV suppression. ⚠️ Live type is SMALLINT (0–100 integer scale), not FLOAT (0.0–1.0 probability). |
| `injury_risk` | FLOAT | YES | **Injury Risk** — Similar to overtraining risk but weighted toward acute load spikes. |

---

### `weekly_derived`

**PK:** `week_start` (Monday)
**Computed by:** `AnalysisEngine._compute_weekly_derived()`

Weekly rollup of training metrics. Populated in Phase 3 of the implementation plan.

⚠️ **Several column names use `_avg` suffix (not `avg_`) and zone columns use a 3-zone polarised model.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `week_start` | DATE | NO | Monday of the ISO week. Primary key. |
| `weekly_trimp` | FLOAT | YES | Sum of daily TRIMP for the week. Total training impulse. |
| `atl_avg` | FLOAT | YES | Average ATL across the week. ⚠️ Live column is `atl_avg`, not `avg_atl`. |
| `ctl_avg` | FLOAT | YES | Average CTL across the week. ⚠️ Live column is `ctl_avg`, not `avg_ctl`. |
| `tsb_avg` | FLOAT | YES | Average TSB across the week. Positive = fresher week, negative = accumulated fatigue. ⚠️ Live column is `tsb_avg`, not `avg_tsb`. |
| `polarized_z1_pct` | FLOAT | YES | Percentage of training time in polarised zone 1 (easy/recovery, below aerobic threshold). ⚠️ Live DB uses a 3-zone polarised model (`polarized_z1/z2/z3`), not a 5-zone model. |
| `polarized_z2_pct` | FLOAT | YES | Percentage in polarised zone 2 (moderate/tempo, between thresholds). |
| `polarized_z3_pct` | FLOAT | YES | Percentage in polarised zone 3 (hard, above lactate threshold). |
| `intensity_min_mod` | INTEGER | YES | Weekly total minutes of moderate-intensity activity. ⚠️ Live DB only column. |
| `intensity_min_vig` | INTEGER | YES | Weekly total minutes of vigorous-intensity activity. ⚠️ Live DB only column. |

---

### `activity_derived`

**PK:** `activity_id`
**Computed by:** `AnalysisEngine` post-activity analysis

Per-activity quality metrics computed from `activity_records`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `activity_id` | BIGINT | NO | FK to `activities`. Primary key. |
| `efficiency_factor` | FLOAT | YES | **Efficiency Factor** — `normalised_pace / avg_hr` (running) or `normalized_power / avg_hr` (cycling). Increases as aerobic fitness improves. |
| `pace_decoupling_pct` | FLOAT | YES | **Aerobic Decoupling (Pa:Hr decoupling)** — Difference between first-half and second-half efficiency factor as a percentage. Values >5% indicate aerobic deficiency in that session. |
| `cardiac_drift` | FLOAT | YES | **Cardiac Drift** — Rise in HR during steady-state effort due to dehydration and thermoregulation. Computed as (second-half avg HR − first-half avg HR) / first-half avg HR × 100. |
| `hr_recovery_1min` | INTEGER | YES | HR drop 1 minute after activity end. >12 bpm = normal autonomic function. |
| `hr_recovery_2min` | INTEGER | YES | HR drop 2 minutes after activity end. >22 bpm = good recovery. |

---

### `max_hr_aging_year`

**PK:** `year`
**Computed by:** `MaxHRAgingAnalysis.run()`
**Source:** `activities` table (HR and timestamps)

Tracks how actual measured maximum heart rate changes with age. Activities are filtered to minimum 10 minutes duration, minimum 130 bpm peak HR, and sports likely to elicit true maximum effort (excludes strength training, yoga, etc.). The Tanaka formula (208 − 0.7 × age) is used for age-predicted comparison.

⚠️ **All HR columns use `annual_` prefix; `decline_rate` column has a longer suffix.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `year` | INTEGER | NO | Calendar year. Primary key. |
| `age` | FLOAT | YES | User's age during this year (from `user_profile.birth_date`). |
| `annual_peak_hr` | INTEGER | YES | Single highest max_hr recorded across all qualifying activities this year. ⚠️ Live column is `annual_peak_hr`, not `peak_hr`. |
| `annual_p95_hr` | INTEGER | YES | 95th percentile of max_hr across qualifying activities. Filters outlier spikes. ⚠️ Live column is `annual_p95_hr`, not `p95_hr`. |
| `annual_p90_hr` | INTEGER | YES | 90th percentile. Used as the primary trend line (more robust than peak). ⚠️ Live column is `annual_p90_hr`, not `p90_hr`. |
| `activity_count` | INTEGER | YES | Number of qualifying activities used in the computation. |
| `age_predicted_max` | FLOAT | YES | Tanaka formula: `208 − 0.7 × age`. Population average age-predicted maximum. ⚠️ Live column is `age_predicted_max`, not `age_predicted_max_hr`. |
| `hr_reserve` | FLOAT | YES | `annual_peak_hr − resting_hr`. Heart rate reserve (Karvonen). |
| `pct_age_predicted` | FLOAT | YES | `annual_peak_hr / age_predicted_max × 100`. Values >100 indicate above-average cardiovascular fitness for age. |
| `decline_rate_bpm_per_year` | FLOAT | YES | Linear regression slope (bpm/year) fitted to the `annual_p90_hr` series. Typical expected decline: −0.7 bpm/year. Negative = declining max HR. ⚠️ Live column is `decline_rate_bpm_per_year`, not `decline_rate_bpm_yr`. |

---

## 6. Assessments & Goals

### `goals`

**PK:** `id` (autoincrement)

User-defined performance targets.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `metric` | VARCHAR(64) | YES | Metric being targeted (e.g., "vo2max", "weight_kg", "steps"). |
| `target_value` | FLOAT | YES | Numeric target. |
| `target_date` | DATE | YES | Deadline for achieving the goal. |
| `status` | VARCHAR(16) | YES | "ACTIVE", "ACHIEVED", "ABANDONED". |
| `created_at` | DATETIME | YES | Goal creation timestamp. |

---

### `assessments`

**PK:** `id` (autoincrement), indexed on `period_start`

Automated or manual weekly/monthly assessments of fitness progress.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `period_start` | DATE | YES | Start of the assessment period. Indexed. |
| `period_end` | DATE | YES | End of the assessment period. |
| `period_type` | VARCHAR(16) | YES | "WEEKLY" or "MONTHLY". |
| `category` | VARCHAR(32) | YES | Assessment category: "TRAINING_LOAD", "SLEEP", "RECOVERY", "NUTRITION", etc. |
| `severity` | VARCHAR(16) | YES | "GOOD", "WARNING", "ALERT". |
| `summary` | TEXT | YES | Human-readable summary of findings. |
| `metrics_json` | TEXT | YES | JSON blob of supporting metric values used in the assessment. |

---

### `trend_classifications`

**PK:** `id` (autoincrement), indexed on `date`

Automated linear regression trend labels on any time-series metric.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `date` | DATE | YES | Date of the classification. Indexed. |
| `metric` | VARCHAR(64) | YES | Metric name (e.g., "resting_hr", "weight_kg", "daily_derived.ctl"). |
| `direction` | VARCHAR(16) | YES | "IMPROVING", "DECLINING", "STABLE". |
| `slope` | FLOAT | YES | Linear regression slope (units/day). |
| `r_squared` | FLOAT | YES | R² of the fit (0–1). High values indicate a reliable trend. |
| `p_value` | FLOAT | YES | Statistical significance of the slope. Values <0.05 are considered significant. |
| `lookback_days` | INTEGER | YES | Number of days of history used in the regression. |

---

### `correlation_results`

**PK:** `id` (autoincrement), indexed on `computed_at`

Pairwise statistical correlations between any two metrics.

⚠️ **Correlation coefficient column names use `r_` prefix; sample count uses `n_samples`.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `metric_a` | VARCHAR(64) | YES | First metric name. |
| `metric_b` | VARCHAR(64) | YES | Second metric name. |
| `r_pearson` | FLOAT | YES | Pearson correlation coefficient (−1 to 1). Linear relationship. ⚠️ Live column is `r_pearson`, not `pearson_r`. |
| `r_spearman` | FLOAT | YES | Spearman rank correlation (−1 to 1). Monotonic relationship (more robust to outliers). ⚠️ Live column is `r_spearman`, not `spearman_r`. |
| `p_value` | FLOAT | YES | Statistical significance of the correlation. |
| `lag_days` | INTEGER | YES | Time lag applied (e.g., sleep tonight → performance tomorrow uses lag=1). |
| `n_samples` | INTEGER | YES | Number of data points used in the calculation. ⚠️ Live column is `n_samples`, not `sample_count`. |
| `computed_at` | DATETIME | YES | Timestamp when the correlation was computed. Indexed. |

---

### `data_quality_flags`

**PK:** `id` (autoincrement), indexed on `date` and `excluded`

Automated flags for data issues that may affect analysis accuracy.

⚠️ **The live DB schema is significantly simpler than the original model.** The anomaly analysis columns were removed; the schema uses `metric`/`source_table`/`record_id` instead.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `date` | DATE | YES | Date of the flagged data. Indexed. |
| `metric` | VARCHAR(64) | YES | Metric name with the data quality issue (e.g., `"resting_hr"`, `"steps"`). ⚠️ Live column is `metric`; original model had `column_name`. |
| `source_table` | VARCHAR(64) | YES | Table containing the suspect row. ⚠️ Live column is `source_table`; original model had `table_name`. |
| `record_id` | VARCHAR(128) | YES | Serialised primary key of the flagged row. ⚠️ Live column is `record_id`; original model had `value`. |
| `flag_type` | VARCHAR(32) | YES | "MISSING", "IMPLAUSIBLE", "DUPLICATE", "GAP". |
| `message` | TEXT | YES | Human-readable description of the issue. |
| `excluded` | BOOLEAN | NO | Whether this record has been excluded from analysis. Indexed for fast filtering. Default FALSE. |

---

## 7. Nutrition (MyFitnessPal)

These tables are populated either by the `MFPNutritionAdapter` (reads GarminDB-processed CSVs) or the **MFP ZIP Upload** endpoint (`POST /admin/upload/mfp`), which accepts a MyFitnessPal export ZIP and parses the three included CSVs in-memory.

**MFP ZIP export format:**
- `Nutrition-Summary-*.csv` — Per-meal nutrition totals, one row per meal per day
- `Measurement-Summary-*.csv` — Body fat % and weight entries
- `Exercise-Summary-*.csv` — Manual exercise log entries

---

### `mfp_daily_nutrition`

**PK:** `date` (natural key)
**Dedup:** Upsert (`ON CONFLICT DO UPDATE` / `ON DUPLICATE KEY UPDATE`)
**Populated by:** `MFPNutritionAdapter` (file), `POST /admin/upload/mfp` (ZIP upload)

Daily nutrition totals aggregated from all meal entries. One row per day.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Calendar date. Primary key. |
| `calories_in` | INTEGER | YES | Total calories consumed across all meals logged. Sourced from CSV "Calories" column, summed per day. |
| `carbs_g` | FLOAT | YES | Total carbohydrates in grams. |
| `fat_g` | FLOAT | YES | Total fat in grams. |
| `protein_g` | FLOAT | YES | Total protein in grams. |
| `sodium_mg` | FLOAT | YES | Total sodium in milligrams. |
| `sugar_g` | FLOAT | YES | Total sugar in grams. |
| `fiber_g` | FLOAT | YES | Total dietary fibre in grams. |
| `cholesterol_mg` | FLOAT | YES | Total cholesterol in milligrams. |
| `logged_meals` | SMALLINT | YES | Number of distinct meal entries logged this day (e.g., 3 = breakfast + lunch + dinner). |
| `source` | VARCHAR(32) | NO | Data source identifier: `"mfp_upload"` (ZIP upload) or `"mfp_file"` (file adapter). Allows distinguishing import method. |

---

### `mfp_food_diary`

**PK:** `id` (autoincrement), indexed on `date`
**Dedup:** Delete date range then re-insert (no natural unique key — same meal name can appear multiple times per day)
**Populated by:** `POST /admin/upload/mfp`

Per-meal diary entries. MFP's Nutrition Summary export provides one row per meal category per day (e.g., "Breakfast", "Lunch", "Dinner", "Snacks"). Note: this is a **meal-level** summary — individual food items within a meal are not available in the MFP bulk export format.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `date` | DATE | NO | Calendar date of the diary entry. Indexed. |
| `meal` | VARCHAR(32) | NO | Meal category (truncated to 32 chars): "Breakfast", "Lunch", "Dinner", "Snacks", etc. |
| `food_name` | VARCHAR(512) | NO | Meal label (same as `meal` in the ZIP upload — MFP Nutrition Summary does not include individual food item names). |
| `calories` | INTEGER | YES | Calories for this meal entry. Rounded from CSV float. |
| `carbs_g` | FLOAT | YES | Carbohydrates in grams for this meal. |
| `fat_g` | FLOAT | YES | Fat in grams for this meal. |
| `protein_g` | FLOAT | YES | Protein in grams for this meal. |
| `sodium_mg` | FLOAT | YES | Sodium in milligrams. Added in schema migration `mfp_upload_v1`. |
| `sugar_g` | FLOAT | YES | Sugar in grams. Added in schema migration `mfp_upload_v1`. |
| `fiber_g` | FLOAT | YES | Dietary fibre in grams. Added in schema migration `mfp_upload_v1`. |
| `cholesterol_mg` | FLOAT | YES | Cholesterol in milligrams. Added in schema migration `mfp_upload_v1`. |

---

### `mfp_measurements`

**PK:** `(date, name)` (composite natural key)
**Dedup:** Upsert
**Populated by:** `POST /admin/upload/mfp`

Custom body measurements from MFP's Measurement-Summary export. Uses an EAV (Entity-Attribute-Value) pattern to store arbitrary measurement types.

**Schema note:** The GarminDB MFP integration previously created an `mfp_measurements` table with a different schema (`id`, `Date`, `BodyFat_Perc`, `Weight_lbs`, `ts`). The `_migrate_mfp_food_diary_columns()` migration detects this schema mismatch (by checking for the absence of the `name` column) and recreates the table with the correct garminview schema.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | DATE | NO | Measurement date. Part of composite PK. |
| `name` | VARCHAR(64) | NO | Measurement name. Part of composite PK. Values: `"body_fat_pct"` (Body Fat % column) or `"weight"` (Weight column). |
| `value` | FLOAT | NO | Measurement value. |
| `unit` | VARCHAR(16) | NO | Measurement unit. `"%"` for body fat, `"lbs"` for weight (stored in original MFP units — lbs). |

---

### `mfp_exercises`

**PK:** `id` (autoincrement), indexed on `date`
**Dedup:** Delete date range then re-insert
**Populated by:** `POST /admin/upload/mfp`

Manual exercise log entries from MFP's Exercise-Summary export. This table is kept **separate from Garmin activity data** (`activities`) to allow direct comparison: MFP exercise logs are self-reported and may differ from Garmin's sensor-measured data. Cross-referencing these two sources reveals discrepancies in calorie estimation or effort perception.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `date` | DATE | NO | Exercise date. Indexed. |
| `exercise_name` | VARCHAR(256) | NO | Name of the exercise as entered in MFP (e.g., "Running", "Bench Press"). Sourced from CSV "Exercise" column. |
| `exercise_type` | VARCHAR(32) | YES | MFP exercise category: `"Cardio"` or `"Strength"`. Sourced from CSV "Type" column. |
| `calories` | FLOAT | YES | Calories burned as estimated by MFP or entered by user. May differ significantly from Garmin's HR-based estimate. Sourced from "Exercise Calories". |
| `duration_min` | FLOAT | YES | Exercise duration in minutes. Sourced from "Exercise Minutes". |
| `sets` | INTEGER | YES | Number of sets (strength exercises only). NULL for cardio. Sourced from "Sets". |
| `reps_per_set` | INTEGER | YES | Repetitions per set (strength only). Sourced from "Reps Per Set". |
| `weight_lbs` | FLOAT | YES | Weight used in lbs (strength only). Stored in original MFP units. Sourced from "Pounds". |
| `steps` | INTEGER | YES | Step count for this exercise (walking/running cardio). Sourced from "Steps". |
| `note` | VARCHAR(512) | YES | Optional user note. Sourced from "Note" column. |

---

## 8. Sync & Schema Tracking

### `sync_log`

**PK:** `id` (autoincrement), indexed on `started_at`

Audit log of every ingestion run. Supports debugging and incremental sync decisions (the orchestrator reads the most recent successful run timestamp to determine the incremental window).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `source` | VARCHAR(32) | YES | Data source: "garmindb_files", "garmin_api", "mfp_files", "mfp_upload". |
| `mode` | VARCHAR(16) | YES | Sync mode: "FULL", "INCREMENTAL", "ANALYSIS_ONLY". |
| `date_start` | DATE | YES | Earliest date in the sync window. ⚠️ Live column is `date_start`, not `start_date`. |
| `date_end` | DATE | YES | Latest date in the sync window. ⚠️ Live column is `date_end`, not `end_date`. |
| `records_upserted` | INTEGER | YES | Number of rows written across all tables. ⚠️ Live column is `records_upserted`, not `row_count`. |
| `status` | VARCHAR(16) | YES | "RUNNING", "SUCCESS", "FAILED". |
| `error_message` | TEXT | YES | Exception message if status = "FAILED". |
| `started_at` | DATETIME | YES | UTC timestamp when the sync began. Indexed. |
| `finished_at` | DATETIME | YES | UTC timestamp when the sync completed or failed. |

---

### `data_provenance`

**PK:** `id` (autoincrement)

Fine-grained source tracking per table row.

⚠️ **Live column names differ from original model.**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `table_name` | VARCHAR(64) | YES | Target table the data was written to. |
| `record_id` | VARCHAR(128) | YES | Serialised PK of the specific row (e.g., "2024-01-15" for a date PK). ⚠️ Live column is `record_id`, not `record_key`. |
| `source` | VARCHAR(32) | YES | Data source identifier. |
| `imported_at` | DATETIME | YES | When provenance was recorded. ⚠️ Live column is `imported_at`, not `recorded_at`. |

---

### `schema_version`

**PK:** `id` (autoincrement)

Migration history tracking. When `_migrate_mfp_food_diary_columns()` (or similar lazy migration helpers) add columns or create tables, they insert a row here recording what changed and when.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `version` | VARCHAR(64) | NO | Migration identifier (e.g., `"mfp_upload_v1"`). |
| `description` | TEXT | YES | Human-readable description of what was changed (e.g., `"MFP upload migration: added sodium_mg, sugar_g, fiber_g, cholesterol_mg"`). |
| `applied_at` | DATETIME | YES | UTC timestamp when the migration ran. |
| `applied_by` | VARCHAR(16) | YES | Component that triggered the migration (e.g., `"mfp_upload"`, `"sync"`). Max 16 chars. |

---

## 9. Configuration

### `user_profile`

**PK:** `id` (always 1 — singleton row)

The single user's biological profile used in all calculations. Created once; updated via the Admin UI.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Always 1. Primary key. |
| `name` | VARCHAR(64) | YES | User's display name. |
| `birth_date` | DATE | YES | Used to calculate age for max HR formulas and fitness age. |
| `sex` | VARCHAR(8) | YES | "MALE" or "FEMALE". Used in Gulati max HR formula and BMR calculations. |
| `height_cm` | FLOAT | YES | Height in centimetres. Used in BMI and FFMI calculations. |
| `weight_kg` | FLOAT | YES | Reference body weight. Used as fallback when no recent scale data. |
| `max_hr_override` | INTEGER | YES | User-specified maximum HR. Takes precedence over all formula-based estimates. Set this if you know your actual max HR from a field test. |
| `resting_hr_override` | INTEGER | YES | User-specified resting HR. Takes precedence over device-measured values in TRIMP and zone calculations. |
| `preferred_units` | VARCHAR(8) | YES | "METRIC" or "IMPERIAL". Affects display in the frontend (stored values always metric). |

---

### `app_config`

**PK:** `key`

Key-value store for application settings. Managed via the Admin UI. Allows runtime tuning of analysis parameters without code changes.

⚠️ Live DB uses `VARCHAR(128)` for `key` (not 64), and has an additional `updated_at` column.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `key` | VARCHAR(128) | NO | Setting name. Primary key (e.g., `"trimp_tau_atl"`, `"sleep_target_min"`). ⚠️ Live DB uses VARCHAR(128), not VARCHAR(64). |
| `value` | TEXT | YES | Setting value serialised as a string. |
| `data_type` | VARCHAR(16) | YES | Type hint for deserialisation: "int", "float", "bool", "str", "json". |
| `category` | VARCHAR(32) | YES | Grouping for Admin UI display (e.g., "training", "sleep", "analysis"). |
| `description` | TEXT | YES | Human-readable explanation of what the setting controls. |
| `updated_at` | DATETIME | YES | Timestamp of last update to this setting. ⚠️ Present in live DB; absent from original model. |

---

### `sync_schedule`

**PK:** `id` (autoincrement)

APScheduler job configuration. Rows are loaded at app startup and used to register scheduled jobs. Updates via the Admin API hot-reload the scheduler without restart.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `name` | VARCHAR(64) | YES | Human-readable schedule name (e.g., "Nightly GarminDB sync"). |
| `source` | VARCHAR(32) | YES | Data source this schedule syncs: "garmindb_files", "garmin_api", "analysis_only". |
| `cron_expression` | VARCHAR(64) | YES | Cron string (e.g., `"0 3 * * *"` = 3:00 AM daily). |
| `mode` | VARCHAR(16) | YES | "FULL", "INCREMENTAL", or "ANALYSIS_ONLY". |
| `enabled` | BOOLEAN | NO | Whether the schedule is active. |
| `last_run_at` | DATETIME | YES | Timestamp of the last execution. |
| `next_run_at` | DATETIME | YES | Scheduled next execution time. |

---

### `goal_benchmarks`

**PK:** `id` (autoincrement)

Reference targets for analysis thresholds (e.g., what counts as "good" VO2max for the user's age/sex).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `metric` | VARCHAR(64) | YES | Metric name. |
| `target_value` | FLOAT | YES | Target value. |
| `source` | VARCHAR(32) | YES | Where the target comes from: "user_set", "age_norm", "garmin_default". |
| `notes` | TEXT | YES | Context for this benchmark. |

---

### `notification_config`

**PK:** `id` (autoincrement)

Future-use notification rules (not yet active).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | INTEGER | NO | Autoincrement primary key. |
| `event_type` | VARCHAR(64) | YES | Event that triggers the notification (e.g., "HIGH_INJURY_RISK", "GOAL_ACHIEVED"). |
| `channel` | VARCHAR(32) | YES | Delivery channel: "email", "webhook", "push". |
| `enabled` | BOOLEAN | NO | Whether this notification is active. |
| `config_json` | TEXT | YES | Channel-specific configuration (endpoint URL, email address, etc.) as JSON. |

---

## Conventions

### Primary Key Patterns

| Pattern | Used for | Example tables |
|---|---|---|
| **Natural date PK** | One row per calendar day | `daily_summary`, `sleep`, `mfp_daily_nutrition` |
| **Composite natural PK** | One row per (date × dimension) | `mfp_measurements (date, name)`, `activity_hr_zones (activity_id, zone)` |
| **Garmin ID (BIGINT)** | Garmin Connect activities | `activities` |
| **Timestamp PK** | Sub-day monitoring data | `monitoring_heart_rate`, `stress` |
| **Autoincrement** | Logs, events, multi-row-per-day | `sleep_events`, `mfp_food_diary`, `sync_log` |

### Naming Conventions

- All column names: `snake_case`
- Units are encoded in column names: `_kg`, `_m`, `_min`, `_sec`, `_pct`, `_bpm`, `_w` (watts), `_ms` (milliseconds)
- Nullable columns default to `NULL` (no sentinel values — Garmin's `-1` sentinel is converted to NULL on ingestion)
- Boolean columns use SQLAlchemy `Boolean` type (MariaDB `TINYINT(1)`)

---

## Deduplication Strategy

Different tables use different strategies depending on their primary key structure:

| Strategy | Tables | Description |
|---|---|---|
| **Natural-key upsert** | `daily_summary`, `sleep`, `mfp_daily_nutrition`, `mfp_measurements`, all supplemental tables | `ON CONFLICT DO UPDATE` (SQLite) / `ON DUPLICATE KEY UPDATE` (MySQL). Overwrites existing rows on re-sync. |
| **Delete-range + re-insert** | `sleep_events`, `mfp_food_diary`, `mfp_exercises` | For autoincrement PK tables with no natural unique key per row: delete all rows where `date BETWEEN min_date AND max_date`, then bulk insert. Prevents duplicates without needing a unique index. |
| **Computed tables** | `daily_derived`, `max_hr_aging_year` | Always upserted; values are recomputed from source tables on every analysis run. |

---

## Dialect Notes

The codebase runs against both **SQLite** (development, testing) and **MariaDB/MySQL** (production). Dialect differences are handled explicitly:

| Feature | SQLite | MariaDB |
|---|---|---|
| Upsert | `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE` | `INSERT ... ON DUPLICATE KEY UPDATE` |
| Insert dialect import | `sqlalchemy.dialects.sqlite.insert` | `sqlalchemy.dialects.mysql.insert` |
| Detection | `session.bind.dialect.name == "sqlite"` | `session.bind.dialect.name == "mysql"` |
| FIT timestamp storage | Strings accepted | Strict datetime types required |
| Boolean | Native BOOLEAN | TINYINT(1) |

All adapters and analysis code branches on `dialect.name` for upserts. Never hardcode `sqlite` or `mysql` dialect imports at module level — import inside the branch.

---

## Alembic Version Table

### `alembic_version`

**Managed by:** Alembic migrations (`alembic/`)
**Not documented as an application table** — present in the live DB solely as Alembic's migration tracking mechanism.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `version_num` | VARCHAR(32) | NO | Current Alembic migration head revision ID. |

---

## Legacy / External Tables

The following tables exist in the live MariaDB database but are **not owned by garminview**. They were created by prior GarminDB or experimental scripts and are not used by any garminview code path. They should not be queried by garminview and may be dropped when no longer needed.

| Table | Origin | Notes |
|---|---|---|
| `attendance` | Unknown legacy script | No garminview model. |
| `garmin_activities` | GarminDB staging remnant | Superseded by garminview's `activities` table. |
| `garmin_test` | GarminDB test table | Scratch table; can be dropped. |
| `justdates` | Unknown legacy script | Scratch/test table. |
| `justdatetimes` | Unknown legacy script | Scratch/test table. |
| `timer` | Unknown legacy script | Scratch/test table. |
| `mfp_exercise` | GarminDB MFP integration | Old schema. Replaced by garminview's `mfp_exercises`. |
| `mfp_exercise_test` | GarminDB test table | Scratch/test table. |
| `mfp_nutrition` | GarminDB MFP integration | Old schema. Replaced by garminview's `mfp_daily_nutrition`. |
| `mfp_nutrition_test` | GarminDB test table | Scratch/test table. |
| `mfp_measurements_test` | GarminDB test table | Scratch/test table. |

**Cleanup command (run when safe):**
```sql
DROP TABLE IF EXISTS attendance, garmin_activities, garmin_test, justdates,
    justdatetimes, timer, mfp_exercise, mfp_exercise_test, mfp_nutrition,
    mfp_nutrition_test, mfp_measurements_test;
```
