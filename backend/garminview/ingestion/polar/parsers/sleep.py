"""Parse sleep_result_*.json files into polar_sleep + polar_sleep_states."""

import json
from datetime import date as date_type, datetime
from pathlib import Path


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    # Strip timezone offset for naive datetime storage
    for tz in ("+00:00", "-05:00", "-04:00", "-03:00", "-06:00", "-07:00", "-08:00"):
        s = s.replace(tz, "")
    s = s.replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_sleep(filepath: Path, now: datetime) -> list[dict]:
    """Parse a sleep_result JSON file (contains an array of sleep nights).

    Returns list of dicts, each with keys: sleep, states.
    """
    with open(filepath) as f:
        data = json.load(f)

    # File is a JSON array of sleep nights
    if not isinstance(data, list):
        data = [data]

    fname = filepath.name
    results = []

    for entry in data:
        night = date_type.fromisoformat(entry["night"])
        evaluation = entry.get("evaluation", {})
        analysis = evaluation.get("analysis", {})
        interruptions = evaluation.get("interruptions", {})
        hypno = (entry.get("sleepResult") or {}).get("hypnogram", {})

        sleep = {
            "night": night,
            "sleep_type": evaluation.get("sleepType"),
            "sleep_span": evaluation.get("sleepSpan"),
            "asleep_duration": evaluation.get("asleepDuration"),
            "age": int(evaluation["age"]) if evaluation.get("age") is not None else None,
            "efficiency_pct": analysis.get("efficiencyPercent"),
            "continuity_index": analysis.get("continuityIndex"),
            "continuity_class": analysis.get("continuityClass"),
            "feedback": analysis.get("feedback"),
            "interruption_total_dur": interruptions.get("totalDuration"),
            "interruption_total_count": interruptions.get("totalCount"),
            "interruption_short_count": interruptions.get("shortCount"),
            "interruption_long_count": interruptions.get("longCount"),
            "sleep_start": _parse_dt(hypno.get("sleepStart")),
            "sleep_end": _parse_dt(hypno.get("sleepEnd")),
            "sleep_goal": hypno.get("sleepGoal"),
            "rating": hypno.get("rating"),
            "device_id": hypno.get("deviceId"),
            "battery_ran_out": hypno.get("batteryRanOut"),
            "source_file": fname,
            "imported_at": now,
        }

        states = []
        for idx, sc in enumerate(hypno.get("sleepStateChanges", [])):
            states.append({
                "night": night,
                "state_index": idx,
                "offset_from_start": sc.get("offsetFromStart"),
                "state": sc.get("state"),
            })

        results.append({"sleep": sleep, "states": states})

    return results
