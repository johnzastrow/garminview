import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


def _time_str_to_seconds(t: str | None) -> int | None:
    """Convert GarminDB time string 'HH:MM:SS.ffffff' to integer seconds."""
    if not t:
        return None
    try:
        parts = t.split(":")
        h, m = int(parts[0]), int(parts[1])
        s = float(parts[2])
        return int(h * 3600 + m * 60 + s)
    except Exception:
        return None


class GarminDBHRZonesAdapter(BaseAdapter):
    """Reads pre-parsed HR zone data from GarminDB's garmin_activities.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_activities.db"

    def source_name(self) -> str:
        return "garmindb:hr_zones"

    def target_table(self) -> str:
        return "activity_hr_zones"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT activity_id, start_time,
                       hrz_1_time, hrz_2_time, hrz_3_time, hrz_4_time, hrz_5_time
                FROM activities
                WHERE start_time >= ? AND start_time <= ?
                  AND hrz_1_time IS NOT NULL
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                activity_id = int(row[0])
                zone_times = row[2:7]
                for zone_num, time_str in enumerate(zone_times, start=1):
                    secs = _time_str_to_seconds(time_str)
                    if secs is not None:
                        yield {
                            "activity_id": activity_id,
                            "zone": zone_num,
                            "time_in_zone_s": secs,
                        }
        finally:
            conn.close()
