#!/bin/sh
set -e

# garmindb defaults its data dir to $HOME/HealthData (= /root/HealthData). Point it at the
# mounted volume so downloads land where the GarminView ingestion reads them. Without this,
# garmindb writes to an empty /root/HealthData, finds no prior data, and re-downloads from
# 2012 (never finishing) while ingestion reads a stale /data/HealthData. Idempotent.
[ -L /root/HealthData ] || rm -rf /root/HealthData
ln -sfn /data/HealthData /root/HealthData
echo "==> Linked /root/HealthData -> /data/HealthData (garmindb data dir)"

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting GarminView API..."
exec uvicorn garminview.api.main:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
