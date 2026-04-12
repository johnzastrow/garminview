"""Parse fitness-test-results-*.json files into polar_fitness_tests."""

from datetime import datetime
from pathlib import Path
import json


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "").split("+")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_fitness_test(filepath: Path, now: datetime) -> dict:
    """Parse a single fitness-test-results JSON file. Returns a dict for DB insertion."""
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    ftr = data.get("fitnessTestResult", {})
    phys = ftr.get("physicalInformation", {})

    return {
        "created": _parse_dt(data.get("created")),
        "start_time": _parse_dt(data.get("startTime")),
        "own_index": ftr.get("ownIndex"),
        "avg_hr": ftr.get("averageHeartRate"),
        "fitness_class": ftr.get("fitnessClass"),
        "tz_offset_min": ftr.get("timezoneOffsetMinutes"),
        "weight_kg": phys.get("weight"),
        "vo2max": phys.get("vo2Max"),
        "source_file": fname,
        "imported_at": now,
    }
