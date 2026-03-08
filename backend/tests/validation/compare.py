"""
GarminDB vs GarminView comparison validation suite.

Usage:
    python tests/validation/compare.py \\
      --garmindb-path ~/HealthData/DBs/garmin.db \\
      --garminview-path garminview.db \\
      --tables daily_summary sleep weight resting_heart_rate
"""
import argparse
import sys

import pandas as pd
from sqlalchemy import create_engine

TABLE_MAP = {
    # garmindb_table -> garminview_table, key_cols
    "daily_summary": ("daily_summary", ["date"]),
    "sleep": ("sleep", ["date"]),
    "weight": ("weight", ["date"]),
    "resting_heart_rate": ("resting_heart_rate", ["date"]),
}


def compare_table(
    garmindb_engine,
    garminview_engine,
    garmindb_table: str,
    garminview_table: str,
    key_cols: list[str],
) -> dict:
    df_gdb = pd.read_sql_table(garmindb_table, garmindb_engine)
    df_gv = pd.read_sql_table(garminview_table, garminview_engine)

    df_gdb = df_gdb.set_index(key_cols).sort_index()
    df_gv = df_gv.set_index(key_cols).sort_index()

    common_cols = list(set(df_gdb.columns) & set(df_gv.columns))
    numeric_cols = [c for c in common_cols if pd.api.types.is_numeric_dtype(df_gdb[c])]

    diff = pd.DataFrame()
    if numeric_cols:
        _gdb_num = df_gdb[numeric_cols].reindex(df_gv.index)
        _gv_num = df_gv[numeric_cols]
        diff = (_gdb_num - _gv_num).abs()

    return {
        "garmindb_rows": len(df_gdb),
        "garminview_rows": len(df_gv),
        "missing_in_garminview": len(df_gdb) - len(df_gv),
        "max_diff_per_col": diff.max().to_dict() if not diff.empty else {},
        "match": (diff.max().max() < 0.01 if not diff.empty else True) and len(df_gdb) == len(df_gv),
    }


def run_comparison(garmindb_path: str, garminview_path: str, tables: list[str]) -> int:
    gdb_engine = create_engine(f"sqlite:///{garmindb_path}")
    gv_engine = create_engine(f"sqlite:///{garminview_path}")

    exit_code = 0
    for table in tables:
        if table not in TABLE_MAP:
            print(f"[SKIP] Unknown table mapping for '{table}'. Known: {list(TABLE_MAP)}")
            continue
        gv_table, key_cols = TABLE_MAP[table]
        print(f"\n--- {table} ---")
        result = compare_table(gdb_engine, gv_engine, table, gv_table, key_cols)
        print(f"  GarminDB rows:   {result['garmindb_rows']}")
        print(f"  GarminView rows: {result['garminview_rows']}")
        print(f"  Missing in GV:   {result['missing_in_garminview']}")
        if result["max_diff_per_col"]:
            print("  Max numeric diff per column:")
            for col, diff in result["max_diff_per_col"].items():
                print(f"    {col}: {diff:.4f}")
        status = "PASS" if result["match"] else "FAIL"
        print(f"  Result: {status}")
        if not result["match"]:
            exit_code = 1
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare GarminDB vs GarminView tables")
    parser.add_argument("--garmindb-path", required=True)
    parser.add_argument("--garminview-path", required=True)
    parser.add_argument("--tables", nargs="+", default=list(TABLE_MAP))
    args = parser.parse_args()

    sys.exit(run_comparison(args.garmindb_path, args.garminview_path, args.tables))


if __name__ == "__main__":
    main()
