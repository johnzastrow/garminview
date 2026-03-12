#!/usr/bin/env python3
"""
Migrate garminview data from SQLite → MariaDB.

Uses INSERT IGNORE so it is safe to re-run; existing rows are kept as-is.

Usage:
    uv run python scripts/migrate_to_mariadb.py
    uv run python scripts/migrate_to_mariadb.py --dry-run
    uv run python scripts/migrate_to_mariadb.py --tables daily_summary sleep
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

# ---------------------------------------------------------------------------
# Tables to migrate, in a safe insertion order (parents before children).
# Config/schema tables are excluded — they start fresh on each install.
# ---------------------------------------------------------------------------
TABLES = [
    # Daily health
    "daily_summary",
    "sleep",
    "sleep_events",
    "weight",
    "stress",
    "resting_heart_rate",
    # Minute monitoring
    "monitoring_heart_rate",
    "monitoring_intensity",
    "monitoring_steps",
    "monitoring_respiration",
    "monitoring_pulse_ox",
    "monitoring_climb",
    # Activities
    "activities",
    "activity_laps",
    "activity_hr_zones",
    "steps_activities",
    "activity_records",      # largest table — chunked
    # Supplemental API
    "hrv_data",
    "training_readiness",
    "training_status",
    "body_battery_events",
    "vo2max",
    "race_predictions",
    "lactate_threshold",
    "hill_score",
    "endurance_score",
    "personal_records",
    "body_composition",
    "blood_pressure",
    "gear",
    "gear_stats",
    # Derived / analysis
    "daily_derived",
    "weekly_derived",
    "activity_derived",
    # Sync history
    "sync_log",
    "data_provenance",
]

# Rows per INSERT batch. activity_records rows are wide so keep this modest.
CHUNK_SIZE = 2000


def _insert_ignore(table, conn, keys, data_iter):
    """pandas to_sql method that uses INSERT IGNORE instead of INSERT."""
    from sqlalchemy.dialects.mysql import insert as mysql_insert

    rows = [dict(zip(keys, row)) for row in data_iter]
    if not rows:
        return
    stmt = mysql_insert(table.table).prefix_with("IGNORE").values(rows)
    conn.execute(stmt)


def migrate_table(table: str, src_engine, dst_engine, src_tables: set, dry_run: bool) -> tuple[int, int]:
    """Returns (rows_read, rows_inserted)."""
    if table not in src_tables:
        print(f"  ⚠  {table}: not in source — skipping")
        return 0, 0

    with src_engine.connect() as conn:
        total_rows = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
    if total_rows == 0:
        print(f"  –  {table}: empty — skipping")
        return 0, 0

    print(f"  →  {table}: {total_rows:,} rows", end="", flush=True)

    if dry_run:
        print(" (dry-run)")
        return total_rows, 0

    inserted = 0
    t0 = time.monotonic()

    for chunk_df in pd.read_sql_table(table, src_engine, chunksize=CHUNK_SIZE):
        # SQLite stores datetimes as strings; coerce to datetime where possible
        for col in chunk_df.select_dtypes(include=["object", "string"]).columns:
            try:
                chunk_df[col] = pd.to_datetime(chunk_df[col], utc=True)
            except Exception:
                pass  # leave as-is if not a datetime column

        chunk_df.to_sql(
            table,
            dst_engine,
            if_exists="append",
            index=False,
            method=_insert_ignore,
            chunksize=CHUNK_SIZE,
        )
        inserted += len(chunk_df)
        pct = inserted / total_rows * 100
        elapsed = time.monotonic() - t0
        print(f"\r  →  {table}: {inserted:,}/{total_rows:,} ({pct:.0f}%) [{elapsed:.1f}s]",
              end="", flush=True)

    print()  # newline after progress
    return total_rows, inserted


def main():
    parser = argparse.ArgumentParser(description="Migrate garminview SQLite → MariaDB")
    parser.add_argument("--dry-run", action="store_true", help="Count rows only, don't write")
    parser.add_argument("--tables", nargs="+", help="Only migrate these tables")
    args = parser.parse_args()

    # Load config from .env
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from garminview.core.config import get_config

    cfg = get_config()

    # Source: always SQLite
    sqlite_path = Path(cfg.db_path).expanduser()
    if not sqlite_path.exists():
        # Try relative to backend dir
        sqlite_path = Path(__file__).parent.parent / cfg.db_path
    if not sqlite_path.exists():
        print(f"ERROR: SQLite file not found: {sqlite_path}", file=sys.stderr)
        sys.exit(1)

    # Destination: MariaDB from config
    if cfg.db_backend.value != "mariadb":
        print("ERROR: GARMINVIEW_DB_BACKEND must be 'mariadb' in .env", file=sys.stderr)
        sys.exit(1)

    src_engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
    )
    dst_engine = create_engine(
        f"mysql+pymysql://{cfg.db_url}?charset=utf8mb4",
        pool_pre_ping=True,
    )

    # Verify connections
    try:
        src_engine.connect().execute(text("SELECT 1"))
        print(f"✓ Source: {sqlite_path}")
    except Exception as e:
        print(f"ERROR connecting to SQLite: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        dst_engine.connect().execute(text("SELECT 1"))
        print(f"✓ Destination: {cfg.db_url.split('@')[-1]}")
    except Exception as e:
        print(f"ERROR connecting to MariaDB: {e}", file=sys.stderr)
        sys.exit(1)

    src_tables = set(inspect(src_engine).get_table_names())

    tables = args.tables if args.tables else TABLES
    print(f"\nMigrating {len(tables)} tables {'(DRY RUN)' if args.dry_run else ''}...\n")

    total_read = total_written = 0
    t_start = time.monotonic()

    for table in tables:
        read, written = migrate_table(table, src_engine, dst_engine, src_tables, args.dry_run)
        total_read += read
        total_written += written

    elapsed = time.monotonic() - t_start
    print(f"\n{'─'*50}")
    print(f"Done in {elapsed:.1f}s — {total_read:,} rows read, {total_written:,} rows written")


if __name__ == "__main__":
    main()
