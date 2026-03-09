import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class SleepAdapter(BaseAdapter):
    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:sleep"

    def target_table(self) -> str:
        return "sleep"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        for path in sorted(self._data_dir.glob("*.json")):
            yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        # All sleep fields are nested under dailySleepDTO
        dto = raw.get("dailySleepDTO", {})
        d = dto.get("calendarDate")
        if not d:
            return
        day = date.fromisoformat(d)

        start_ts = dto.get("sleepStartTimestampGMT")
        end_ts = dto.get("sleepEndTimestampGMT")
        scores = dto.get("sleepScores", {})
        overall = scores.get("overall", {}) if isinstance(scores, dict) else {}

        yield {
            "date": day,
            "start": datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc) if start_ts else None,
            "end": datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc) if end_ts else None,
            "total_sleep_min": (dto.get("deepSleepSeconds", 0) + dto.get("lightSleepSeconds", 0)
                                + dto.get("remSleepSeconds", 0)) // 60,
            "deep_sleep_min": (dto.get("deepSleepSeconds") or 0) // 60,
            "light_sleep_min": (dto.get("lightSleepSeconds") or 0) // 60,
            "rem_sleep_min": (dto.get("remSleepSeconds") or 0) // 60,
            "awake_min": (dto.get("awakeSleepSeconds") or 0) // 60,
            "score": overall.get("value") if isinstance(overall, dict) else None,
            "qualifier": dto.get("sleepResultType"),
            "avg_spo2": dto.get("averageSpO2Value"),
            "avg_respiration": dto.get("averageRespirationValue"),
            "avg_stress": dto.get("averageStressLevel"),
        }
