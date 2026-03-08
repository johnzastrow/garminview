"""
Run GarminDB pipeline to populate garmin.db for comparison.

Usage:
    cd /path/to/GarminDB
    python /path/to/tests/validation/run_garmindb.py --health-data-dir ~/HealthData
"""
import argparse
import subprocess
import sys
from pathlib import Path

GARMINDB_DIR = Path.home() / "Github" / "GarminDB"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GarminDB pipeline")
    parser.add_argument("--health-data-dir", default=str(Path.home() / "HealthData"))
    parser.add_argument("--garmindb-dir", default=str(GARMINDB_DIR))
    args = parser.parse_args()

    result = subprocess.run(
        [
            sys.executable, "-m", "garmindb_cli.garmindb",
            "--all", "--download", "--import", "--analyze",
            "--latest",
        ],
        cwd=args.garmindb_dir,
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
