"""Parse training-target-*.json files into polar_training_targets + phases."""

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


def parse_training_target(filepath: Path, now: datetime) -> dict:
    """Parse a training-target JSON file.

    Returns dict with keys: target, phases.
    target has no id yet (autoincrement); the importer assigns it after insert.
    """
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name

    target = {
        "start_time": _parse_dt(data.get("startTime")),
        "name": data.get("name"),
        "description": data.get("description"),
        "done": data.get("done"),
        "program_ref": data.get("programRef"),
        "non_user_editable": data.get("nonUserEditable"),
        "source_file": fname,
        "imported_at": now,
    }

    phases = []
    for ex_idx, ex in enumerate(data.get("exercises", [])):
        sport = ex.get("sport")
        for phase in ex.get("phases", []):
            goal = phase.get("goal", {})
            intensity = phase.get("intensity", {})
            phases.append({
                "exercise_index": ex_idx,
                "sport": sport,
                "phase_index": phase.get("index"),
                "phase_name": phase.get("name"),
                "change_type": phase.get("changeType"),
                "goal_type": goal.get("type"),
                "goal_duration": goal.get("duration"),
                "intensity_type": intensity.get("type"),
                "intensity_upper_zone": intensity.get("upperZone"),
                "intensity_lower_zone": intensity.get("lowerZone"),
            })

    return {"target": target, "phases": phases}
