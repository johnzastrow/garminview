#!/usr/bin/env bash
set -e
cd ~/Github/garminview/backend

cat > /tmp/ingest.py << 'EOF'
from datetime import date
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory
from garminview.ingestion.orchestrator import IngestionOrchestrator
cfg = get_config()
engine = create_db_engine(cfg)
with get_session_factory(engine)() as s:
    IngestionOrchestrator(s, cfg.health_data_dir).run_full(date(2012, 1, 1), date.today())
EOF

uv run python /tmp/ingest.py
