import json
from datetime import date
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class WeightAdapter(BaseAdapter):
    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:weight"

    def target_table(self) -> str:
        return "weight"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        for path in sorted(self._data_dir.glob("*.json")):
            yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        # Weight data is a list under dateWeightList; skip files with no entries
        for entry in raw.get("dateWeightList", []):
            d = entry.get("calendarDate")
            if not d:
                continue
            weight = entry.get("weight")
            if weight and weight > 1000:  # grams → kg
                weight = weight / 1000
            yield {
                "date": date.fromisoformat(d),
                "weight_kg": weight,
                "source": "garmin",
            }
