#!/bin/sh
set -e

# garmindb defaults its data dir to $HOME/HealthData. Point it at the mounted volume so
# downloads land where the GarminView ingestion reads them. Without this, garmindb writes to
# an empty $HOME/HealthData, finds no prior data, and re-downloads from 2012 (never
# finishing) while ingestion reads a stale /data/HealthData. Idempotent.
# (HOME is /home/garminview: the container runs as that user, not root.)
[ -L "$HOME/HealthData" ] || rm -rf "$HOME/HealthData"
ln -sfn /data/HealthData "$HOME/HealthData"
echo "==> Linked $HOME/HealthData -> /data/HealthData (garmindb data dir)"

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting GarminView API..."
exec uvicorn garminview.api.main:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
