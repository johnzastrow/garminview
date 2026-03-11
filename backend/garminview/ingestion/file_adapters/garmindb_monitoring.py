import sqlite3
from datetime import date, datetime
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


def _parse_ts(ts: str) -> datetime:
    """Parse GarminDB timestamp '2025-08-18 00:01:00.000000' to datetime."""
    return datetime.fromisoformat(ts[:19])


class GarminDBRespirationAdapter(BaseAdapter):
    """Reads respiration (RR interval) data from GarminDB's garmin_monitoring.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_monitoring.db"

    def source_name(self) -> str:
        return "garmindb:monitoring_rr"

    def target_table(self) -> str:
        return "monitoring_respiration"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, rr
                FROM monitoring_rr
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                yield {
                    "timestamp": _parse_ts(row[0]),
                    "rr": row[1],
                }
        finally:
            conn.close()


class GarminDBPulseOxAdapter(BaseAdapter):
    """Reads pulse oximetry data from GarminDB's garmin_monitoring.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_monitoring.db"

    def source_name(self) -> str:
        return "garmindb:monitoring_pulse_ox"

    def target_table(self) -> str:
        return "monitoring_pulse_ox"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, pulse_ox
                FROM monitoring_pulse_ox
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                yield {
                    "timestamp": _parse_ts(row[0]),
                    "spo2": row[1],
                }
        finally:
            conn.close()


class GarminDBClimbAdapter(BaseAdapter):
    """Reads climb/descent data from GarminDB's garmin_monitoring.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_monitoring.db"

    def source_name(self) -> str:
        return "garmindb:monitoring_climb"

    def target_table(self) -> str:
        return "monitoring_climb"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, ascent, descent, cum_ascent, cum_descent
                FROM monitoring_climb
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                yield {
                    "timestamp": _parse_ts(row[0]),
                    "ascent_m": row[1],
                    "descent_m": row[2],
                    "cum_ascent_m": row[3],
                    "cum_descent_m": row[4],
                }
        finally:
            conn.close()


class GarminDBIntensityAdapter(BaseAdapter):
    """Reads intensity minute data from GarminDB's garmin_monitoring.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_monitoring.db"

    def source_name(self) -> str:
        return "garmindb:monitoring_intensity"

    def target_table(self) -> str:
        return "monitoring_intensity"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, moderate_activity_time, vigorous_activity_time
                FROM monitoring_intensity
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                yield {
                    "timestamp": _parse_ts(row[0]),
                    "moderate_time_s": _time_str_to_seconds(row[1]),
                    "vigorous_time_s": _time_str_to_seconds(row[2]),
                }
        finally:
            conn.close()


class GarminDBStepsAdapter(BaseAdapter):
    """Reads per-minute steps data from GarminDB's garmin_monitoring.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_monitoring.db"

    def source_name(self) -> str:
        return "garmindb:monitoring_steps"

    def target_table(self) -> str:
        return "monitoring_steps"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT timestamp, steps, activity_type
                FROM monitoring
                WHERE timestamp >= ? AND timestamp <= ?
                  AND steps IS NOT NULL
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                yield {
                    "timestamp": _parse_ts(row[0]),
                    "steps": row[1],
                    "activity_type": row[2],
                }
        finally:
            conn.close()
