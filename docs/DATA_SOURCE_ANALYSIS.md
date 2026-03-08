# Data Source Analysis — python-garminconnect & GarminDB

> **Generated**: 2026-03-07
> **Purpose**: Reference document capturing the full capabilities of both upstream data projects for garminview development.

---




## Table of Contents

1. [python-garminconnect — API Reference](#1-python-garminconnect--api-reference)
2. [GarminDB — Database & Pipeline Reference](#2-garmindb--database--pipeline-reference)
3. [How They Complement Each Other](#3-how-they-complement-each-other)

---



## 1. python-garminconnect — API Reference

**Location**: `/home/jcz/Github/python-garminconnect`
**Role**: Real-time Garmin Connect API wrapper
**Total API Methods**: 105+ endpoints across 12 categories
**Authentication**: OAuth 2.0 via Garth library (token stored at `~/.garminconnect`, ~1 year lifetime, MFA support)

### 1.1 User & Profile (4 methods)

| Method | Description |
|--------|-------------|
| `get_full_name()` | User's full name |
| `get_unit_system()` | Measurement system (metric/imperial) |
| `get_user_profile()` | Complete user settings |
| `get_userprofile_settings()` | Detailed profile settings |

### 1.2 Daily Health & Activity (9 methods)

| Method | Description |
|--------|-------------|
| `get_stats(cdate)` / `get_user_summary(cdate)` | Daily activity summary |
| `get_stats_and_body(cdate)` | Combined activity + body composition |
| `get_steps_data(cdate)` | Hourly step breakdown |
| `get_heart_rates(cdate)` | Daily heart rate data |
| `get_resting_heart_rate(cdate)` | Resting heart rate |
| `get_sleep_data(cdate)` | Sleep duration & stages (REM, light, deep, awake) |
| `get_all_day_stress(cdate)` | Daily stress levels |
| `get_lifestyle_logging_data(cdate)` | Manual wellness logging |

### 1.3 Advanced Health Metrics (11 methods)

| Method | Description |
|--------|-------------|
| `get_training_readiness(cdate)` | Readiness score (1–100) |
| `get_morning_training_readiness(cdate)` | Morning readiness snapshot |
| `get_training_status(cdate)` | Qualitative status (Productive, Detraining, etc.) |
| `get_respiration_data(cdate)` | Respiratory rate |
| `get_spo2_data(cdate)` | Blood oxygen levels (SpO2) |
| `get_max_metrics(cdate)` | VO2 Max, Fitness Age |
| `get_hrv_data(cdate)` | Heart Rate Variability |
| `get_fitnessage_data(cdate)` | Fitness age estimation |
| `get_stress_data(cdate)` | Detailed stress metrics |
| `get_lactate_threshold(latest, start_date, end_date, aggregation)` | Running lactate threshold (speed, HR, power) |
| `get_intensity_minutes_data(cdate)` | Moderate/vigorous intensity minutes |

### 1.4 Historical Data & Trends (9 methods)

| Method | Description |
|--------|-------------|
| `get_daily_steps(start, end)` | Daily steps over date range |
| `get_body_battery(startdate, enddate)` | Daily body battery levels |
| `get_floors(cdate)` | Floors climbed |
| `get_blood_pressure(startdate, enddate)` | Blood pressure history |
| `get_progress_summary_between_dates(startdate, enddate, metric, groupbyactivities)` | Aggregated metrics by activity type |
| `get_body_battery_events(cdate)` | Sleep/activity events affecting battery |
| `get_weekly_steps(end, weeks=52)` | Weekly step aggregates (52 weeks default) |
| `get_weekly_stress(end, weeks=52)` | Weekly stress aggregates |
| `get_weekly_intensity_minutes(start, end)` | Weekly intensity aggregates |

**Bulk Query Note**: Date ranges >28 days are auto-chunked into 28-day requests.

### 1.5 Activities & Workouts (28 methods)

#### Activity Retrieval

| Method | Description |
|--------|-------------|
| `get_activities(start, limit, activitytype)` | Recent activities (paginated) |
| `get_last_activity()` | Most recent activity |
| `get_activities_fordate(fordate)` | Activities on specific date |
| `get_activities_by_date(startdate, enddate, activitytype, sortorder)` | Date range (auto-paginated) |
| `get_activity(activity_id)` | Single activity summary |
| `get_activity_details(activity_id, maxchart, maxpoly)` | Full details with charts/maps |
| `get_activity_exercise_sets(activity_id)` | Strength training exercises |
| `get_activity_gear(activity_id)` | Gear used |
| `get_activity_splits(activity_id)` | Lap/pace splits |
| `get_activity_typed_splits(activity_id)` | Sport-specific splits |
| `get_activity_split_summaries(activity_id)` | Split summaries |
| `get_activity_weather(activity_id)` | Weather during activity |
| `get_activity_hr_in_timezones(activity_id)` | HR zones breakdown |
| `get_activity_power_in_timezones(activity_id)` | Power zones breakdown |
| `download_activity(activity_id, dl_fmt)` | Download as FIT/TCX/GPX/KML/CSV |
| `count_activities()` | Total activity count |
| `get_activity_types()` | Supported activity types |

#### Activity Management

| Method | Description |
|--------|-------------|
| `upload_activity(activity_path)` | Upload .FIT/.GPX/.TCX file |
| `delete_activity(activity_id)` | Delete activity |
| `set_activity_name(activity_id, title)` | Rename activity |
| `set_activity_type(activity_id, type_id, type_key, parent_type_id)` | Change activity type |
| `create_manual_activity(...)` | Create manual private activity |

#### Workouts

| Method | Description |
|--------|-------------|
| `get_workouts(start, limit)` | Scheduled workouts |
| `get_workout_by_id(workout_id)` | Specific workout |
| `download_workout(workout_id)` | Download as .FIT |
| `upload_workout(workout_json)` | Upload JSON workout |
| `get_scheduled_workout_by_id(scheduled_workout_id)` | Scheduled workout |
| `upload_running_workout(workout)` | Upload typed RunningWorkout (Pydantic) |
| `upload_cycling_workout(workout)` | Upload typed CyclingWorkout |
| `upload_swimming_workout(workout)` | Upload typed SwimmingWorkout |
| `upload_walking_workout(workout)` | Upload typed WalkingWorkout |
| `upload_hiking_workout(workout)` | Upload typed HikingWorkout |

#### Performance

| Method | Description |
|--------|-------------|
| `get_cycling_ftp()` | Functional Threshold Power |

### 1.6 Body Composition & Weight (8 methods)

| Method | Description |
|--------|-------------|
| `get_body_composition(startdate, enddate)` | Weight, fat %, hydration %, muscle mass, bone mass, BMI, metabolic age |
| `get_weigh_ins(startdate, enddate)` | Weigh-in history |
| `get_daily_weigh_ins(cdate)` | Daily weigh-ins |
| `add_weigh_in(weight, unitKey, timestamp)` | Log weight (kg/lbs) |
| `add_weigh_in_with_timestamps(weight, unitKey, dateTimestamp, gmtTimestamp)` | Log with explicit timestamps |
| `add_body_composition(...)` | Log full body composition (16 parameters) |
| `delete_weigh_ins(cdate, delete_all)` | Delete weigh-in(s) |
| `delete_weigh_in(weight_pk, cdate)` | Delete specific entry |

### 1.7 Goals & Achievements (15 methods)

| Method | Description |
|--------|-------------|
| `get_active_goals(start, limit)` | Active goals |
| `get_future_goals(start, limit)` | Upcoming goals |
| `get_past_goals(start, limit)` | Completed goals |
| `get_earned_badges()` | Earned badges |
| `get_available_badges()` | Unearned badges |
| `get_in_progress_badges()` | Badge progress tracking |
| `get_badge_challenges(start, limit)` | Completed challenges |
| `get_available_badge_challenges(start, limit)` | Available challenges |
| `get_non_completed_badge_challenges(start, limit)` | In-progress challenges |
| `get_adhoc_challenges(start, limit)` | Ad-hoc challenges |
| `get_inprogress_virtual_challenges(start, limit)` | Virtual challenge progress |
| `get_personal_records()` | User's PRs (distances, times) |
| `get_race_predictions(startdate, enddate, _type)` | 5K/10K/half/full marathon predictions |
| `get_hill_score(startdate, enddate)` | Hill score rating |
| `get_endurance_score(startdate, enddate)` | Endurance score |

### 1.8 Device & Technical (7 methods)

| Method | Description |
|--------|-------------|
| `get_devices()` | All connected devices |
| `get_device_settings(device_id)` | Device-specific settings |
| `get_device_alarms()` | Active alarms |
| `get_device_last_used()` | Last used device |
| `get_primary_training_device()` | Primary training device |
| `get_device_solar_data(device_id, startdate, enddate)` | Solar charging data |
| `request_reload(cdate)` | Request data refresh/reload |

### 1.9 Gear & Equipment (7 methods)

| Method | Description |
|--------|-------------|
| `get_gear(userProfileNumber)` | User gear list |
| `get_gear_stats(gearUUID)` | Gear usage statistics |
| `get_gear_defaults(userProfileNumber)` | Default gear by activity type |
| `get_gear_activities(gearUUID, limit)` | Activities using gear |
| `set_gear_default(activityType, gearUUID, defaultGear)` | Set gear as default |
| `add_gear_to_activity(gearUUID, activity_id)` | Associate gear with activity |
| `remove_gear_from_activity(gearUUID, activity_id)` | Unassociate gear |

### 1.10 Hydration & Wellness (9 methods)

| Method | Description |
|--------|-------------|
| `get_hydration_data(cdate)` | Daily hydration tracking |
| `add_hydration_data(value_in_ml, timestamp, cdate)` | Log water intake |
| `set_blood_pressure(systolic, diastolic, pulse, timestamp, notes)` | Log blood pressure |
| `get_blood_pressure(startdate, enddate)` | Blood pressure history |
| `delete_blood_pressure(version, cdate)` | Delete BP entry |
| `get_all_day_events(cdate)` | Auto-detected activities |
| `get_menstrual_data_for_date(fordate)` | Menstrual cycle data |
| `get_menstrual_calendar_data(startdate, enddate)` | Cycle calendar |
| `get_pregnancy_summary()` | Pregnancy snapshot |

### 1.11 System & Export (4 methods)

| Method | Description |
|--------|-------------|
| `query_garmin_graphql(query)` | Execute GraphQL queries (advanced) |
| `logout()` | Logout (deprecated; use token deletion) |
| Report generation via demo.py | JSON and HTML health reports |

### 1.12 Training Plans (3 methods)

| Method | Description |
|--------|-------------|
| `get_training_plans()` | Available training plans |
| `get_training_plan_by_id(plan_id)` | Plan details |
| `get_adaptive_training_plan_by_id(plan_id)` | Adaptive plan details |

### 1.13 Pagination & Rate Limits

- Default limit: 20 items per request
- Max activity limit: 1000 per request
- Auto-chunking: date ranges >28 days split automatically
- Pagination params: `start` (offset) + `limit` (count)
- Date range limit: 28 days per request (single-day queries use `cdate` format YYYY-MM-DD)
- Weekly queries: up to 52 weeks
- Lactate threshold: 1-year max range
- Rate limit: 429 HTTP status → `GarminConnectTooManyRequestsError`
- Token refresh handled automatically by Garth

### 1.14 Download/Export Formats

| Direction | Formats |
|-----------|---------|
| Activity download | FIT, TCX, GPX, KML, CSV |
| Activity upload | FIT, GPX, TCX |
| Workout download | FIT |
| Workout upload | JSON (Pydantic models) |

### 1.15 Exception Types

| Exception | Trigger |
|-----------|---------|
| `GarminConnectConnectionError` | HTTP/connection failures |
| `GarminConnectAuthenticationError` | Login errors (401) |
| `GarminConnectTooManyRequestsError` | Rate limit exceeded (429) |
| `GarminConnectInvalidFileFormatError` | Invalid file on upload |

---

## 2. GarminDB — Database & Pipeline Reference

**Location**: `/home/jcz/Github/GarminDB`
**Role**: End-to-end download pipeline → FIT/JSON parsing → SQLite storage → summary aggregation
**Architecture**: 5 SQLite databases, 30+ tables, plugin-extensible FIT parsing

### 2.1 Database Architecture

#### 2.1.1 garmin.db — Core Device & User Data

| Table | Key Fields | Description |
|-------|-----------|-------------|
| **Attributes** | key-value pairs | Metadata (measurement system, etc.) |
| **Device** | serial_number, manufacturer, product, hardware_version, software_version, battery_status | Garmin device records |
| **DeviceInfo** | battery_voltage, cumulative_operating_time | Device info from FIT files |
| **File** | type, device association | FIT file registry |
| **Weight** | day (PK), weight (Float) | Daily weight measurements |
| **Stress** | timestamp, stress_level | Daily stress readings |
| **Sleep** | day (PK), start, end, total_sleep, deep_sleep, light_sleep, rem_sleep, awake, avg_spo2, avg_rr, avg_stress, score, qualifier | Sleep sessions with stages |
| **SleepEvents** | Event type (deep/light/rem/awake) + duration | Individual sleep stage events |
| **RestingHeartRate** | day (PK), resting_heart_rate | Daily RHR |
| **DailySummary** | 50+ fields | Consolidated daily metrics (HR, steps, floors, distance, calories, intensity, hydration, SpO2, respiration, body battery, stress) |

#### 2.1.2 garmin_monitoring.db — Minute-Level Health Metrics

| Table | Key Fields | Description |
|-------|-----------|-------------|
| **MonitoringInfo** | activity_types, metabolic_rate | File-level metadata |
| **MonitoringHeartRate** | timestamp (PK), heart_rate | Per-minute heart rate |
| **MonitoringIntensity** | timestamp, moderate_activity_time, vigorous_activity_time | Daily cardio minutes |
| **MonitoringClimb** | timestamp, ascent, descent, cum_ascent, cum_descent | Elevation data |
| **Monitoring** | timestamp, activity_type, intensity, duration, distance, active_calories, steps, strokes, cycles | Aggregated activity data |
| **MonitoringRespirationRate** | timestamp, rr | Breaths per minute |
| **MonitoringPulseOx** | timestamp, pulse_ox | Blood oxygen saturation |

#### 2.1.3 garmin_activities.db — Detailed Activity Records

**ActivitiesCommon** (shared fields for Activities and Laps):
- Timing: `start_time, stop_time, elapsed_time, moving_time`
- Performance: `distance, cycles, avg_hr, max_hr, avg_rr, max_rr, calories`
- Cadence: `avg_cadence, max_cadence`
- Speed: `avg_speed, max_speed`
- Elevation: `ascent, descent`
- Temperature: `min_temperature, max_temperature, avg_temperature`
- GPS: `start_lat, start_long, stop_lat, stop_long`
- HR Zones: 5 zones (threshold HR + time in zone)

| Table | Key Fields | Description |
|-------|-----------|-------------|
| **Activities** | activity_id (PK), name, description, type, sport, sub_sport, course_id, laps, device_serial_number, self_eval_feel, self_eval_effort, training_load, training_effect, anaerobic_training_effect | Activity records |
| **ActivityLaps** | activity_id + lap (PK) | Per-lap breakdown |
| **ActivitySplits** | Climbing/sport-specific splits | Split data |
| **ActivityRecords** | activity_id + record (PK), timestamp, position_lat, position_long, distance, cadence, altitude, hr, rr, speed, temperature | Point-in-time data |
| **ActivitiesDevices** | activity_id, device_id | Activity-device mapping |
| **StepsActivities** | steps, pace (avg/moving/max), steps_per_minute, step_length, vertical_oscillation, vertical_ratio, ground_contact_time, stance_time_percent, vo2_max | Running/walking-specific metrics |

**Dynamic Views**: walking_activities_view, running_activities_view, hiking_activities_view (auto-created by sport + course)

#### 2.1.4 garmin_summary.db — Garmin-Specific Summaries

| Table | Key Fields | Description |
|-------|-----------|-------------|
| **DaysSummary** | day (PK) | Daily aggregates |
| **WeeksSummary** | first_day (PK) | Weekly aggregates |
| **MonthsSummary** | first_day (PK) | Monthly aggregates |
| **YearsSummary** | first_day (PK) | Yearly aggregates |
| **IntensityHR** | timestamp + intensity (PK) | HR values per intensity level |

#### 2.1.5 summary.db — Cross-Trainer Aggregates

Same structure as garmin_summary.db (Days/Weeks/Months/Years Summary).

**SummaryBase fields**: HR averages, weight, intensity time, steps, floors, sleep (all stages), stress, calories, activities, hydration, SpO2, respiration, body battery.

### 2.2 Data Pipeline

```
DOWNLOAD PHASE (download.py)
─────────────────────────────
Garmin Connect (via Garth API) → local files:
  • Activities: JSON summary + details
  • Daily summaries: JSON (daily monitoring endpoint)
  • Sleep data: JSON
  • Weight data: JSON
  • Resting heart rate: JSON
  • Hydration: JSON
  • Monitoring files: FIT format (daily HR/steps/intensity)
  • Settings/Profile: FIT files
  • All files retained for DB regeneration without re-download

         │
         ▼

PARSE/IMPORT PHASE
──────────────────
  1. Settings FIT → GarminUserSettings, Attributes
  2. Weight files → Weight table
  3. Sleep files → Sleep + SleepEvents tables
  4. RHR files → RestingHeartRate table
  5. Daily summaries → DailySummary table (50+ metrics)
  6. Monitoring FIT files → MonitoringHeartRate, Intensity,
     Climb, Monitoring, RespirationRate, PulseOx tables
  7. Activity JSON → Activities table
  8. Activity FIT files → ActivityRecords, ActivityLaps,
     ActivitySplits, StepsActivities
  9. Hydration → DailySummary.hydration_* fields
  • Plugins can extend FIT parsing for custom fields

         │
         ▼

ANALYSIS PHASE (analyze.py)
───────────────────────────
  For each day:
    • Aggregate from raw tables:
      - RestingHeartRate → rhr_avg
      - Stress → stress_avg
      - MonitoringIntensity → intensity time
      - MonitoringClimb → floors
      - Monitoring → steps, active_calories
      - MonitoringHeartRate → hr_avg/min/max
      - IntensityHR → inactive_hr metrics
      - Weight → weight_avg/min/max
      - Sleep → sleep_avg, stages
    • Store → DaysSummary (garmin_summary.db) + summary.db

  For each week/month/year:
    • Aggregate daily stats
    • Store → WeeksSummary / MonthsSummary / YearsSummary

  • Create dynamic views for courses, sports
```

### 2.3 CLI Commands

```bash
garmindb_cli.py [options]

# Modes
  -d, --download              Download from Garmin Connect
  -c, --copy                  Copy from USB-mounted Garmin device
  -i, --import                Parse files into DB
  --analyze                   Generate summaries
  -b, --backup                Backup database files
  --rebuild_db                Delete + regenerate DBs from files
  --delete_db                 Delete DB files for selected stats
  -e, --export-activity ID    Export activity to TCX
  --basecamp-activity ID      Open in Garmin BaseCamp
  -g, --google-earth-activity ID  Open in Google Earth

# Statistics selection
  -A, --all                   All enabled stats
  -a, --activities            Activities only
  -m, --monitoring            Daily monitoring
  -r, --rhr                   Resting heart rate
  -s, --sleep                 Sleep data
  -w, --weight                Weight data

# Modifiers
  -l, --latest                Recent data only
  -o, --overwrite             Overwrite existing files
  -t, --trace LEVEL           Debug level (0-n)
  -f, --config PATH           Config file path

# Common workflows
  garmindb_cli.py --all --download --import --analyze           # Full from scratch
  garmindb_cli.py --all --download --import --analyze --latest  # Incremental update
  garmindb_cli.py --rebuild_db                                  # Regenerate DBs
```

### 2.4 Configuration

File: `~/.GarminDb/GarminConnectConfig.json`

```json
{
  "credentials": {
    "user": "garmin_email@example.com",
    "password": "your_password"
  },
  "data": {
    "weight_start_date": "12/31/2019",
    "sleep_start_date": "12/31/2019",
    "rhr_start_date": "12/31/2019",
    "monitoring_start_date": "12/31/2019",
    "download_latest_activities": 25,
    "download_all_activities": 1000
  },
  "directories": {
    "relative_to_home": true,
    "base_dir": "HealthData"
  },
  "enabled_stats": {
    "monitoring": true,
    "steps": true,
    "itime": true,
    "sleep": true,
    "rhr": true,
    "weight": true,
    "activities": true
  },
  "settings": {
    "metric": false,
    "default_display_activities": ["walking", "running", "cycling"]
  }
}
```

### 2.5 Existing Analysis & Reporting

#### Jupyter Notebooks (`/Jupyter/`)

| Notebook | Purpose |
|----------|---------|
| `daily.ipynb` | Daily metrics dashboard |
| `daily_trends.ipynb` | Trends over time |
| `activities.ipynb` | Activity statistics |
| `activities_dashboard.ipynb` | Activity overview |
| `activity.ipynb` | Single activity analysis |
| `monitoring.ipynb` | Health monitoring insights |
| `month.ipynb` | Monthly summaries |
| `summary.ipynb` | Health summary |
| `checkup.ipynb` | Health checkup report |
| `course.ipynb` | Course/route analysis |
| `garmin.ipynb` | General health report |

#### Export Capabilities

- Activities to TCX (Garmin TCX format)
- Export to BaseCamp
- Export to Google Earth (with GPS tracks)

#### Database Views

- Auto-created for activities by sport (walking, running, hiking views)
- Course-specific views for recurring routes
- Summary views (days/weeks/months/years) with computed percentages

### 2.6 Schema Versioning

Each table has `table_version` and `view_version`. On upgrade, GarminDB detects version mismatches and prompts `--rebuild_db` to regenerate from retained raw files (no re-download required).

### 2.7 Plugin Architecture

- `plugin_manager.py` manages plugins
- `PluginBase` provides base classes for activity/monitoring FIT plugins
- Custom plugins can extend FIT field parsing

### 2.8 Key Modules

| Module | Purpose |
|--------|---------|
| `download.py` | Authenticates (Garth), fetches JSON/FIT data |
| `analyze.py` | Aggregates raw metrics into summaries |
| `garmindb/garmin_db.py` | ORM: Device, File, Weight, Sleep, Stress, RHR, DailySummary |
| `garmindb/monitoring_db.py` | ORM: MonitoringHeartRate, Intensity, Climb, Monitoring, RespirationRate, PulseOx |
| `garmindb/activities_db.py` | ORM: Activities, ActivityLaps, ActivityRecords, ActivitySplits, StepsActivities |
| `garmindb/garmin_summary_db.py` | ORM: DaysSummary, WeeksSummary, MonthsSummary, YearsSummary, IntensityHR |
| `summarydb/summary_db.py` | Cross-trainer aggregates |
| `import_monitoring.py` | File processors for JSON/FIT parsing |
| `garmin_connect_config_manager.py` | Config management, file paths |
| `plugin_manager.py` | Plugin architecture for custom FIT fields |

---

## 3. How They Complement Each Other

| Aspect | python-garminconnect | GarminDB |
|--------|---------------------|----------|
| **Role** | Low-level API wrapper | Full download/storage/analysis pipeline |
| **Auth dependency** | Uses Garth directly | Uses Garth directly |
| **Scope** | Individual API calls | End-to-end data management |
| **Storage** | In-memory (returns JSON) | Persists to SQLite |
| **History** | No data retention | Full historical archive |
| **Analysis** | None built-in | Aggregations, trends, Jupyter |
| **Data formats** | JSON from Garmin endpoints | JSON + FIT + TCX + SQLite |
| **Pagination** | Manual (start + limit) | Auto-pagination built in |
| **Rate handling** | Raises exception | Raises exception |

### Usage Strategy for garminview

- **GarminDB** handles bulk historical backfill and ongoing daily sync (download → import → analyze)
- **python-garminconnect** fills gaps that GarminDB doesn't download:
  - HRV data (`get_hrv_data`)
  - Training readiness (`get_training_readiness`)
  - Training status (`get_training_status`)
  - VO2 Max / fitness age (`get_max_metrics`, `get_fitnessage_data`)
  - Race predictions (`get_race_predictions`)
  - Lactate threshold (`get_lactate_threshold`)
  - Hill score (`get_hill_score`)
  - Endurance score (`get_endurance_score`)
  - Body battery events (`get_body_battery_events`)
  - Personal records (`get_personal_records`)
  - Gear stats (`get_gear_stats`)
  - Advanced body composition fields (muscle mass, bone mass, hydration %, visceral fat, physique rating, metabolic age)
  - Blood pressure (`get_blood_pressure`)
- **garminview** adds the derived metrics engine, composite scores, and visualization layer on top of both
