import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class ActivityJsonAdapter(BaseAdapter):
    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:activity_json"

    def target_table(self) -> str:
        return "activities"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        # Filter by mtime: --latest downloads only recent files with fresh timestamps.
        mtime_cutoff = start_date - timedelta(days=2)
        for path in sorted(self._data_dir.glob("activity_details_*.json")):
            if date.fromtimestamp(path.stat().st_mtime) >= mtime_cutoff:
                yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        activity_id = raw.get("activityId")
        if not activity_id:
            return
        s = raw.get("summaryDTO") or {}
        at = raw.get("activityTypeDTO") or {}
        start_gmt = s.get("startTimeGMT")
        start_time = None
        if start_gmt:
            try:
                start_time = datetime.fromisoformat(start_gmt.rstrip("Z")).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        elapsed = s.get("elapsedDuration") or s.get("duration") or 0
        yield {
            "activity_id": activity_id,
            "name": raw.get("activityName"),
            "type": at.get("typeKey"),
            "sport": at.get("typeKey"),
            "sub_sport": None,
            "start_time": start_time,
            "elapsed_time_s": int(elapsed),
            "moving_time_s": int(s.get("movingDuration") or 0),
            "distance_m": s.get("distance"),
            "calories": s.get("calories"),
            "avg_hr": s.get("averageHR"),
            "max_hr": s.get("maxHR"),
            "avg_cadence": s.get("averageRunCadence"),
            "avg_speed": s.get("averageSpeed"),
            "ascent_m": s.get("elevationGain"),
            "descent_m": s.get("elevationLoss"),
            "training_load": raw.get("trainingLoad"),
            "aerobic_effect": raw.get("aerobicTrainingEffect"),
            "anaerobic_effect": raw.get("anaerobicTrainingEffect"),
            "source": "garmin_api",
        }
