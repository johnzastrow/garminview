# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Current Version

**v0.10.0** (source of truth: `backend/pyproject.toml`)

## Project Overview

**garminview** — A Garmin fitness data harvesting and analysis tool that combines:
- **`python-garminconnect`** (API wrapper) for live data access and real-time pulls
- **`GarminDB`** (pipeline + SQLite storage) for bulk download, parsing, and historical analysis

## Related Projects

| Project | Location | Role |
|---------|----------|------|
| python-garminconnect | `/home/jcz/Github/python-garminconnect` | Garmin Connect API wrapper |
| GarminDB | `/home/jcz/Github/GarminDB` | Download pipeline + SQLite storage |

## Requirements

See `REQUIREMENTS.md` for full project requirements.

## Versioning and Releases

**Single source of truth:** `backend/pyproject.toml` → `version = "X.Y.Z"`

Increment the version whenever any code changes are committed:
- **Patch** (Z): bug fixes, dependency updates, small config tweaks
- **Minor** (Y): new features, new API endpoints, new dashboard views
- **Major** (X): breaking schema changes, major architectural changes

### Release process

After making and committing code changes:

```bash
# 1. Bump version in backend/pyproject.toml
# 2. Commit the bump
git add backend/pyproject.toml
git commit -m "chore: bump version to vX.Y.Z"

# 3. Tag and push — this triggers the GitHub Actions release workflow
git tag vX.Y.Z
git push && git push --tags
```

The `release.yml` workflow automatically:
- Builds `ghcr.io/johnzastrow/garminview-backend:vX.Y.Z` and `:latest`
- Builds `ghcr.io/johnzastrow/garminview-frontend:vX.Y.Z` and `:latest`
- Creates a GitHub Release with deploy instructions

### Docker deployment

See `docker-compose.yml` and `docs/SETUP.md` → "Docker deployment" section.

- Backend: `backend/Dockerfile` + `backend/entrypoint.sh` (runs migrations then uvicorn)
- Frontend: `frontend/Dockerfile` + `frontend/Caddyfile` (Caddy serves static files + proxies API)
- MariaDB runs on an external host — no DB container in compose

## QA commands

```bash
cd backend
uv run pytest -q                                    # unit + integration tests
uv run python tests/validation/compare.py          # validate against GarminDB
curl http://localhost:8000/health/daily?days=7     # smoke test API
```

## Production Database

MariaDB on external host — connection configured via `GARMINVIEW_DB_URL` in `.env`.
Format: `user:password@host:port/dbname`

## Key Implementation Patterns

### FIT file timestamp_16 resolution
When parsing FIT monitoring files, `timestamp_16` values are 16-bit offsets from
a base `timestamp` record. Always resolve them using the last seen full `timestamp`
field. Dropping the base timestamp causes ~80% of records to store NULL heart rate.
See `MonitoringFitAdapter` for the reference implementation.

### GarminDB CLI flags
Never pass `--analyze` to `garmindb_cli.py` — it re-analyzes the entire DB and
was ~80% of total sync time. Only use `--all --download --import --latest`.

### Column naming conventions (match live MariaDB)
- Short: `hr` not `heart_rate`, `lat`/`lon` not `latitude`/`longitude`
- Speed: `avg_speed` not `avg_speed_ms`
- Elevation: `ascent_m`/`descent_m` not `total_ascent_m`/`total_descent_m`

# currentDate
Today's date is 2026-04-08.
