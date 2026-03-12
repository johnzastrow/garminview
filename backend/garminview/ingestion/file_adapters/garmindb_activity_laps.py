import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


def _time_str_to_seconds_int(t: str | None) -> int | None:
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


class GarminDBActivityLapsAdapter(BaseAdapter):
    """Reads activity lap data from GarminDB's garmin_activities.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_activities.db"

    def source_name(self) -> str:
        return "garmindb:activity_laps"

    def target_table(self) -> str:
        return "activity_laps"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT l.activity_id, l.lap, l.start_time, l.elapsed_time,
                       l.distance, l.avg_hr, l.max_hr, l.avg_speed,
                       l.ascent, l.calories
                FROM activity_laps l
                JOIN activities a ON a.activity_id = l.activity_id
                WHERE a.start_time >= ? AND a.start_time <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                (
                    activity_id_raw, lap, start_time_str, elapsed_time,
                    distance, avg_hr, max_hr, avg_speed,
                    ascent, calories,
                ) = row

                try:
                    activity_id = int(activity_id_raw)
                except (TypeError, ValueError):
                    continue

                start_time = None
                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str[:19])
                    except ValueError:
                        pass

                yield {
                    "activity_id": activity_id,
                    "lap_index": lap,
                    "start_time": start_time,
                    "elapsed_time_s": _time_str_to_seconds_int(elapsed_time),
                    "distance_m": distance,
                    "avg_hr": avg_hr,
                    "max_hr": max_hr,
                    "avg_speed": avg_speed,
                    "ascent_m": ascent,
                    "calories": calories,
                }
        finally:
            conn.close()
