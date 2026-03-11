import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class GarminDBStressAdapter(BaseAdapter):
    """Reads stress data from GarminDB's garmin.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin.db"

    def source_name(self) -> str:
        return "garmindb:stress"

    def target_table(self) -> str:
        return "stress"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, stress
                FROM stress
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                ts_str, stress = row[0], row[1]
                if stress is None or stress < 0:
                    continue
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str[:19])
                except ValueError:
                    continue
                yield {
                    "timestamp": ts,
                    "stress_level": stress,
                }
        finally:
            conn.close()
