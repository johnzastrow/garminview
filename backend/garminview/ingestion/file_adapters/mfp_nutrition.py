import csv
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from garminview.ingestion.base import BaseAdapter
from garminview.core.logging import get_logger

log = get_logger(__name__)


def _parse_date(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _clean_num(s: str) -> float | None:
    if s is None:
        return None
    s = s.strip().replace(",", "")
    if not s or s == "—":
        return None
    try:
        return float(s)
    except ValueError:
        return None


class MFPNutritionAdapter(BaseAdapter):
    """Parses MFP 'Nutrition Summary.csv' -> mfp_daily_nutrition."""

    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "mfp_files:nutrition_summary"

    def target_table(self) -> str:
        return "mfp_daily_nutrition"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        path = self._data_dir / "Nutrition Summary.csv"
        if not path.exists():
            log.warning("mfp_nutrition_file_not_found", path=str(path))
            return
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = _parse_date(row.get("Date", ""))
                if not d or d < start_date or d > end_date:
                    continue
                # Flexible calorie column name
                cal_raw = row.get("Calories") or row.get("Calories Consumed") or ""
                yield {
                    "date": d,
                    "calories_in": int(_clean_num(cal_raw) or 0) or None,
                    "carbs_g": _clean_num(row.get("Carbohydrates", "")),
                    "fat_g": _clean_num(row.get("Fat", "")),
                    "protein_g": _clean_num(row.get("Protein", "")),
                    "sodium_mg": _clean_num(row.get("Sodium", "")),
                    "sugar_g": _clean_num(row.get("Sugar", "")),
                    "fiber_g": _clean_num(row.get("Fiber", "")),
                    "cholesterol_mg": _clean_num(row.get("Cholesterol", "")),
                    "logged_meals": None,
                    "source": "mfp_export",
                }


class MFPFoodDiaryAdapter(BaseAdapter):
    """Parses MFP 'Food Diary.csv' -> mfp_food_diary."""

    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "mfp_files:food_diary"

    def target_table(self) -> str:
        return "mfp_food_diary"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        path = self._data_dir / "Food Diary.csv"
        if not path.exists():
            log.warning("mfp_food_diary_not_found", path=str(path))
            return
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = _parse_date(row.get("Date", ""))
                if not d or d < start_date or d > end_date:
                    continue
                yield {
                    "date": d,
                    "meal": (row.get("Meal", "") or "").strip(),
                    "food_name": (row.get("Food Name", "") or row.get("Description", "") or "").strip()[:512],
                    "calories": int(_clean_num(row.get("Calories", "")) or 0) or None,
                    "carbs_g": _clean_num(row.get("Carbohydrates", "")),
                    "fat_g": _clean_num(row.get("Fat", "")),
                    "protein_g": _clean_num(row.get("Protein", "")),
                }


class MFPMeasurementAdapter(BaseAdapter):
    """Parses MFP 'Measurements.csv' -> mfp_measurements."""

    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "mfp_files:measurements"

    def target_table(self) -> str:
        return "mfp_measurements"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        path = self._data_dir / "Measurements.csv"
        if not path.exists():
            log.warning("mfp_measurements_not_found", path=str(path))
            return
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = _parse_date(row.get("Date", ""))
                if not d or d < start_date or d > end_date:
                    continue
                name = (row.get("Measurement", "") or row.get("Name", "") or "").strip()
                val_raw = _clean_num(row.get("Value", ""))
                unit = (row.get("Unit", "") or "").strip()
                if not name or val_raw is None:
                    continue
                # Normalise weight to kg
                if name.lower() == "weight" and unit.lower() in ("lb", "lbs"):
                    val_raw = val_raw * 0.453592
                    unit = "kg"
                yield {"date": d, "name": name, "value": val_raw, "unit": unit}
