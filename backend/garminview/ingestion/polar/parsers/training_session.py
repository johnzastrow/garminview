"""Parse training-session-*.json files into polar_training_sessions + child tables."""

import json
from datetime import datetime
from pathlib import Path


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    # Polar uses ISO without timezone or with offset — strip offset for naive storage
    s = s.replace("Z", "").split("+")[0].split("-05:00")[0].split("-04:00")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def parse_training_session(filepath: Path, now: datetime) -> dict:
    """Parse a single training-session JSON file.

    Returns dict with keys: session, exercises, statistics, zones, laps, samples, routes.
    Each value is a list of dicts ready for DB insertion.
    """
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    phys = data.get("physicalInformation", {})
    session_id = str(data["identifier"]["id"])

    session = {
        "session_id": session_id,
        "created": _parse_dt(data.get("created")),
        "modified": _parse_dt(data.get("modified")),
        "start_time": _parse_dt(data.get("startTime")),
        "stop_time": _parse_dt(data.get("stopTime")),
        "name": data.get("name"),
        "sport_id": str(data["sport"]["id"]) if data.get("sport") else None,
        "device_id": data.get("deviceId"),
        "device_model": (data.get("product") or {}).get("modelName"),
        "app_name": (data.get("application") or {}).get("name"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "duration_ms": data.get("durationMillis"),
        "distance_m": data.get("distanceMeters"),
        "calories": data.get("calories"),
        "training_load": data.get("trainingLoad"),
        "recovery_time_ms": _safe_int(data.get("recoveryTimeMillis")),
        "tz_offset_min": data.get("timezoneOffsetMinutes"),
        "max_hr": phys.get("maximumHeartRate"),
        "resting_hr": phys.get("restingHeartRate"),
        "aerobic_threshold": phys.get("aerobicThreshold"),
        "anaerobic_threshold": phys.get("anaerobicThreshold"),
        "vo2max": phys.get("vo2Max"),
        "weight_kg": phys.get("weightKg"),
        "source_file": fname,
        "imported_at": now,
    }

    exercises = []
    statistics = []
    zones = []
    laps = []
    samples = []
    routes = []

    for idx, ex in enumerate(data.get("exercises", [])):
        ex_id = str(ex["identifier"]["id"])
        exercises.append({
            "exercise_id": ex_id,
            "session_id": session_id,
            "exercise_index": idx,
            "start_time": _parse_dt(ex.get("startTime")),
            "stop_time": _parse_dt(ex.get("stopTime")),
            "duration_ms": ex.get("durationMillis"),
            "distance_m": ex.get("distanceMeters"),
            "calories": ex.get("calories"),
            "training_load": ex.get("trainingLoad"),
            "recovery_time_ms": _safe_int(ex.get("recoveryTimeMillis")),
            "sport_id": str(ex["sport"]["id"]) if ex.get("sport") else None,
            "latitude": ex.get("latitude"),
            "longitude": ex.get("longitude"),
            "tz_offset_min": ex.get("timezoneOffsetMinutes"),
        })

        # Statistics
        for stat in (ex.get("statistics") or {}).get("statistics", []):
            statistics.append({
                "exercise_id": ex_id,
                "stat_type": stat["type"],
                "avg": stat.get("avg"),
                "max": stat.get("max"),
            })

        # Zones
        for zone_group in ex.get("zones", []):
            zone_type = zone_group.get("type", "")
            for zi, z in enumerate(zone_group.get("zones", [])):
                zones.append({
                    "exercise_id": ex_id,
                    "zone_type": zone_type,
                    "zone_index": zi,
                    "lower_limit": z.get("lowerLimit"),
                    "higher_limit": z.get("higherLimit"),
                })

        # Laps (often empty dict — only store if list)
        ex_laps = ex.get("laps")
        if isinstance(ex_laps, list):
            for li, lap in enumerate(ex_laps):
                laps.append({
                    "exercise_id": ex_id,
                    "lap_index": li,
                    "raw_json": json.dumps(lap),
                })

        # Samples — store as JSON arrays per type
        for sample in (ex.get("samples") or {}).get("samples", []):
            values = sample.get("values", [])
            # Replace NaN-like values with None
            clean = [None if v != v else v for v in values] if values else []
            samples.append({
                "exercise_id": ex_id,
                "sample_type": sample["type"],
                "interval_ms": sample.get("intervalMillis"),
                "values_json": json.dumps(clean),
            })

        # Routes
        ex_routes = ex.get("routes")
        if isinstance(ex_routes, dict):
            for route_type in ("route", "transitionRoute"):
                route_data = ex_routes.get(route_type)
                if route_data and route_data.get("wayPoints"):
                    routes.append({
                        "exercise_id": ex_id,
                        "route_type": "main" if route_type == "route" else "transition",
                        "start_time": _parse_dt(route_data.get("startTime")),
                        "waypoints_json": json.dumps(route_data["wayPoints"]),
                    })

    return {
        "session": session,
        "exercises": exercises,
        "statistics": statistics,
        "zones": zones,
        "laps": laps,
        "samples": samples,
        "routes": routes,
    }
