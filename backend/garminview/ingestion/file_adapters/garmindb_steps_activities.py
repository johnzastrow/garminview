import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


def _time_str_to_seconds_float(t: str | None) -> float | None:
    """Convert GarminDB time string 'HH:MM:SS.ffffff' to total seconds as float."""
    if not t:
        return None
    try:
        parts = t.split(":")
        h, m = int(parts[0]), int(parts[1])
        s = float(parts[2])
        return h * 3600.0 + m * 60.0 + s
    except Exception:
        return None


class GarminDBStepsActivitiesAdapter(BaseAdapter):
    """Reads steps activity metrics from GarminDB's garmin_activities.db."""

    def __init__(self, health_data_dir: str | Path):
        self._db_path = Path(health_data_dir).expanduser() / "DBs" / "garmin_activities.db"

    def source_name(self) -> str:
        return "garmindb:steps_activities"

    def target_table(self) -> str:
        return "steps_activities"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT s.activity_id, s.avg_pace, s.avg_moving_pace, s.max_pace,
                       s.avg_steps_per_min, s.avg_step_length,
                       s.avg_vertical_oscillation, s.avg_vertical_ratio,
                       s.avg_gct_balance, s.avg_stance_time_percent, s.vo2_max
                FROM steps_activities s
                JOIN activities a ON a.activity_id = s.activity_id
                WHERE a.start_time >= ? AND a.start_time <= ?
                """,
                (str(start_date), str(end_date) + " 23:59:59"),
            )
            for row in cursor:
                (
                    activity_id_raw, avg_pace, avg_moving_pace, max_pace,
                    avg_steps_per_min, avg_step_length,
                    avg_vertical_oscillation, avg_vertical_ratio,
                    avg_gct_balance, avg_stance_time_percent, vo2_max,
                ) = row

                try:
                    activity_id = int(activity_id_raw)
                except (TypeError, ValueError):
                    continue

                yield {
                    "activity_id": activity_id,
                    "pace_avg": _time_str_to_seconds_float(avg_pace),
                    "pace_moving": _time_str_to_seconds_float(avg_moving_pace),
                    "pace_max": _time_str_to_seconds_float(max_pace),
                    "steps_per_min": avg_steps_per_min,
                    "step_length_m": avg_step_length,
                    "vertical_oscillation_mm": avg_vertical_oscillation,
                    "vertical_ratio_pct": avg_vertical_ratio,
                    "gct_ms": avg_gct_balance,
                    "stance_pct": avg_stance_time_percent,
                    "vo2max": vo2_max,
                }
        finally:
            conn.close()
