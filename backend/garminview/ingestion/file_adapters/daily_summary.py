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
        # Only scan year directories that overlap with the requested date range.
        years = range(start_date.year, end_date.year + 1)
        for year in years:
            year_dir = self._data_dir / str(year)
            if not year_dir.is_dir():
                continue
            for path in sorted(year_dir.glob("daily_summary_*.json")):
                yield from self._parse_file(path, start_date, end_date)

    @staticmethod
    def _nn(value):
        """Return None for Garmin sentinel values (-1, -1.0) meaning 'no data'."""
        if value is None:
            return None
        return None if value == -1 else value

    def _parse_file(self, path: Path, start_date: date | None = None, end_date: date | None = None) -> Iterator[dict]:
        raw = json.loads(path.read_text())
        d = raw.get("calendarDate")
        if not d:
            return
        parsed_date = date.fromisoformat(d)
        if start_date and parsed_date < start_date:
            return
        if end_date and parsed_date > end_date:
            return
        nn = self._nn
        yield {
            "date": parsed_date,
            "steps": raw.get("totalSteps"),
            "floors": raw.get("floorsAscended"),
            "distance_m": raw.get("totalDistanceMeters"),
            "calories_total": raw.get("totalKilocalories"),
            "calories_bmr": raw.get("bmrKilocalories"),
            "calories_active": raw.get("activeKilocalories"),
            "hr_min": nn(raw.get("minHeartRate")),
            "hr_max": nn(raw.get("maxHeartRate")),
            "hr_resting": nn(raw.get("restingHeartRate")),
            "stress_avg": nn(raw.get("averageStressLevel")),
            "body_battery_max": nn(raw.get("bodyBatteryHighestValue")),
            "body_battery_min": nn(raw.get("bodyBatteryLowestValue")),
            "spo2_avg": nn(raw.get("averageSpo2")),
            "respiration_avg": nn(raw.get("avgWakingRespirationValue")),
            "hydration_intake_ml": raw.get("totalLiquidConsumptionMl"),
            "hydration_goal_ml": raw.get("dailyHydrationGoal"),
            "intensity_min_moderate": raw.get("moderateIntensityMinutes"),
            "intensity_min_vigorous": raw.get("vigorousIntensityMinutes"),
        }
