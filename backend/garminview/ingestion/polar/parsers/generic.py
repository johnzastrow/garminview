"""Parse JSON-blob file types: sport-profiles, devices, programs, planned-routes, favourite-targets."""

import json
from datetime import datetime
from pathlib import Path


def parse_sport_profiles(filepath: Path, now: datetime) -> list[dict]:
    """Parse sport-profiles JSON (array of profiles). Returns list of dicts."""
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    if not isinstance(data, list):
        data = [data]

    rows = []
    for item in data:
        rows.append({
            "sport": item.get("sport"),
            "raw_json": json.dumps(item),
            "source_file": fname,
            "imported_at": now,
        })
    return rows


def parse_generic_blob(filepath: Path, now: datetime) -> dict:
    """Parse a generic JSON file as a single raw_json blob row."""
    with open(filepath) as f:
        data = json.load(f)

    return {
        "raw_json": json.dumps(data),
        "source_file": filepath.name,
        "imported_at": now,
    }


def parse_programs(filepath: Path, now: datetime) -> dict:
    """Parse a programs-*.json file. Detects program type from filename prefix."""
    fname = filepath.name
    # e.g. programs-eventtrainingprograms-... → eventtrainingprograms
    parts = fname.split("-", 1)
    program_type = parts[1].split("-")[0] if len(parts) > 1 else "unknown"

    with open(filepath) as f:
        data = json.load(f)

    return {
        "program_type": program_type,
        "raw_json": json.dumps(data),
        "source_file": fname,
        "imported_at": now,
    }
