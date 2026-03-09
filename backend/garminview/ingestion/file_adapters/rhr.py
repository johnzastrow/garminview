import json
from datetime import date
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class RHRAdapter(BaseAdapter):
    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:rhr"

    def target_table(self) -> str:
        return "resting_heart_rate"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        for path in sorted(self._data_dir.glob("*.json")):
            yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        # RHR is nested: allMetrics.metricsMap.WELLNESS_RESTING_HEART_RATE[0]
        entries = (
            raw.get("allMetrics", {})
               .get("metricsMap", {})
               .get("WELLNESS_RESTING_HEART_RATE", [])
        )
        for entry in entries:
            d = entry.get("calendarDate")
            if not d:
                continue
            yield {
                "date": date.fromisoformat(d),
                "resting_hr": entry.get("value"),
            }
