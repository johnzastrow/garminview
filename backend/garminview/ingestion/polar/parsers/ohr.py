"""Parse 247ohr_*.json files into polar_247ohr."""

import json
from datetime import date as date_type, datetime
from pathlib import Path


def parse_247ohr(filepath: Path, now: datetime) -> list[dict]:
    """Parse a 247ohr JSON file. Returns list of dicts (one per device-day)."""
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    rows = []

    for dd in data.get("deviceDays", []):
        rows.append({
            "date": date_type.fromisoformat(dd["date"]),
            "device_id": dd.get("deviceId"),
            "user_id": dd.get("userId"),
            "samples_json": json.dumps(dd.get("samples", [])),
            "source_file": fname,
            "imported_at": now,
        })

    return rows
