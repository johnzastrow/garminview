import fitparse
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class ActivityFitAdapter(BaseAdapter):
    """Parses activity FIT files → activity_records, activity_laps, steps_activities, activity_hr_zones."""

    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:activity_fit"

    def target_table(self) -> str:
        return "activity_records"  # primary; laps/zones written by orchestrator

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        # GarminDB names activity FIT files *_ACTIVITY.fit.
        # Filter by file mtime: --latest downloads only recent files, so newly downloaded
        # files have a recent mtime. Add a 2-day buffer to avoid missing edge cases.
        mtime_cutoff = start_date - timedelta(days=2)
        for path in sorted(self._data_dir.glob("*_ACTIVITY.fit")):
            if date.fromtimestamp(path.stat().st_mtime) >= mtime_cutoff:
                yield from self._parse_fit(path)

    def _parse_fit(self, path: Path) -> Iterator[dict]:
        try:
            ff = fitparse.FitFile(str(path))
            activity_id = None
            for msg in ff.get_messages("session"):
                data = {f.name: f.value for f in msg}
                activity_id = data.get("activity_id") or hash(str(path))

            record_index = 0
            for msg in ff.get_messages("record"):
                data = {f.name: f.value for f in msg}
                yield {
                    "type": "record",
                    "activity_id": activity_id,
                    "record_index": record_index,
                    "timestamp": data.get("timestamp"),
                    "lat": data.get("position_lat"),
                    "lon": data.get("position_long"),
                    "distance_m": data.get("distance"),
                    "hr": data.get("heart_rate"),
                    "cadence": data.get("cadence"),
                    "altitude_m": data.get("altitude"),
                    "speed": data.get("speed"),
                    "power": data.get("power"),
                }
                record_index += 1
        except Exception as e:
            from garminview.core.logging import get_logger
            get_logger(__name__).warning("fit_parse_error", path=str(path), error=str(e))
