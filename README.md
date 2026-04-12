# GarminView

A personal Garmin fitness data platform: download your full history, store it locally, and explore it through dashboards, interactive notebooks, and automated reports.

**Version: v0.9.1** | **Stack:** Python 3.10+ · FastAPI · SQLAlchemy 2 · Vue.js 3 · ECharts · Marimo · SQLite (or MariaDB)

---

## How it works

```
Garmin Connect
      │
      ▼
  GarminDB  ──── downloads FIT/JSON files ──▶  ~/HealthData/
      │
      ▼
garminview backend
  ├── ingestion adapters  (reads ~/HealthData → garminview.db)
  ├── analysis engine     (TRIMP, ATL/CTL/TSB, sleep science, …)
  └── FastAPI REST + SSE
      │
      ▼
Vue.js frontend  ──  dashboards, charts, export, admin
      +
Marimo notebooks  ──  ad-hoc exploration
```

---

## Quick links

| Document | Purpose |
|----------|---------|
| [docs/SETUP.md](docs/SETUP.md) | Full setup walkthrough — start here |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Complete database schema reference + data dictionary |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Feature requirements & architecture |
| [docs/DATA_SOURCE_ANALYSIS.md](docs/DATA_SOURCE_ANALYSIS.md) | Data source mapping |
| [.env.example](.env.example) | Backend environment variables |

---

## At a glance

```bash
cd ~/Github/garminview

# 1. Download Garmin data (one-time — runs from anywhere)
uv tool install garmindb
# edit ~/.GarminDb/GarminConnectConfig.json with your credentials
garmindb_cli.py --all --download --import --analyze

# 2. Ingest into garminview + start backend
cd backend
cp ../.env.example .env   # edit GARMINVIEW_HEALTH_DATA_DIR
uv run alembic upgrade head
uv run uvicorn garminview.api.main:create_app --factory --reload --port 8000

# 3. Start frontend
cd ../frontend && npm install && npm run dev   # → http://localhost:5173

# 4. Keep data current (daily)
cd ~/Github/GarminDB && make   # incremental update
```

See **[docs/SETUP.md](docs/SETUP.md)** for the full walkthrough.

---

## Features (v0.9.1)

- **Garmin Connect sync** -- bulk download via GarminDB + real-time API (10 adapters, rate-limited)
- **MyFitnessPal import** -- ZIP upload with nutrition, measurements, exercise data
- **MFP backfill** -- cross-populate weight and body composition from MFP into main tables
- **Dashboards** -- Sleep, Cardiovascular, Weight/Body Comp, Activity Summary, Recovery/Stress, Running, Max HR Aging, Nutrition
- **Analysis engine** -- derived metrics (TRIMP, ATL/CTL/TSB), trend classification, data quality checks
- **Admin UI** -- credential management, sync scheduling, file uploads, backfill controls
- **Scheduled sync** -- APScheduler with DB-driven cron, hot-reload on config change
- **Docker deployment** -- backend + Caddy frontend, external MariaDB

### Upcoming

- Polar Flow GDPR export import (26 staging tables)
- HR Zones chart (age-adapted Karvonen zones)
- Data Management Tasks Panel
- Actalog Review Workflow
