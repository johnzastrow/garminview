"""
GarminDB vs GarminView comparison validation suite.

GarminDB data lives across multiple SQLite files:
  ~/HealthData/DBs/garmin.db            — daily_summary, sleep, weight, rhr, stress
  ~/HealthData/DBs/garmin_monitoring.db — monitoring_*
  ~/HealthData/DBs/garmin_activities.db — activities, activity_laps, activity_records

Usage:
    cd backend
    uv run python tests/validation/compare.py
    uv run python tests/validation/compare.py --tables daily_summary sleep
    uv run python tests/validation/compare.py --days 30
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Table map: table_name -> (garmindb_file, garmindb_table, garminview_table,
#                           key_cols, col_remap)
# col_remap maps garmindb column names to garminview column names where they differ.
# ---------------------------------------------------------------------------
GARMINDB_DIR = Path.home() / "HealthData" / "DBs"

TABLE_MAP = {
    "daily_summary": (
        GARMINDB_DIR / "garmin.db",
        "daily_summary",
        "daily_summary",
        ["day"],           # GarminDB key col; renamed to "date" via remap below
        {
            "day": "date",
            "steps": "steps",
            # distance excluded: GarminDB=miles, garminview=meters (different units)
            "hr_min": "hr_min",
            "hr_max": "hr_max",
            "stress_avg": "stress_avg",
            "bb_max": "body_battery_max",
            "bb_min": "body_battery_min",
            "spo2_avg": "spo2_avg",
            "rr_waking_avg": "respiration_avg",
        },
    ),
    "resting_heart_rate": (
        GARMINDB_DIR / "garmin.db",
        "resting_hr",
        "resting_heart_rate",
        ["day"],
        {"day": "date", "rhr": "rhr"},
    ),
    "sleep": (
        GARMINDB_DIR / "garmin.db",
        "sleep",
        "sleep",
        ["day"],
        {
            "day": "date",
            "total_sleep": "total_sleep_s",
            "deep_sleep": "deep_sleep_s",
            "light_sleep": "light_sleep_s",
            "rem_sleep": "rem_sleep_s",
            "awake": "awake_s",
        },
    ),
    "weight": (
        GARMINDB_DIR / "garmin.db",
        "weight",
        "weight",
        ["day"],
        {
            "day": "date",
            # weight excluded: GarminDB=lbs, garminview=kg (different units)
        },
    ),
    "activities": (
        GARMINDB_DIR / "garmin_activities.db",
        "activities",
        "activities",
        ["activity_id"],
        {
            "name": "name",
            "sport": "sport",
            "start_time": "start_time",
            "elapsed_time_secs": "elapsed_time_s",
            "moving_time_secs": "moving_time_s",
            "distance": "distance_m",
            "calories": "calories",
            "avg_hr": "avg_hr",
            "max_hr": "max_hr",
        },
    ),
    "monitoring_heart_rate": (
        GARMINDB_DIR / "garmin_monitoring.db",
        "monitoring_hr",
        "monitoring_heart_rate",
        ["timestamp"],
        {"heart_rate": "hr"},
    ),
}


def _garminview_engine():
    """Connect to garminview DB using project config (supports SQLite and MariaDB)."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from garminview.core.config import get_config
    from garminview.core.database import create_db_engine
    cfg = get_config()
    return create_db_engine(cfg)


def compare_table(
    gdb_engine,
    gv_engine,
    gdb_table: str,
    gv_table: str,
    key_cols: list[str],
    col_remap: dict,
    days: int | None = None,
) -> dict:
    # Build column selection — only columns that exist in both systems
    gv_col_map = {k: v for k, v in col_remap.items() if v is not None}

    df_gdb = pd.read_sql_table(gdb_table, gdb_engine)
    df_gv = pd.read_sql_table(gv_table, gv_engine)

    # Rename GarminDB columns to garminview names
    df_gdb = df_gdb.rename(columns=gv_col_map)

    # Align on key cols (use garminview names after rename)
    gv_key_cols = [gv_col_map.get(k, k) for k in key_cols]

    # Optionally restrict to recent N days
    date_col = gv_key_cols[0]
    if days is not None and date_col in df_gdb.columns:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        try:
            df_gdb[date_col] = pd.to_datetime(df_gdb[date_col], format="mixed")
            df_gv[date_col] = pd.to_datetime(df_gv[date_col], format="mixed")
            df_gdb = df_gdb[df_gdb[date_col] >= cutoff]
            df_gv = df_gv[df_gv[date_col] >= cutoff]
        except Exception:
            pass

    df_gdb = df_gdb.set_index(gv_key_cols).sort_index()
    df_gv = df_gv.set_index(gv_key_cols).sort_index()

    # Only compare columns that exist in both
    common_cols = [v for v in gv_col_map.values() if v and v in df_gdb.columns and v in df_gv.columns]
    numeric_cols = [c for c in common_cols if pd.api.types.is_numeric_dtype(df_gdb[c])]

    diff = pd.DataFrame()
    if numeric_cols:
        _gdb_num = df_gdb[numeric_cols].reindex(df_gv.index)
        _gv_num = df_gv[numeric_cols]
        diff = (_gdb_num - _gv_num).abs()

    max_diff = diff.max().to_dict() if not diff.empty else {}
    all_match = (diff.max().max() < 0.5 if not diff.empty else True) and len(df_gdb) == len(df_gv)

    return {
        "garmindb_rows": len(df_gdb),
        "garminview_rows": len(df_gv),
        "missing_in_garminview": max(0, len(df_gdb) - len(df_gv)),
        "max_diff_per_col": max_diff,
        "match": all_match,
    }


def run_comparison(tables: list[str], days: int | None = None) -> int:
    gv_engine = _garminview_engine()
    exit_code = 0

    for table in tables:
        if table not in TABLE_MAP:
            print(f"[SKIP] No mapping for '{table}'. Known: {list(TABLE_MAP)}")
            continue

        gdb_path, gdb_table, gv_table, key_cols, col_remap = TABLE_MAP[table]

        if not Path(gdb_path).exists():
            print(f"[SKIP] {table}: GarminDB file not found: {gdb_path}")
            continue

        gdb_engine = create_engine(f"sqlite:///{gdb_path}")

        try:
            result = compare_table(gdb_engine, gv_engine, gdb_table, gv_table,
                                   key_cols, col_remap, days=days)
        except Exception as e:
            print(f"[ERROR] {table}: {e}")
            exit_code = 1
            continue

        status = "PASS" if result["match"] else "FAIL"
        scope = f"(last {days}d)" if days else "(all time)"
        print(f"\n{'─'*50}")
        print(f"  {table} {scope}  →  {status}")
        if table == "monitoring_heart_rate":
            print("  ⚠ Note: GarminDB stores monitoring timestamps in local time;")
            print("    garminview stores UTC. Row counts may differ due to TZ shift.")
        print(f"  GarminDB rows:   {result['garmindb_rows']:,}")
        print(f"  GarminView rows: {result['garminview_rows']:,}")
        if result["missing_in_garminview"]:
            print(f"  Missing in GV:   {result['missing_in_garminview']:,}")
        if result["max_diff_per_col"]:
            notable = {c: v for c, v in result["max_diff_per_col"].items()
                       if v is not None and not pd.isna(v) and v > 0}
            if notable:
                print("  Max numeric diff per column:")
                for col, diff in sorted(notable.items(), key=lambda x: -x[1]):
                    print(f"    {col}: {diff:.4f}")
        if not result["match"]:
            exit_code = 1

    print(f"\n{'─'*50}")
    print("Overall:", "PASS" if exit_code == 0 else "FAIL")
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare GarminDB vs GarminView")
    parser.add_argument("--tables", nargs="+", default=list(TABLE_MAP),
                        help=f"Tables to compare. Choices: {list(TABLE_MAP)}")
    parser.add_argument("--days", type=int, default=None,
                        help="Only compare last N days (default: all time)")
    args = parser.parse_args()
    sys.exit(run_comparison(args.tables, days=args.days))


if __name__ == "__main__":
    main()
