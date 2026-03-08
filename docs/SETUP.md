# GarminView — Setup Guide

This guide walks you through every step from a clean machine to a running GarminView stack.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 18+ | `node --version` |
| Git | for cloning GarminView |
| Garmin Connect account | username + password |

---

## Step 1 — Clone GarminView

```bash
mkdir -p ~/Github && cd ~/Github
git clone git@github.com:<you>/garminview.git
cd garminview
```

All subsequent steps can be run from this directory.

---

## Step 2 — Configure and run GarminDB

GarminDB is a PyPI package that downloads your Garmin data into `~/HealthData/`.
Install it once as a `uv` tool — no separate clone needed, available system-wide
from any directory.

### 2a. Install GarminDB

```bash
uv tool install garmindb
```

Verify: `garmindb_cli.py --version`

### 2b. Create GarminDB config

```bash
mkdir -p ~/.GarminDb
curl -o ~/.GarminDb/GarminConnectConfig.json \
  https://raw.githubusercontent.com/tcgoetz/GarminDB/master/garmindb/GarminConnectConfig.json.example
```

Open `~/.GarminDb/GarminConnectConfig.json` and fill in:

```json
{
    "credentials": {
        "user": "your-garmin-email@example.com",
        "password": "your-garmin-password"
    },
    "data": {
        "weight_start_date":     "12/31/2019",
        "sleep_start_date":      "12/31/2019",
        "rhr_start_date":        "12/31/2019",
        "monitoring_start_date": "12/31/2019",
        "download_latest_activities": 25,
        "download_all_activities":   1000
    },
    "directories": {
        "relative_to_home": true,
        "base_dir": "HealthData"
    }
}
```

**Tip:** Set the `*_start_date` fields to the earliest date you care about.
Earlier dates = more history but longer first download.

### 2c. Initial download (first time only)

```bash
garmindb_cli.py --all --download --import --analyze
```

This downloads all your history from Garmin Connect and imports it into
`~/HealthData/`. Expect 10–60 minutes depending on how much history you have
and your connection speed.

When it finishes, `~/HealthData/` will contain:

```
~/HealthData/
├── DBs/
│   ├── garmin.db          ← GarminDB's main SQLite database
│   ├── garmin_monitoring.db
│   └── garmin_activities.db
├── DailyData/             ← downloaded JSON files
├── Activities/            ← FIT activity files
├── Sleep/
├── Weight/
└── RHR/
```

### 2d. Incremental updates (daily / weekly)

```bash
garmindb_cli.py --all --download --import --analyze --latest
```

---

## Step 3 — Configure GarminView backend

```bash
cd ~/Github/garminview/backend
cp ../.env.example .env
```

Edit `.env`:

```dotenv
GARMINVIEW_DB_BACKEND=sqlite
GARMINVIEW_DB_PATH=garminview.db
GARMINVIEW_HEALTH_DATA_DIR=~/HealthData   # must match GarminDB "base_dir"
GARMINVIEW_LOG_LEVEL=INFO
GARMINVIEW_SECRET_KEY=change-me-to-something-random
```

> **MariaDB (optional):** Set `GARMINVIEW_DB_BACKEND=mariadb` and
> `GARMINVIEW_DB_URL=user:password@localhost:3306/garminview`.
> Create the database first: `CREATE DATABASE garminview CHARACTER SET utf8mb4;`

---

## Step 4 — Install backend and run migrations

```bash
cd ~/Github/garminview/backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uv run alembic upgrade head
```

Alembic creates all tables in `garminview.db` (or MariaDB).

---

## Step 5 — Ingest your data

This reads the raw files from `~/HealthData/` and populates `garminview.db`.

```bash
cd ~/Github/garminview/backend
uv run python - <<'EOF'
from datetime import date
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory
from garminview.ingestion.orchestrator import IngestionOrchestrator

cfg = get_config()
engine = create_db_engine(cfg)
with get_session_factory(engine)() as session:
    orch = IngestionOrchestrator(session, cfg.health_data_dir)
    orch.run_full(date(2020, 1, 1), date.today())   # adjust start date as needed
EOF
```

For subsequent runs (incremental):

```bash
uv run python - <<'EOF'
from datetime import date, timedelta
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory
from garminview.ingestion.orchestrator import IngestionOrchestrator

cfg = get_config()
engine = create_db_engine(cfg)
with get_session_factory(engine)() as session:
    orch = IngestionOrchestrator(session, cfg.health_data_dir)
    orch.run_incremental(date.today() - timedelta(days=7), date.today())
EOF
```

---

## Step 6 — Start the backend

```bash
cd ~/Github/garminview/backend
uv run uvicorn garminview.api.main:create_app --factory --reload --port 8000
```

Verify: `curl http://localhost:8000/` → `{"status":"ok","version":"1.0.0"}`

API docs available at: `http://localhost:8000/docs`

---

## Step 7 — Start the frontend

```bash
cd ~/Github/garminview/frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Step 8 — (Optional) Marimo notebooks

The notebooks in `backend/notebooks/` use the same database via the shared
`get_notebook_session()` helper.

```bash
cd ~/Github/garminview/backend
uv pip install marimo altair pandas scipy

# Interactive browser UI
uv run marimo edit notebooks/health_explorer.py
uv run marimo edit notebooks/training_load.py
uv run marimo edit notebooks/activity_explorer.py
uv run marimo edit notebooks/correlation_explorer.py

# Non-interactive (script mode, for testing)
uv run notebooks/health_explorer.py
```

---

## Keeping everything current

Run this sequence whenever you want fresh data (automate with cron or systemd):

```bash
# 1. Download latest from Garmin Connect
garmindb_cli.py --all --download --import --analyze --latest

# 2. Ingest into garminview (last 7 days)
cd ~/Github/garminview/backend
uv run python -c "
from datetime import date, timedelta
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory
from garminview.ingestion.orchestrator import IngestionOrchestrator
cfg = get_config()
engine = create_db_engine(cfg)
with get_session_factory(engine)() as s:
    IngestionOrchestrator(s, cfg.health_data_dir).run_incremental(
        date.today() - timedelta(days=7), date.today()
    )
"
```

### Example cron (daily at 06:00)

```cron
0 6 * * * garmindb_cli.py --all --download --import --analyze --latest >> ~/garmindb.log 2>&1
5 6 * * * cd ~/Github/garminview/backend && .venv/bin/python -c "..." >> ~/garminview.log 2>&1
```

---

## Troubleshooting

### "No such table" errors

Run `uv run alembic upgrade head` — migrations haven't been applied yet.

### GarminDB login fails / MFA prompt

Garmin Connect sometimes requires MFA on first login. Run the CLI directly in
your terminal so you can respond to the prompt:

```bash
garmindb_cli.py --all --download --import --analyze --latest
```

Follow the on-screen MFA prompt. Subsequent runs will use the cached session.

### `~/HealthData` not found / wrong path

Check that `GARMINVIEW_HEALTH_DATA_DIR` in `.env` matches `base_dir` in
`~/.GarminDb/GarminConnectConfig.json`. Both default to `~/HealthData`.

### Frontend can't reach backend

Set `VITE_API_URL` in `frontend/.env.local`:

```dotenv
VITE_API_URL=http://localhost:8000
```

### Run backend tests

```bash
cd ~/Github/garminview/backend
uv run pytest -q
```

### Validate garminview data against GarminDB

```bash
cd ~/Github/garminview/backend
uv run python tests/validation/compare.py \
  --garmindb-path ~/HealthData/DBs/garmin.db \
  --garminview-path garminview.db \
  --tables daily_summary sleep weight resting_heart_rate
```
