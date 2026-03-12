#!/bin/sh
set -e

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting GarminView API..."
exec uvicorn garminview.api.main:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
