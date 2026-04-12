"""Parse activity-*.json files into polar_activities + child tables."""

import json
from datetime import date as date_type, datetime
from pathlib import Path


def parse_activity(filepath: Path, now: datetime) -> dict:
    """Parse a single daily activity JSON file.

    Returns dict with keys: activity, samples, met_sources, physical_info.
    """
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    activity_date = date_type.fromisoformat(data["date"])

    activity = {
        "date": activity_date,
        "export_version": data.get("exportVersion"),
        "source_file": fname,
        "imported_at": now,
    }

    samples = []
    met_sources = []
    physical_info = None

    # Samples: mets and steps arrays
    samp = data.get("samples", {})
    for sample_type in ("mets", "steps"):
        raw = samp.get(sample_type, [])
        if raw:
            values = [item.get("value") for item in raw]
            samples.append({
                "date": activity_date,
                "sample_type": sample_type,
                "values_json": json.dumps(values),
            })

    # MET sources
    for idx, source_name in enumerate(samp.get("metSources", [])):
        met_sources.append({
            "date": activity_date,
            "source_index": idx,
            "source_name": source_name,
        })

    # Physical information
    phys = data.get("physicalInformation")
    if phys:
        bday = phys.get("birthday")
        physical_info = {
            "date": activity_date,
            "sex": phys.get("sex"),
            "birthday": date_type.fromisoformat(bday) if bday else None,
            "height_cm": phys.get("height, cm"),
            "weight_kg": phys.get("weight, kg"),
        }

    return {
        "activity": activity,
        "samples": samples,
        "met_sources": met_sources,
        "physical_info": physical_info,
    }
