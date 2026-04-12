"""Parse calendar-items-*.json files into polar_calendar_items."""

from datetime import datetime
from pathlib import Path
import json


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_calendar(filepath: Path, now: datetime) -> list[dict]:
    """Parse calendar-items JSON. Returns list of physical info snapshot dicts."""
    with open(filepath) as f:
        data = json.load(f)

    rows = []
    for item in data.get("physicalInformations", []):
        rows.append({
            "datetime_": _parse_dt(item.get("dateTime")),
            "height_cm": item.get("height, cm"),
            "weight_kg": item.get("weight, kg"),
            "vo2max": item.get("vo2Max"),
            "max_hr": item.get("maximumHeartRate"),
            "resting_hr": item.get("restingHeartRate"),
            "aerobic_threshold": item.get("aerobicThreshold"),
            "anaerobic_threshold": item.get("anaerobicThreshold"),
            "ftp": item.get("functionalThresholdPower"),
            "training_background": item.get("trainingBackground"),
            "typical_day": item.get("typicalDay"),
        })

    return rows
