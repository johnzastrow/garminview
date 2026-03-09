import json
from datetime import date
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter


class DailySummaryAdapter(BaseAdapter):
    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:daily_summary"

    def target_table(self) -> str:
        return "daily_summary"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        # Files live in year subdirs: FitFiles/Monitoring/2024/daily_summary_*.json
        for path in sorted(self._data_dir.rglob("daily_summary_*.json")):
            yield from self._parse_file(path)

    def _parse_file(self, path: Path) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        d = raw.get("calendarDate")
        if not d:
            return
        yield {
            "date": date.fromisoformat(d),
            "steps": raw.get("totalSteps"),
            "floors": raw.get("floorsAscended"),
            "distance_m": raw.get("totalDistanceMeters"),
            "calories_total": raw.get("totalKilocalories"),
            "calories_bmr": raw.get("bmrKilocalories"),
            "calories_active": raw.get("activeKilocalories"),
            "hr_avg": raw.get("averageHeartRate"),
            "hr_min": raw.get("minHeartRate"),
            "hr_max": raw.get("maxHeartRate"),
            "hr_resting": raw.get("restingHeartRateValue"),
            "stress_avg": raw.get("averageStressLevel"),
            "body_battery_max": raw.get("maxBodyBattery"),
            "body_battery_min": raw.get("minBodyBattery"),
            "spo2_avg": raw.get("averageSpo2"),
            "respiration_avg": raw.get("averageRespirationValue"),
            "hydration_intake_ml": raw.get("totalLiquidConsumptionMl"),
            "hydration_goal_ml": raw.get("dailyHydrationGoal"),
            "intensity_min_moderate": raw.get("moderateIntensityMinutes"),
            "intensity_min_vigorous": raw.get("vigorousIntensityMinutes"),
        }
