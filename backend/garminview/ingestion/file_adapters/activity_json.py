import json
from datetime import date, datetime, timezone
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
        for path in sorted(self._data_dir.glob("activity_details_*.json")):
            yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        activity_id = raw.get("activityId")
        if not activity_id:
            return
        begin_ts = raw.get("beginTimestamp")
        yield {
            "activity_id": activity_id,
            "name": raw.get("activityName"),
            "type": (raw.get("activityType") or {}).get("typeKey"),
            "sport": raw.get("sport"),
            "sub_sport": raw.get("subSport"),
            "start_time": datetime.fromtimestamp(begin_ts / 1000, tz=timezone.utc) if begin_ts else None,
            "elapsed_time_s": int(raw.get("duration", 0)),
            "moving_time_s": int(raw.get("movingDuration", 0)),
            "distance_m": raw.get("distance"),
            "calories": raw.get("calories"),
            "avg_hr": raw.get("averageHR"),
            "max_hr": raw.get("maxHR"),
            "avg_cadence": raw.get("averageRunCadence"),
            "avg_speed": raw.get("averageSpeed"),
            "ascent_m": raw.get("elevationGain"),
            "descent_m": raw.get("elevationLoss"),
            "training_load": raw.get("trainingLoad"),
            "aerobic_effect": raw.get("aerobicTrainingEffect"),
            "anaerobic_effect": raw.get("anaerobicTrainingEffect"),
            "source": "garmin_api",
        }
