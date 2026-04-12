"""Parse account-data and account-profile JSON files into polar_account."""

import json
import re
from datetime import date as date_type, datetime
from pathlib import Path


def _extract_user_id(filename: str) -> int | None:
    """Extract user ID from filename like account-data-17498985-uuid.json."""
    m = re.search(r"account-(?:data|profile)-(\d+)-", filename)
    return int(m.group(1)) if m else None


def parse_account_data(filepath: Path, now: datetime) -> dict:
    """Parse account-data JSON. Returns partial account dict."""
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    user_id = _extract_user_id(fname)
    phys = data.get("physicalInformation", {})
    bday = phys.get("birthday")

    return {
        "user_id": user_id,
        "username": data.get("username"),
        "first_name": data.get("firstName"),
        "last_name": data.get("lastName"),
        "nickname": data.get("nickname"),
        "sex": phys.get("sex"),
        "birthday": date_type.fromisoformat(bday) if bday else None,
        "height_cm": phys.get("height, cm"),
        "weight_kg": phys.get("weight, kg"),
        "vo2max": phys.get("vo2Max"),
        "resting_hr": phys.get("restingHeartRate"),
        "sleep_goal": phys.get("sleepGoal"),
        "timezone": (data.get("settings") or {}).get("timeZone"),
        "settings_json": json.dumps(data.get("settings")) if data.get("settings") else None,
        "linked_apps_json": json.dumps(data.get("linkedApplications")) if data.get("linkedApplications") else None,
        "source_file": fname,
        "imported_at": now,
    }


def parse_account_profile(filepath: Path, now: datetime) -> dict:
    """Parse account-profile JSON. Returns partial account dict (profile fields only)."""
    with open(filepath) as f:
        data = json.load(f)

    fname = filepath.name
    user_id = _extract_user_id(fname)

    return {
        "user_id": user_id,
        "motto": data.get("motto"),
        "phone": data.get("phone"),
        "country_code": data.get("countryCode"),
        "city": data.get("city"),
        "favourite_sports_json": json.dumps(data.get("favouriteSports")) if data.get("favouriteSports") else None,
        "source_file": fname,
        "imported_at": now,
    }
