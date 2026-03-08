# GarminView

A personal Garmin fitness data platform: download your full history, store it locally, and explore it through dashboards, interactive notebooks, and automated reports.

**Stack:** Python 3.10+ · FastAPI · SQLAlchemy 2 · Vue.js 3 · ECharts · Marimo · SQLite (or MariaDB)

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
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Feature requirements & architecture |
| [docs/DATA_SOURCE_ANALYSIS.md](docs/DATA_SOURCE_ANALYSIS.md) | Data source mapping |
| [.env.example](.env.example) | Backend environment variables |

---

## At a glance

```bash
# 1. Download Garmin data (one-time)
cd ~/Github/GarminDB && make setup && make create_dbs

# 2. Ingest into garminview + start backend
cd ~/Github/garminview/backend
cp ../.env.example .env   # edit GARMINVIEW_HEALTH_DATA_DIR
uv run alembic upgrade head
uv run uvicorn garminview.api.main:create_app --factory --reload --port 8000

# 3. Start frontend
cd ../frontend && npm install && npm run dev   # → http://localhost:5173

# 4. Keep data current (daily)
cd ~/Github/GarminDB && make   # incremental update
```

See **[docs/SETUP.md](docs/SETUP.md)** for the full walkthrough.
