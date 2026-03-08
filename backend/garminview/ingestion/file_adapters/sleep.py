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
        d = raw.get("calendarDate")
        if not d:
            return
        day = date.fromisoformat(d)

        start_ts = raw.get("sleepStartTimestampGMT")
        end_ts = raw.get("sleepEndTimestampGMT")
        scores = raw.get("sleepScores", {})
        overall = scores.get("overall", {}) if isinstance(scores, dict) else {}

        yield {
            "date": day,
            "start": datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc) if start_ts else None,
            "end": datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc) if end_ts else None,
            "total_sleep_min": (raw.get("deepSleepSeconds", 0) + raw.get("lightSleepSeconds", 0)
                                + raw.get("remSleepSeconds", 0)) // 60,
            "deep_sleep_min": (raw.get("deepSleepSeconds") or 0) // 60,
            "light_sleep_min": (raw.get("lightSleepSeconds") or 0) // 60,
            "rem_sleep_min": (raw.get("remSleepSeconds") or 0) // 60,
            "awake_min": (raw.get("awakeSleepSeconds") or 0) // 60,
            "score": overall.get("value") if isinstance(overall, dict) else None,
            "qualifier": raw.get("sleepResultType"),
            "avg_spo2": raw.get("averageSpO2Value"),
            "avg_respiration": raw.get("averageRespirationValue"),
            "avg_stress": raw.get("averageStressLevel"),
        }
