# GarminView — Requirements Document

> **Version**: 1.0 — 2026-03-07
> **Purpose**: Download a comprehensive historical body of fitness data from Garmin Connect, keep it current with frequent updates, and produce a rich statistical and metric-driven view of fitness, health, and body composition.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Data Harvesting — Garmin Connect](#2-data-harvesting--garmin-connect)
3. [Multi-Source Data Integration](#3-multi-source-data-integration)
4. [Data Storage](#4-data-storage)
5. [Health & Body Metrics — Reports & Analysis](#5-health--body-metrics--reports--analysis)
6. [Activity & Training Metrics — Reports & Analysis](#6-activity--training-metrics--reports--analysis)
7. [Derived & Calculated Metrics](#7-derived--calculated-metrics)
8. [Intelligent Assessments & Goal Tracking](#8-intelligent-assessments--goal-tracking)
9. [Cross-Source Correlation & Data Quality](#9-cross-source-correlation--data-quality)
10. [Web Application — Vue.js Frontend](#10-web-application--vuejs-frontend)
11. [Dashboards & Visualization](#11-dashboards--visualization)
12. [Marimo Notebooks — Ad-Hoc Exploration](#12-marimo-notebooks--ad-hoc-exploration)
13. [Export & Sharing](#13-export--sharing)
14. [Scheduling & Automation](#14-scheduling--automation)
15. [Non-Functional Requirements](#15-non-functional-requirements)

---


## Mission: 

This will be an application to fetch data from Garmin Connect, store it in a local database, and analyze it to generate insights and visualizations. it will provide a web view and update itself periodically with new data from Garmin Connect and eventually other data sources like 1. Actalog, 2. Apple Health, and 3. Myfitnesspal. It will calculate derived metrics, composite scores, and visualizations. It will also contain new logic based on authoritative sources to assess the metrics and present assessments about trends and targets and based on goals for health and fitness. It will correlate information from across the data sources and also present findings about correlations and patterns, and possible data quality issues. It will also allow users to export their data and insights in various formats (PDF, CSV, JSON) and share them with others. The project will be built using Python for the backend, and SQlite or MariaDB for the database. The frontend will be developed using Vue.js for a responsive and interactive user experience.

This development will also create one or more marimo notebooks to explore the data and create visualizations and insights in a more ad-hoc way, which can then be formalized into the web view dashboards and reports.

## 1. System Architecture

### 1.1 Components

| Component | Role |
|-----------|------|
| **python-garminconnect** | Real-time Garmin Connect API wrapper (105+ endpoints) |
| **GarminDB** | Bulk download pipeline → FIT/JSON parsing → SQLite storage → summary aggregation |
| **garminview backend** (Python) | Orchestration, data ingestion from all sources, derived metrics engine, assessment logic, REST API |
| **garminview frontend** (Vue.js) | Responsive web UI — dashboards, charts, reports, goal management, data export |
| **Marimo notebooks** | Ad-hoc data exploration, prototype visualizations, analysis experimentation |

### 1.2 Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+ |
| **Frontend** | Vue.js (responsive, interactive SPA) |
| **Database** | SQLite (default, single-user) or MariaDB (optional, multi-user / higher volume) |
| **API** | REST API (Python backend → Vue.js frontend) |
| **Notebooks** | Marimo (ad-hoc exploration, prototyping) |
| **Scheduling** | cron / systemd timer for periodic sync |

### 1.3 Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                       DATA SOURCES                               │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│ Garmin       │ Apple Health │ MyFitnessPal │ Actalog            │
│ Connect API  │ Export       │ API/Export   │ API/Export         │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────────┘
       │              │              │                │
       ▼              ▼              ▼                ▼
┌──────────────────────────────────────────────────────────────────┐
│              garminview Python Backend                            │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Data Ingestion Layer                                     │     │
│  │  • GarminDB pipeline (bulk) + garminconnect (real-time)  │     │
│  │  • Apple Health XML/CDA parser                           │     │
│  │  • MyFitnessPal nutrition data importer                  │     │
│  │  • Actalog activity data importer                        │     │
│  └─────────────────────┬───────────────────────────────────┘     │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ SQLite / MariaDB                                         │     │
│  │  • Garmin tables (5 DBs, 30+ tables)                     │     │
│  │  • External source tables (nutrition, additional health)  │     │
│  │  • Derived metrics & assessment tables                    │     │
│  └─────────────────────┬───────────────────────────────────┘     │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Analysis Engine                                          │     │
│  │  • Derived metrics calculation                           │     │
│  │  • Intelligent assessments (trends, targets, goals)      │     │
│  │  • Cross-source correlation & pattern detection           │     │
│  │  • Data quality validation                               │     │
│  └─────────────────────┬───────────────────────────────────┘     │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ REST API                                                 │     │
│  │  • Dashboard data endpoints                              │     │
│  │  • Report generation endpoints                           │     │
│  │  • Export endpoints (PDF, CSV, JSON)                     │     │
│  │  • Goal management endpoints                             │     │
│  └─────────────────────┬───────────────────────────────────┘     │
│                        │                                         │
└────────────────────────┼─────────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼                     ▼
   ┌──────────────────┐  ┌──────────────────┐
   │ Vue.js Web App   │  │ Marimo Notebooks │
   │ (Dashboards,     │  │ (Ad-hoc analysis │
   │  Reports, Goals, │  │  & prototyping)  │
   │  Export, Share)  │  │                  │
   └──────────────────┘  └──────────────────┘
```

### 1.4 Garmin Database Targets (via GarminDB)

| Database | Contents |
|----------|----------|
| `garmin.db` | Devices, weight, sleep, stress, RHR, daily summaries |
| `garmin_monitoring.db` | Minute-level HR, SpO2, respiration, intensity, elevation |
| `garmin_activities.db` | Activities, laps, records, splits, sport-specific metrics |
| `garmin_summary.db` | Day/week/month/year aggregations |
| `summary.db` | Cross-trainer summary aggregations |

---

## 2. Data Harvesting — Garmin Connect

### 2.1 Initial Historical Backfill

| Requirement | Detail |
|-------------|--------|
| **REQ-DH-001** | Download ALL historical activities (use `get_activities_by_date` with auto-pagination, no limit) |
| **REQ-DH-002** | Download ALL historical daily summaries back to the earliest configured start date |
| **REQ-DH-003** | Download ALL historical sleep data back to start date |
| **REQ-DH-004** | Download ALL historical weight / body composition data back to start date |
| **REQ-DH-005** | Download ALL historical resting heart rate data back to start date |
| **REQ-DH-006** | Download ALL historical monitoring FIT files (minute-level HR, steps, SpO2, respiration) |
| **REQ-DH-007** | Download ALL historical stress data |
| **REQ-DH-008** | Download ALL historical HRV data |
| **REQ-DH-009** | Download ALL historical body battery data |
| **REQ-DH-010** | Download ALL historical hydration data |
| **REQ-DH-011** | Download ALL historical blood pressure data (if available) |
| **REQ-DH-012** | Download ALL historical training readiness and training status data |
| **REQ-DH-013** | Download ALL historical VO2 Max / fitness age data |
| **REQ-DH-014** | Download ALL historical intensity minutes data |
| **REQ-DH-015** | Download activity FIT files for every activity (original sensor data) |
| **REQ-DH-016** | Respect Garmin rate limits (429 status) with exponential backoff and retry |
| **REQ-DH-017** | Auto-chunk date ranges >28 days into 28-day batches |
| **REQ-DH-018** | Store all raw files locally so databases can be rebuilt without re-downloading |

### 2.2 Incremental Updates

| Requirement | Detail |
|-------------|--------|
| **REQ-DU-001** | Support `--latest` mode: download only data since last sync timestamp |
| **REQ-DU-002** | Detect and fill gaps in historical data (missing days) |
| **REQ-DU-003** | Run full pipeline on update: download → import → analyze → summarize |
| **REQ-DU-004** | Support scheduled automated updates (cron / systemd timer) |
| **REQ-DU-005** | Log sync timestamps, record counts, and errors per update run |

### 2.3 Authentication

| Requirement | Detail |
|-------------|--------|
| **REQ-DA-001** | OAuth 2.0 authentication via Garth library |
| **REQ-DA-002** | Token persistence (~1 year lifetime) at `~/.garminconnect` |
| **REQ-DA-003** | MFA support with interactive prompt fallback |
| **REQ-DA-004** | Automatic token refresh without manual re-login |

---

## 3. Multi-Source Data Integration

Garmin Connect is the primary data source, but the system will eventually integrate additional sources for a holistic health picture.

### 3.1 Apple Health (Phase 2)

| Requirement | Detail |
|-------------|--------|
| **REQ-MS-001** | Import Apple Health XML/CDA export files |
| **REQ-MS-002** | Parse and store: steps, heart rate, sleep, workouts, nutrition, body measurements, reproductive health, mindfulness |
| **REQ-MS-003** | Deduplicate overlapping data with Garmin (same activity recorded on both Apple Watch and Garmin) |
| **REQ-MS-004** | Map Apple Health data types to unified garminview schema |
| **REQ-MS-005** | Support periodic re-import as user exports new Apple Health data |

### 3.2 MyFitnessPal (Phase 2)

| Requirement | Detail |
|-------------|--------|
| **REQ-MS-010** | Import nutrition/food diary data (API or CSV export) |
| **REQ-MS-011** | Store: daily calories consumed, macronutrients (protein, carbs, fat), micronutrients if available |
| **REQ-MS-012** | Store: meal timing (breakfast, lunch, dinner, snacks) |
| **REQ-MS-013** | Correlate nutrition intake with Garmin calorie expenditure for energy balance analysis |
| **REQ-MS-014** | Track calorie target compliance over time |

### 3.3 Actalog (Phase 2)

| Requirement | Detail |
|-------------|--------|
| **REQ-MS-020** | Import activity/exercise data from Actalog (API or export) |
| **REQ-MS-021** | Map Actalog activity types to garminview unified activity taxonomy |
| **REQ-MS-022** | Deduplicate activities that exist in both Garmin and Actalog |
| **REQ-MS-023** | Incorporate Actalog-specific metadata not captured by Garmin |

### 3.4 Unified Data Model

| Requirement | Detail |
|-------------|--------|
| **REQ-MS-030** | Define a unified schema that normalizes data across all sources |
| **REQ-MS-031** | Track data provenance — every record tagged with its source (Garmin, Apple Health, MFP, Actalog) |
| **REQ-MS-032** | Source priority rules: when the same metric appears from multiple sources, apply configurable precedence (default: Garmin > Apple Health > others) |
| **REQ-MS-033** | Extensible adapter pattern: adding a new data source should not require changes to the analysis or visualization layers |

---

## 4. Data Storage

### 4.1 Raw Data Retention

| Requirement | Detail |
|-------------|--------|
| **REQ-DS-001** | Retain all downloaded FIT, JSON, and TCX files indefinitely |
| **REQ-DS-002** | Support `--rebuild_db` to regenerate all SQLite databases from retained raw files |
| **REQ-DS-003** | Handle schema version upgrades gracefully (detect version mismatch, auto-rebuild) |

### 4.2 Database Integrity

| Requirement | Detail |
|-------------|--------|
| **REQ-DI-001** | Upsert semantics: re-importing a day overwrites stale data, never creates duplicates |
| **REQ-DI-002** | Automated backup before destructive operations (rebuild, delete) |
| **REQ-DI-003** | Validate record counts after import against expected day count |

---

### 4.3 Database Engine

| Requirement | Detail |
|-------------|--------|
| **REQ-DB-001** | Support SQLite as the default database (single-user, zero-config, file-based) |
| **REQ-DB-002** | Support MariaDB as an optional backend (multi-user, higher concurrency, remote access) |
| **REQ-DB-003** | Database engine selection via configuration — all queries and models must work with both backends |
| **REQ-DB-004** | Use an ORM or abstraction layer (e.g., SQLAlchemy) to ensure portability between SQLite and MariaDB |

---

## 5. Health & Body Metrics — Reports & Analysis

This is the primary reporting focus. Every metric below should support daily, weekly, monthly, and yearly aggregation with trend lines, rolling averages, and statistical summaries.

### 5.1 Sleep Analysis (Priority: HIGH)

**Source data**: Sleep table, SleepEvents table, DailySummary

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-HS-001** | Total sleep duration | Nightly hours, trend over time |
| **REQ-HS-002** | Sleep stage breakdown | REM / light / deep / awake — absolute minutes and percentages |
| **REQ-HS-003** | Sleep stage ratios | % deep sleep, % REM sleep with population benchmarks |
| **REQ-HS-004** | Sleep efficiency | (Total sleep − awake time) / time in bed × 100 |
| **REQ-HS-005** | Sleep consistency | Bedtime and wake-time variability (std deviation) |
| **REQ-HS-006** | Sleep quality score | Garmin sleep score + trend |
| **REQ-HS-007** | Sleep SpO2 | Average blood oxygen during sleep, dip events |
| **REQ-HS-008** | Sleep respiration rate | Average breathing rate during sleep |
| **REQ-HS-009** | Sleep stress | Average stress level during sleep |
| **REQ-HS-010** | Sleep vs. recovery correlation | Sleep quality vs. next-day body battery, HRV, training readiness |
| **REQ-HS-011** | Sleep debt tracking | Cumulative deficit below target (e.g., 7–9h) over rolling 7/14/30 days |
| **REQ-HS-012** | Day-of-week sleep patterns | Average sleep by weekday vs. weekend |
| **REQ-HS-013** | Sleep stage timeline | Hypnogram visualization per night |
| **REQ-HS-014** | Sleep latency estimation | Time from bedtime to first non-awake stage |
| **REQ-HS-015** | Sleep regularity index (SRI) | Derived: probability of same sleep/wake state at same time across days (0–100) |

### 5.2 Weight & Body Composition (Priority: HIGH)

**Source data**: Weight table, `get_body_composition`, `get_weigh_ins`

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-HW-001** | Weight trend | Daily weight with 7-day and 30-day moving averages |
| **REQ-HW-002** | Weight rate of change | Weekly Δ (lbs/kg per week), monthly Δ |
| **REQ-HW-003** | Body fat percentage | Trend over time, with population percentile reference |
| **REQ-HW-004** | Lean body mass | Weight × (1 − body fat %) — trend over time |
| **REQ-HW-005** | Muscle mass trend | If available from scale data |
| **REQ-HW-006** | Bone mass trend | If available from scale data |
| **REQ-HW-007** | Hydration percentage | Body water % trend |
| **REQ-HW-008** | BMI | Calculated from weight + height, plotted over time |
| **REQ-HW-009** | Metabolic age | Garmin-reported metabolic age vs. chronological age |
| **REQ-HW-010** | Basal metabolic rate (BMR) | Daily BMR trend |
| **REQ-HW-011** | Visceral fat rating | Trend and risk zone classification |
| **REQ-HW-012** | Physique rating | Garmin physique rating over time |
| **REQ-HW-013** | Weight goal tracking | Current vs. target weight, projected date to reach goal |
| **REQ-HW-014** | Body recomposition index | Derived: lean mass gained / fat mass lost ratio over rolling periods |
| **REQ-HW-015** | Weight vs. training load | Correlation of weight changes with activity volume |

### 5.3 Heart Rate & Cardiovascular (Priority: HIGH)

**Source data**: RestingHeartRate, MonitoringHeartRate, DailySummary, HRV data

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-HC-001** | Resting heart rate | Daily RHR trend, 7/30/90-day moving average |
| **REQ-HC-002** | RHR variability | Day-to-day RHR delta, standard deviation over windows |
| **REQ-HC-003** | Heart rate range | Daily min, max, avg with band chart |
| **REQ-HC-004** | HRV trend | Daily HRV (RMSSD or Garmin metric) with rolling average |
| **REQ-HC-005** | HRV baseline & status | 7-day HRV baseline vs. current reading, status classification |
| **REQ-HC-006** | HRV coefficient of variation | Derived: HRV CV% = (SD / mean) × 100 over rolling windows |
| **REQ-HC-007** | Autonomic balance indicators | Derived from HRV: sympathetic vs. parasympathetic proxy |
| **REQ-HC-008** | Heart rate recovery estimation | Post-activity HR drop (from activity records) |
| **REQ-HC-009** | Cardiac drift detection | HR increase at constant pace during endurance activities |
| **REQ-HC-010** | RHR anomaly detection | Flag days where RHR deviates >2 SD from 30-day mean (illness/overtraining indicator) |

### 5.4 Stress & Recovery (Priority: HIGH)

**Source data**: Stress table, DailySummary, body battery, training readiness

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-HR-001** | Daily stress average | Trend over time |
| **REQ-HR-002** | Stress distribution | Time in low / medium / high / rest stress zones per day |
| **REQ-HR-003** | Body battery | Daily max, min, charged, drained values |
| **REQ-HR-004** | Body battery efficiency | Derived: charge gained per hour of rest vs. drain per hour of activity |
| **REQ-HR-005** | Training readiness score | Daily score (1–100) with trend |
| **REQ-HR-006** | Training readiness components | Sleep, recovery, training load contributions to readiness |
| **REQ-HR-007** | Recovery-to-stress ratio | Derived: hours in recovery / hours in stress per day |
| **REQ-HR-008** | Stress day-of-week patterns | Average stress by weekday |
| **REQ-HR-009** | Cumulative stress load | Rolling 7/14/30-day stress sum |

### 5.5 Blood Oxygen & Respiration (Priority: MEDIUM)

**Source data**: MonitoringPulseOx, MonitoringRespirationRate, DailySummary

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-HO-001** | SpO2 daily average | Trend over time |
| **REQ-HO-002** | SpO2 overnight trend | Sleep-time SpO2 trend, desaturation event count |
| **REQ-HO-003** | Respiration rate | Daily average, sleep average, trend |
| **REQ-HO-004** | SpO2 anomaly detection | Flag days below 90% (clinical concern threshold) |
| **REQ-HO-005** | Respiratory rate vs. training load | Correlation with elevated respiration and overtraining |

### 5.6 Hydration (Priority: MEDIUM)

**Source data**: DailySummary hydration fields, `get_hydration_data`

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-HH-001** | Daily water intake vs. goal | Trend and compliance % |
| **REQ-HH-002** | Sweat loss tracking | Estimated sweat loss per activity day |
| **REQ-HH-003** | Hydration vs. performance | Correlation with activity performance metrics |

---

## 6. Activity & Training Metrics — Reports & Analysis

### 6.1 Activity Volume & Distribution

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-AT-001** | Activity count by type | Weekly/monthly/yearly breakdown (run, bike, swim, hike, strength, etc.) |
| **REQ-AT-002** | Total duration by type | Hours per activity type over time |
| **REQ-AT-003** | Total distance by type | km/miles per activity type over time |
| **REQ-AT-004** | Training frequency | Activities per week, consistency streaks |
| **REQ-AT-005** | Activity calendar heatmap | GitHub-style heatmap of training days |
| **REQ-AT-006** | Intensity minutes | Weekly moderate + vigorous minutes vs. WHO 150/75 min target |
| **REQ-AT-007** | Calorie expenditure | Total / active / BMR calories, daily and trended |
| **REQ-AT-008** | Steps & distance | Daily steps vs. goal, distance walked/run over time |
| **REQ-AT-009** | Floors climbed | Daily floors vs. goal, trend |

### 6.2 Running Metrics

**Source data**: StepsActivities (running views), Activities, ActivityRecords

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-AR-001** | Pace trend | Average pace over time by distance/type |
| **REQ-AR-002** | Cadence | Steps per minute average and distribution |
| **REQ-AR-003** | Stride length | Average stride length trend |
| **REQ-AR-004** | Vertical oscillation | Bounce per step — efficiency indicator |
| **REQ-AR-005** | Ground contact time | GCT and GCT balance trend |
| **REQ-AR-006** | Running power | If available (Stryd/Garmin) — power per run |
| **REQ-AR-007** | Heart rate zones per run | Time-in-zone distribution per activity |
| **REQ-AR-008** | Elevation gain per run | Cumulative climb metrics |
| **REQ-AR-009** | Negative splits analysis | Even/negative/positive split detection per run |
| **REQ-AR-010** | Race predictions | Garmin-estimated 5K / 10K / half / full marathon times, trend |
| **REQ-AR-011** | Course comparison | Same route repeated — pace, HR, time comparison over months |

### 6.3 Cycling Metrics

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-AC-001** | FTP trend | Functional Threshold Power over time |
| **REQ-AC-002** | Average speed trend | Speed by ride type |
| **REQ-AC-003** | Power zones | Time-in-zone per ride (if power meter equipped) |
| **REQ-AC-004** | Elevation per ride | Climbing volume trends |
| **REQ-AC-005** | Cadence trend | RPM averages and distribution |

### 6.4 Strength & General Fitness

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-AS-001** | Strength training volume | Sets, reps, exercises per session |
| **REQ-AS-002** | Training load | Garmin training load per activity |
| **REQ-AS-003** | Training effect | Aerobic + anaerobic training effect per activity |
| **REQ-AS-004** | VO2 Max trend | Running and cycling VO2 Max over time |
| **REQ-AS-005** | Fitness age trend | Garmin fitness age vs. chronological age over time |
| **REQ-AS-006** | Hill score trend | Hill / climbing capability score |
| **REQ-AS-007** | Endurance score trend | Multi-sport endurance metric |
| **REQ-AS-008** | Personal records timeline | PRs for distances, paces, times — when achieved |
| **REQ-AS-009** | Gear tracking & mileage | Shoe / equipment mileage, projected replacement date |

### 6.5 Training Load & Periodization

| Requirement | Metric / Report | Detail |
|-------------|----------------|--------|
| **REQ-AL-001** | Acute training load (ATL) | 7-day rolling load (TRIMP or duration-weighted) |
| **REQ-AL-002** | Chronic training load (CTL) | 42-day rolling load |
| **REQ-AL-003** | Training stress balance (TSB) | CTL − ATL = form estimate |
| **REQ-AL-004** | Training status | Garmin status: productive / maintaining / recovery / unproductive / detraining / overreaching / peaking |
| **REQ-AL-005** | Lactate threshold trend | Speed, HR, and power at LT over time |
| **REQ-AL-006** | Monotony & strain | Derived: monotony = mean load / SD load; strain = weekly load × monotony |
| **REQ-AL-007** | Polarized training distribution | % of activities in zone 1 / zone 2 / zone 3 (80/20 compliance) |

---

## 7. Derived & Calculated Metrics

These metrics are NOT provided by Garmin directly. They are calculated from raw Garmin data using established exercise science formulas.

### 7.1 Training Load & Fitness Modeling

| Metric | Formula / Method | Source Data |
|--------|-----------------|-------------|
| **TRIMP (Training Impulse)** | Duration × avg HR fraction × weighting factor (Banister 1991) | Activity HR + duration |
| **hrTSS (Heart Rate Training Stress Score)** | (duration × avg HR × intensity factor) / (FTP HR × 3600) × 100 | Activity HR, threshold HR |
| **Acute Training Load (ATL)** | Exponentially weighted moving average, 7-day time constant | Daily TRIMP/hrTSS |
| **Chronic Training Load (CTL)** | EWMA, 42-day time constant | Daily TRIMP/hrTSS |
| **Training Stress Balance (TSB)** | CTL − ATL (positive = fresh, negative = fatigued) | ATL, CTL |
| **Monotony Index** | Mean(daily load) / SD(daily load) over 7 days | Daily training load |
| **Strain** | Weekly load sum × monotony | Weekly load, monotony |
| **ACWR (Acute:Chronic Workload Ratio)** | ATL / CTL — sweet spot 0.8–1.3, injury risk >1.5 | ATL, CTL |

### 7.2 Cardiovascular & Recovery

| Metric | Formula / Method | Source Data |
|--------|-----------------|-------------|
| **HRV Coefficient of Variation** | (SD of HRV / Mean HRV) × 100 over rolling window | Daily HRV |
| **Autonomic Stress Score** | Derived from HRV: ln(RMSSD) normalized to 1–10 scale | HRV data |
| **Heart Rate Recovery (HRR)** | HR at end of activity − HR at 1 min / 2 min post-activity | Activity HR records |
| **Cardiac Efficiency Index** | Pace / HR — higher = more efficient | Running pace + HR |
| **Orthostatic HR response** | Standing HR − resting HR (if morning data available) | Morning HR data |
| **RHR Z-Score** | (Today's RHR − 30-day mean) / 30-day SD | Daily RHR |
| **Readiness Composite Score** | Weighted: 30% HRV + 25% RHR + 20% sleep quality + 15% body battery + 10% stress | Multiple sources |

### 7.3 Sleep Science

| Metric | Formula / Method | Source Data |
|--------|-----------------|-------------|
| **Sleep Efficiency** | (Total sleep − awake) / time in bed × 100 | Sleep table |
| **Sleep Regularity Index (SRI)** | Probability of same state (asleep/awake) at same time across consecutive days | SleepEvents |
| **Sleep Debt** | Cumulative (target hours − actual hours) over rolling N days | Sleep duration |
| **Social Jet Lag** | |Weekend midpoint of sleep − weekday midpoint of sleep| | Sleep start/end |
| **REM Rebound Detection** | Flag nights with >30% REM following REM-deprived nights | Sleep stages |
| **Deep Sleep Adequacy** | Deep sleep minutes vs. age-adjusted target (15–20% of total) | Sleep stages |

### 7.4 Body Composition Science

| Metric | Formula / Method | Source Data |
|--------|-----------------|-------------|
| **Lean Body Mass (LBM)** | Weight × (1 − body fat %) | Weight + body fat |
| **Fat-Free Mass Index (FFMI)** | LBM(kg) / height(m)² — benchmark: 18–25 natural range | LBM + height |
| **Body Recomposition Index** | Δ lean mass / Δ fat mass over period (positive = recomp) | Body composition history |
| **Weight Velocity** | Rate of change: Δ weight / Δ time (smoothed) | Weight trend |
| **Predicted TDEE** | BMR × activity factor (from daily active calories / BMR ratio) | Calorie data |

### 7.5 Performance Efficiency

| Metric | Formula / Method | Source Data |
|--------|-----------------|-------------|
| **Efficiency Factor (EF)** | Normalized pace ÷ avg HR for aerobic runs — increasing = improving | Run pace + HR |
| **Pace Decoupling** | (1st half EF − 2nd half EF) / 1st half EF × 100 — <5% = good aerobic base | Activity laps/splits |
| **Running Economy Proxy** | Pace at given HR over time — tracks how fast you can go at same effort | Runs at similar HR |
| **Endurance Ratio** | Best pace at long distance / best pace at short distance | Personal records |
| **Power-to-Weight Ratio** | FTP / body weight (cycling benchmark) | FTP + weight |

### 7.6 Composite & Wellness Scores

| Metric | Formula / Method | Source Data |
|--------|-----------------|-------------|
| **Daily Wellness Score** | Weighted composite: sleep + HRV + RHR + stress + body battery (0–100) | Multiple daily metrics |
| **Weekly Fitness Trend** | Direction (improving / maintaining / declining) from CTL slope | CTL over weeks |
| **Overtraining Risk Score** | Composite: elevated RHR + depressed HRV + poor sleep + high monotony + ACWR >1.5 | Multiple metrics |
| **Injury Risk Index** | ACWR spike + monotony + strain above threshold | Training load metrics |
| **Recovery Quality Score** | Body battery overnight charge rate + HRV trend + sleep score | Recovery metrics |

---

## 8. Intelligent Assessments & Goal Tracking

The system will go beyond raw metrics to provide actionable assessments based on authoritative exercise science, sleep research, and health guidelines.

### 8.1 Automated Trend Assessments

| Requirement | Detail |
|-------------|--------|
| **REQ-IA-001** | For each key metric, automatically classify the trend direction: improving, stable, declining, or insufficient data |
| **REQ-IA-002** | Apply configurable lookback windows (7/14/30/90 days) for trend detection |
| **REQ-IA-003** | Generate natural-language assessment summaries (e.g., "Your RHR has decreased 4 bpm over 30 days — consistent with improving cardiovascular fitness") |
| **REQ-IA-004** | Reference authoritative sources inline (e.g., AHA guidelines, ACSM recommendations, WHO targets) |
| **REQ-IA-005** | Flag concerning trends with severity levels: informational, caution, warning (e.g., rising RHR + declining HRV + poor sleep → overtraining warning) |

### 8.2 Target & Benchmark Evaluation

| Requirement | Detail |
|-------------|--------|
| **REQ-IA-010** | Compare metrics against evidence-based population benchmarks (age/sex adjusted where available) |
| **REQ-IA-011** | Sleep targets: assess against National Sleep Foundation recommendations (7–9h for adults, ≥15% deep, ≥20% REM) |
| **REQ-IA-012** | Activity targets: assess against WHO physical activity guidelines (150 min moderate or 75 min vigorous/week) |
| **REQ-IA-013** | Cardiovascular: classify RHR into fitness zones (athlete <50, excellent 50–60, good 60–70, etc.) |
| **REQ-IA-014** | VO2 Max: compare against age/sex percentile tables (ACSM classification: superior, excellent, good, fair, poor) |
| **REQ-IA-015** | Body composition: assess body fat % against ACSM categories, BMI against WHO ranges, visceral fat against health risk zones |
| **REQ-IA-016** | Weight velocity: flag rates exceeding safe thresholds (>1 kg/week loss or >0.5 kg/week gain) |
| **REQ-IA-017** | HRV: classify against age-adjusted norms and individual baseline |

### 8.3 Goal Management

| Requirement | Detail |
|-------------|--------|
| **REQ-IG-001** | User-defined goals with target metric, target value, and target date (e.g., "Reach 75 kg by June 1") |
| **REQ-IG-002** | Goal types: weight target, body fat % target, VO2 Max target, weekly activity volume, sleep duration, RHR target |
| **REQ-IG-003** | Progress tracking: % complete, current trajectory, projected achievement date |
| **REQ-IG-004** | Goal status: on-track, behind, ahead, achieved, abandoned |
| **REQ-IG-005** | Goal history: archive completed/abandoned goals with outcome summary |
| **REQ-IG-006** | Automatic suggestions: recommend goal adjustments when trajectory diverges significantly from target |

### 8.4 Health & Fitness Assessments

| Requirement | Detail |
|-------------|--------|
| **REQ-IA-020** | Weekly health assessment: synthesize sleep, stress, recovery, weight, and activity into a narrative summary |
| **REQ-IA-021** | Training load assessment: classify current training phase (building, maintaining, recovering, overreaching) based on ATL/CTL/TSB |
| **REQ-IA-022** | Recovery assessment: rate overnight recovery quality from body battery charge rate, HRV, sleep quality |
| **REQ-IA-023** | Injury risk assessment: flag elevated risk from ACWR spikes, high monotony, training load ramp rate |
| **REQ-IA-024** | Sleep assessment: rate sleep quality against individual baseline and population norms, flag sleep debt |
| **REQ-IA-025** | Body composition assessment: evaluate trajectory toward goal, flag plateau, suggest adjustment |

---

## 9. Cross-Source Correlation & Data Quality

### 9.1 Correlation Analysis

| Requirement | Detail |
|-------------|--------|
| **REQ-CC-001** | Automatically compute Pearson/Spearman correlations between all major metric pairs |
| **REQ-CC-002** | Highlight statistically significant correlations (p < 0.05) with effect size |
| **REQ-CC-003** | Key cross-metric correlations to surface: sleep quality ↔ next-day HRV, sleep ↔ training readiness, weight trend ↔ calorie balance, training load ↔ RHR, stress ↔ sleep quality, nutrition ↔ performance (when MFP data available) |
| **REQ-CC-004** | Lagged correlation analysis: test whether metric A on day N predicts metric B on day N+1 (e.g., does poor sleep predict elevated RHR?) |
| **REQ-CC-005** | Present correlation findings as scatter plots with regression lines and confidence intervals |
| **REQ-CC-006** | Periodic correlation report: monthly summary of strongest correlations discovered in the user's data |

### 9.2 Pattern Detection

| Requirement | Detail |
|-------------|--------|
| **REQ-CC-010** | Day-of-week patterns: detect significant weekday vs. weekend differences for sleep, stress, activity, weight |
| **REQ-CC-011** | Seasonal patterns: detect month-over-month or seasonal trends (e.g., less activity in winter, weight gain in holidays) |
| **REQ-CC-012** | Pre/post activity patterns: how do metrics change in the days before and after intense training blocks? |
| **REQ-CC-013** | Habit streak detection: identify consistent behavior streaks (e.g., "You've hit 10K steps for 14 consecutive days") |
| **REQ-CC-014** | Anomaly clustering: group co-occurring anomalies (e.g., poor sleep + high stress + elevated RHR on same day) |

### 9.3 Data Quality Monitoring

| Requirement | Detail |
|-------------|--------|
| **REQ-DQ-001** | Detect missing data: flag days with no sleep, no HR, no activity, no weight when historically present |
| **REQ-DQ-002** | Detect implausible values: weight spikes >5 kg in a day, RHR <30 or >120, sleep >16h, SpO2 <70% |
| **REQ-DQ-003** | Detect device gaps: identify periods where monitoring data is absent (device not worn, battery dead, sync issues) |
| **REQ-DQ-004** | Detect duplicate records: same activity from multiple sources or duplicate weigh-ins |
| **REQ-DQ-005** | Data completeness dashboard: percentage of days with data for each metric type over configurable period |
| **REQ-DQ-006** | Source conflict detection: flag when the same metric from different sources disagrees significantly |
| **REQ-DQ-007** | Data freshness indicator: show time since last successful sync per data source |

---

## 10. Web Application — Vue.js Frontend

### 10.1 General Web UI

| Requirement | Detail |
|-------------|--------|
| **REQ-WA-001** | Single-page application (SPA) built with Vue.js |
| **REQ-WA-002** | Responsive design: desktop, tablet, and mobile layouts |
| **REQ-WA-003** | Navigation: sidebar with dashboard sections, top bar with date range selector and sync status |
| **REQ-WA-004** | Dark mode / light mode toggle |
| **REQ-WA-005** | Loading states and graceful error display for all data views |
| **REQ-WA-006** | Authentication: local user login (no multi-tenant required for v1, but secure API access) |

### 10.2 Backend REST API

| Requirement | Detail |
|-------------|--------|
| **REQ-WA-010** | Python REST API (Flask or FastAPI) serving all dashboard, report, and export endpoints |
| **REQ-WA-011** | Endpoints for: daily/weekly/monthly metric summaries, activity lists, trend data, assessment results, goal CRUD |
| **REQ-WA-012** | Pagination and date-range filtering on all list endpoints |
| **REQ-WA-013** | Export endpoints: generate PDF/CSV/JSON for any report or data view |
| **REQ-WA-014** | Webhook or SSE support: push updates to frontend when new data is synced |
| **REQ-WA-015** | API documentation (OpenAPI/Swagger) |

### 10.3 Interactive Features

| Requirement | Detail |
|-------------|--------|
| **REQ-WA-020** | Interactive charts: zoom, pan, hover tooltips, click-to-drill-down |
| **REQ-WA-021** | Configurable date ranges on all views (preset: 7d, 30d, 90d, 1y, all-time, custom) |
| **REQ-WA-022** | Metric comparison: overlay any two metrics on a dual-axis chart |
| **REQ-WA-023** | Goal management UI: create, edit, track, archive goals |
| **REQ-WA-024** | Assessment viewer: browse weekly/monthly assessments with drill-down to supporting data |
| **REQ-WA-025** | Data quality dashboard: view completeness, freshness, and flagged issues |
| **REQ-WA-026** | Manual sync trigger from the UI |

---

## 11. Dashboards & Visualization

### 11.1 Dashboard Views

| Requirement | Dashboard | Content |
|-------------|-----------|---------|
| **REQ-VD-001** | **Daily Overview** | Today's snapshot: sleep score, weight, RHR, HRV, stress, body battery, steps, activities, wellness score |
| **REQ-VD-002** | **Sleep Dashboard** | Sleep duration trend, stage breakdown stacked bar, hypnogram, efficiency, consistency, debt tracker |
| **REQ-VD-003** | **Weight & Body Comp Dashboard** | Weight trend line with moving averages, body fat %, lean mass, BMI, metabolic age, body recomp index |
| **REQ-VD-004** | **Cardiovascular Dashboard** | RHR trend, HRV trend with baseline band, HR recovery, RHR anomaly flags |
| **REQ-VD-005** | **Training Load Dashboard** | ATL/CTL/TSB chart (PMC chart), ACWR, monotony, strain, training status timeline |
| **REQ-VD-006** | **Activity Summary Dashboard** | Volume by type (bar chart), calendar heatmap, intensity minutes vs. target, calorie trends |
| **REQ-VD-007** | **Running Dashboard** | Pace trends, cadence, stride, GCT, race predictions, course comparisons, VO2 Max |
| **REQ-VD-008** | **Recovery & Stress Dashboard** | Stress distribution, body battery timeline, training readiness, recovery quality, wellness score |
| **REQ-VD-009** | **Long-Term Trends** | Year-over-year comparisons for all major metrics (weight, RHR, VO2 Max, sleep, activity volume) |
| **REQ-VD-010** | **Correlation Explorer** | Scatter plots and correlations between any two metrics (e.g., sleep vs. HRV, weight vs. activity) |
| **REQ-VD-011** | **Assessments & Goals Dashboard** | Current goal progress, weekly/monthly assessments, trend classifications, benchmark comparisons, alerts |
| **REQ-VD-012** | **Data Quality Dashboard** | Data completeness by metric, freshness per source, flagged anomalies, device gaps, duplicate warnings |
| **REQ-VD-013** | **Nutrition Dashboard** (Phase 2) | Calorie intake vs. expenditure, macronutrient breakdown, meal timing, calorie target compliance (requires MFP data) |

### 11.2 Visualization Requirements

| Requirement | Detail |
|-------------|--------|
| **REQ-VV-001** | Time-series line charts with configurable rolling averages (7/14/30/90 day) |
| **REQ-VV-002** | Stacked bar charts for composition data (sleep stages, activity types, HR zones) |
| **REQ-VV-003** | Heatmaps for calendar views and day-of-week patterns |
| **REQ-VV-004** | Box plots / violin plots for distribution analysis |
| **REQ-VV-005** | Dual-axis charts for correlation overlays |
| **REQ-VV-006** | Sparklines for compact trend indicators |
| **REQ-VV-007** | Statistical annotations: mean lines, ±1 SD bands, trend regression lines |
| **REQ-VV-008** | Anomaly markers (dots/flags) on charts for outlier events |
| **REQ-VV-009** | Configurable date range selection for all views |
| **REQ-VV-010** | Export charts as PNG/SVG and data as CSV |

### 11.3 Report Generation

| Requirement | Detail |
|-------------|--------|
| **REQ-VR-001** | Weekly summary report (auto-generated): key metrics, changes, highlights |
| **REQ-VR-002** | Monthly health report: all metrics with month-over-month comparison |
| **REQ-VR-003** | Quarterly fitness review: VO2 Max, CTL progression, body composition changes, PRs |
| **REQ-VR-004** | Custom date-range report generation |
| **REQ-VR-005** | Output formats: HTML, PDF, marimo notebook |

---

## 12. Marimo Notebooks — Ad-Hoc Exploration

| Requirement | Detail |
|-------------|--------|
| **REQ-MN-001** | Provide one or more marimo notebooks that connect directly to the garminview database(s) |
| **REQ-MN-002** | Notebook for **health exploration**: interactive widgets to select date ranges, metrics, and aggregation levels for sleep, weight, HR, HRV, stress |
| **REQ-MN-003** | Notebook for **activity exploration**: filter by activity type, date, distance; visualize pace, HR zones, elevation, splits |
| **REQ-MN-004** | Notebook for **correlation exploration**: select any two metrics, compute and visualize correlation with scatter plot, regression, and statistical summary |
| **REQ-MN-005** | Notebook for **training load modeling**: interactive PMC chart (ATL/CTL/TSB), adjustable time constants, ACWR visualization |
| **REQ-MN-006** | Notebooks serve as prototyping ground — visualizations validated in notebooks can be promoted to the Vue.js web dashboards |
| **REQ-MN-007** | Notebooks runnable standalone (no web server dependency) using `marimo run` |
| **REQ-MN-008** | Shared utility module: common database queries, metric calculations, and chart builders reusable between notebooks and the web backend |

---

## 13. Export & Sharing

| Requirement | Detail |
|-------------|--------|
| **REQ-EX-001** | Export any dashboard view or report as **PDF** (print-quality layout) |
| **REQ-EX-002** | Export raw or aggregated data as **CSV** (with column headers and metadata) |
| **REQ-EX-003** | Export raw or aggregated data as **JSON** (structured, machine-readable) |
| **REQ-EX-004** | Export chart images as **PNG** or **SVG** |
| **REQ-EX-005** | Bulk export: download all data for a date range across all metric types in a single ZIP archive |
| **REQ-EX-006** | Shareable report links: generate a static HTML report that can be shared without requiring app access |
| **REQ-EX-007** | Export configuration: user can select which metrics, date ranges, and aggregation levels to include |
| **REQ-EX-008** | Data portability: full database export for migration or backup purposes |

---

## 14. Scheduling & Automation

| Requirement | Detail |
|-------------|--------|
| **REQ-SA-001** | Automated daily sync: download latest → import → analyze → update dashboards |
| **REQ-SA-002** | Configurable sync schedule via cron or systemd timer |
| **REQ-SA-003** | Sync logging with success/failure status and record counts |
| **REQ-SA-004** | Notification on sync failure (optional: email, desktop notification) |
| **REQ-SA-005** | Manual trigger for full historical re-sync or specific date range |

---

## 15. Non-Functional Requirements

| Requirement | Detail |
|-------------|--------|
| **REQ-NF-001** | All data stored locally — no cloud dependency after download |
| **REQ-NF-002** | Credentials stored securely (OAuth tokens, not plaintext passwords in config files) |
| **REQ-NF-003** | Idempotent operations — re-running import produces identical results |
| **REQ-NF-004** | Graceful degradation — missing metrics (no scale, no HRV device) or unavailable data sources should not break reports |
| **REQ-NF-005** | Performance: dashboards load in <2s for 5+ years of daily data |
| **REQ-NF-006** | Python 3.10+ for the backend |
| **REQ-NF-007** | Vue.js 3.x for the frontend (Composition API) |
| **REQ-NF-008** | SQLite (default) or MariaDB (optional) — selectable via configuration |
| **REQ-NF-009** | Comprehensive error handling with meaningful messages |
| **REQ-NF-010** | Configurable units: metric / imperial |
| **REQ-NF-011** | Data source extensibility: new sources can be added via adapter pattern without modifying core analysis or UI |
| **REQ-NF-012** | Marimo notebooks run independently of the web application |
| **REQ-NF-013** | API security: all REST endpoints require authentication; no sensitive data in URLs |
| **REQ-NF-014** | Logging: structured logging for sync, analysis, and API operations with configurable verbosity |

---

## Appendix A: Complete Garmin Data Inventory

### Data Available via python-garminconnect (105+ API endpoints)

**Daily Health (per-day)**:
- Steps (hourly breakdown), floors, distance, calories (total/BMR/active/consumed)
- Heart rate (resting, min, max, avg, zones), HRV
- Sleep (duration, stages, score, SpO2, respiration, stress)
- Stress (all-day levels, average), body battery (charge/drain/max/min)
- SpO2 (blood oxygen), respiration rate
- Training readiness (score + components), training status
- VO2 Max, fitness age
- Intensity minutes (moderate + vigorous)
- Hydration (intake, goal, sweat loss)
- Blood pressure (if logged)

**Body Composition (per weigh-in)**:
- Weight, body fat %, hydration %, muscle mass, bone mass
- BMI, BMR, active metabolic rate, metabolic age
- Visceral fat rating, physique rating

**Activities (per activity, 28+ methods)**:
- Type, sport, duration, distance, pace, speed, calories
- HR avg/max + zones breakdown, power zones
- Cadence, stride, vertical oscillation, ground contact time
- Elevation gain/loss, GPS tracks
- Laps/splits detail, weather conditions
- Training load, aerobic/anaerobic training effect
- Self-evaluation (feel + effort)
- Gear used

**Performance Metrics**:
- VO2 Max (running + cycling), fitness age
- Race predictions (5K, 10K, half, full marathon)
- Lactate threshold (speed, HR, power)
- Cycling FTP
- Hill score, endurance score
- Personal records (all-time bests)

**Monitoring (per-minute from FIT files)**:
- Heart rate, SpO2, respiration rate
- Steps, intensity, activity type
- Elevation (ascent/descent)

### Data Available via GarminDB (30+ SQLite tables)

5 databases, pre-aggregated into day/week/month/year summaries with 50+ fields per summary row. All raw FIT file data preserved at record-level granularity.

---

## Appendix B: Exercise Science & Health Guidelines References

| Method / Guideline | Reference | Application |
|---------------------|-----------|-------------|
| TRIMP | Banister (1991) | Training load quantification |
| ATL/CTL/TSB Model | Coggan & Allen (2003) — Performance Management Chart | Fitness/fatigue/form modeling |
| ACWR | Gabbett (2016) | Injury risk monitoring |
| Monotony & Strain | Foster (1998) | Overtraining detection |
| Sleep Regularity Index | Phillips et al. (2017) | Sleep consistency scoring |
| Social Jet Lag | Wittmann et al. (2006) | Circadian disruption metric |
| FFMI | Kouri et al. (1995) | Body composition benchmark |
| Efficiency Factor | Friel — "Training Bible" | Aerobic fitness tracking |
| Pace Decoupling | Friel — "Training Bible" | Aerobic base test |
| HRR as mortality predictor | Cole et al. (1999) NEJM | Cardiovascular fitness |
| Sleep duration targets | National Sleep Foundation (2015) | 7–9h for adults 18–64 |
| Physical activity guidelines | WHO (2020) | 150 min moderate or 75 min vigorous/week |
| VO2 Max classification | ACSM's Guidelines for Exercise Testing (11th ed.) | Age/sex percentile tables |
| RHR fitness zones | AHA / ACSM | Cardiovascular fitness classification |
| Body fat % classification | ACSM (2021) | Age/sex-adjusted body composition categories |
| BMI classification | WHO | Underweight / normal / overweight / obese ranges |
| Visceral fat risk zones | WHO / Japanese Society of Internal Medicine | Health risk classification |
| Safe weight loss rate | ACSM Position Stand (2009) | ≤1 kg/week recommended |
| HRV normative data | Shaffer & Ginsberg (2017) | Age-adjusted HRV norms |
