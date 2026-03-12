import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


def _time_str_to_minutes(t: str | None) -> int | None:
    """Convert GarminDB time string 'HH:MM:SS.ffffff' to integer minutes."""
    if not t:
        return None
    try:
        parts = t.split(":")
        h, m = int(parts[0]), int(parts[1])
        s = float(parts[2])
        total_seconds = h * 3600 + m * 60 + s
        return int(total_seconds // 60)
    except Exception:
        return None


class GarminDBSleepEventsAdapter(BaseAdapter):
    """Reads sleep event data from GarminDB's garmin.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin.db"

    def source_name(self) -> str:
        return "garmindb:sleep_events"

    def target_table(self) -> str:
        return "sleep_events"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, event, duration
                FROM sleep_events
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                ts_str, event, duration = row[0], row[1], row[2]
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str[:19])
                except ValueError:
                    continue
                yield {
                    "date": ts.date(),
                    "event_type": (event or "")[:16],
                    "start": ts,
                    "duration_min": _time_str_to_minutes(duration),
                }
        finally:
            conn.close()
