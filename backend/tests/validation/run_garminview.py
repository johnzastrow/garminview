"""
Run GarminView ingestion pipeline to populate garminview.db for comparison.

Usage:
    cd backend
    uv run python tests/validation/run_garminview.py --start 2024-01-01 --end 2024-12-31
"""
import argparse
import sys
from datetime import date


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GarminView ingestion pipeline")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=str(date.today()))
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    from garminview.core.config import get_config
    from garminview.core.database import create_db_engine, get_session_factory
    from garminview.ingestion.orchestrator import IngestionOrchestrator

    cfg = get_config()
    engine = create_db_engine(cfg)
    factory = get_session_factory(engine)

    with factory() as session:
        orch = IngestionOrchestrator(session, cfg.health_data_dir)
        orch.run_full(start, end)

    print(f"Ingestion complete: {start} → {end}")
    sys.exit(0)


if __name__ == "__main__":
    main()
