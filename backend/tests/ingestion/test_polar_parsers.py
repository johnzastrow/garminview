"""Unit tests for the Polar GDPR-export parsers.

Each parser turns one Polar export file into record dict(s). These tests
assert the mapped fields on a realistic fixture, plus a sparse / missing-field
case that must be handled gracefully (no crash, sensible None/empty output).
"""

import json
from datetime import date, datetime
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures" / "polar"
NOW = datetime(2024, 6, 1, 12, 0, 0)


def _write(tmp_path: Path, name: str, obj) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return p


# ── training_session ─────────────────────────────────────────────────


def test_parse_training_session_fields():
    from garminview.ingestion.polar.parsers.training_session import (
        parse_training_session,
    )

    result = parse_training_session(FIXTURES / "training-session-332906208.json", NOW)

    s = result["session"]
    assert s["session_id"] == "332906208"
    assert s["name"] == "Morning Run"
    assert s["sport_id"] == "1"
    assert s["device_model"] == "Polar Vantage V2"
    assert s["app_name"] == "Polar Flow"
    assert s["duration_ms"] == 2700000
    assert s["distance_m"] == 8000.0
    assert s["calories"] == 500
    assert s["training_load"] == 120.5
    assert s["recovery_time_ms"] == 36000000  # coerced from string
    assert s["max_hr"] == 190
    assert s["vo2max"] == 52.0
    assert s["weight_kg"] == 75.0
    assert s["start_time"] == datetime(2024, 1, 15, 8, 0, 0)
    assert s["imported_at"] == NOW

    assert len(result["exercises"]) == 1
    ex = result["exercises"][0]
    assert ex["exercise_id"] == "987654321"
    assert ex["exercise_index"] == 0

    # 2 statistics, 2 zones, 1 lap, 1 sample, 1 route
    assert len(result["statistics"]) == 2
    assert {st["stat_type"] for st in result["statistics"]} == {"HEART_RATE", "SPEED"}
    assert len(result["zones"]) == 2
    assert result["zones"][0]["zone_type"] == "HEART_RATE"
    assert len(result["laps"]) == 1
    assert len(result["samples"]) == 1
    assert json.loads(result["samples"][0]["values_json"]) == [150, 155, None]
    assert len(result["routes"]) == 1
    assert result["routes"][0]["route_type"] == "main"


def test_parse_training_session_sparse(tmp_path):
    """Missing optional blocks -> empty child lists, None fields, no crash."""
    from garminview.ingestion.polar.parsers.training_session import (
        parse_training_session,
    )

    p = _write(tmp_path, "training-session-1.json", {"identifier": {"id": 1}})
    result = parse_training_session(p, NOW)
    assert result["session"]["session_id"] == "1"
    assert result["session"]["name"] is None
    assert result["session"]["sport_id"] is None
    assert result["exercises"] == []
    assert result["statistics"] == []
    assert result["routes"] == []


def test_parse_training_session_recovery_time_non_numeric(tmp_path):
    """_safe_int must swallow a non-numeric recoveryTimeMillis."""
    from garminview.ingestion.polar.parsers.training_session import (
        parse_training_session,
    )

    p = _write(
        tmp_path,
        "training-session-2.json",
        {"identifier": {"id": 2}, "recoveryTimeMillis": "n/a"},
    )
    result = parse_training_session(p, NOW)
    assert result["session"]["recovery_time_ms"] is None


# ── activity ─────────────────────────────────────────────────────────


def test_parse_activity_fields():
    from garminview.ingestion.polar.parsers.activity import parse_activity

    result = parse_activity(FIXTURES / "activity-2024-01-15.json", NOW)

    assert result["activity"]["date"] == date(2024, 1, 15)
    assert result["activity"]["export_version"] == "1.0"

    # mets + steps -> 2 sample rows
    sample_types = {s["sample_type"] for s in result["samples"]}
    assert sample_types == {"mets", "steps"}
    mets = next(s for s in result["samples"] if s["sample_type"] == "mets")
    assert json.loads(mets["values_json"]) == [1.2, 2.4]

    assert len(result["met_sources"]) == 2
    assert result["met_sources"][0]["source_name"] == "Wrist"
    assert result["met_sources"][1]["source_index"] == 1

    phys = result["physical_info"]
    assert phys["sex"] == "MALE"
    assert phys["birthday"] == date(1990, 5, 5)
    assert phys["height_cm"] == 180.0


def test_parse_activity_no_samples(tmp_path):
    from garminview.ingestion.polar.parsers.activity import parse_activity

    p = _write(tmp_path, "activity-2024-02-01.json", {"date": "2024-02-01"})
    result = parse_activity(p, NOW)
    assert result["activity"]["date"] == date(2024, 2, 1)
    assert result["samples"] == []
    assert result["met_sources"] == []
    assert result["physical_info"] is None


# ── sleep ────────────────────────────────────────────────────────────


def test_parse_sleep_fields():
    from garminview.ingestion.polar.parsers.sleep import parse_sleep

    results = parse_sleep(FIXTURES / "sleep_result_123.json", NOW)
    assert len(results) == 1
    entry = results[0]
    sleep = entry["sleep"]
    assert sleep["night"] == date(2024, 1, 15)
    assert sleep["sleep_type"] == "NIGHT"
    assert sleep["asleep_duration"] == "PT7H30M"
    assert sleep["age"] == 33
    assert sleep["efficiency_pct"] == 92.0
    assert sleep["continuity_class"] == 2
    assert sleep["interruption_total_count"] == 3
    assert sleep["sleep_start"] == datetime(2024, 1, 14, 23, 0, 0)
    assert sleep["sleep_end"] == datetime(2024, 1, 15, 7, 0, 0)
    assert sleep["battery_ran_out"] is False

    states = entry["states"]
    assert len(states) == 4
    assert states[0]["state"] == "NONREM2"
    assert states[0]["state_index"] == 0
    assert states[3]["state"] == "WAKE"


def test_parse_sleep_single_object_wrapped(tmp_path):
    """A non-array sleep file is wrapped into a one-element list."""
    from garminview.ingestion.polar.parsers.sleep import parse_sleep

    p = _write(
        tmp_path,
        "sleep_result_9.json",
        {"night": "2024-03-01", "evaluation": {}, "sleepResult": {}},
    )
    results = parse_sleep(p, NOW)
    assert len(results) == 1
    assert results[0]["sleep"]["night"] == date(2024, 3, 1)
    assert results[0]["sleep"]["age"] is None
    assert results[0]["states"] == []


# ── 247ohr ───────────────────────────────────────────────────────────


def test_parse_247ohr_fields():
    from garminview.ingestion.polar.parsers.ohr import parse_247ohr

    rows = parse_247ohr(FIXTURES / "247ohr_123.json", NOW)
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == date(2024, 1, 15)
    assert r["device_id"] == "DEV123"
    assert r["user_id"] == 17498985
    assert json.loads(r["samples_json"]) == [
        {"secondsFromMidnight": 0, "hr": 60},
        {"secondsFromMidnight": 60, "hr": 62},
    ]


def test_parse_247ohr_empty(tmp_path):
    from garminview.ingestion.polar.parsers.ohr import parse_247ohr

    p = _write(tmp_path, "247ohr_9.json", {"deviceDays": []})
    assert parse_247ohr(p, NOW) == []


# ── fitness_test ─────────────────────────────────────────────────────


def test_parse_fitness_test_fields():
    from garminview.ingestion.polar.parsers.fitness_test import parse_fitness_test

    row = parse_fitness_test(FIXTURES / "fitness-test-results-123.json", NOW)
    assert row["own_index"] == 52.0
    assert row["avg_hr"] == 60
    assert row["fitness_class"] == "GOOD"
    assert row["weight_kg"] == 75.0
    assert row["vo2max"] == 52.0
    # trailing Z stripped for naive datetime
    assert row["created"] == datetime(2024, 1, 15, 8, 0, 0)
    assert row["start_time"] == datetime(2024, 1, 15, 8, 5, 0)


def test_parse_fitness_test_missing_result(tmp_path):
    from garminview.ingestion.polar.parsers.fitness_test import parse_fitness_test

    p = _write(tmp_path, "fitness-test-results-9.json", {"created": None})
    row = parse_fitness_test(p, NOW)
    assert row["own_index"] is None
    assert row["vo2max"] is None
    assert row["created"] is None


# ── training_target ──────────────────────────────────────────────────


def test_parse_training_target_fields():
    from garminview.ingestion.polar.parsers.training_target import parse_training_target

    result = parse_training_target(FIXTURES / "training-target-123.json", NOW)
    t = result["target"]
    assert t["name"] == "Interval Session"
    assert t["description"] == "4x800m"
    assert t["done"] is False
    assert t["program_ref"] == 42
    assert t["start_time"] == datetime(2024, 1, 16, 0, 0, 0)

    phases = result["phases"]
    assert len(phases) == 2
    assert phases[0]["phase_name"] == "Warmup"
    assert phases[0]["sport"] == "RUNNING"
    assert phases[0]["goal_type"] == "DURATION"
    assert phases[0]["intensity_upper_zone"] == 2
    assert phases[1]["phase_name"] == "Interval"


def test_parse_training_target_no_exercises(tmp_path):
    from garminview.ingestion.polar.parsers.training_target import parse_training_target

    p = _write(tmp_path, "training-target-9.json", {"name": "Empty"})
    result = parse_training_target(p, NOW)
    assert result["target"]["name"] == "Empty"
    assert result["phases"] == []


# ── account ──────────────────────────────────────────────────────────


def test_parse_account_data_fields():
    from garminview.ingestion.polar.parsers.account import parse_account_data

    d = parse_account_data(FIXTURES / "account-data-17498985-abcd.json", NOW)
    assert d["user_id"] == 17498985  # extracted from filename
    assert d["username"] == "runner1"
    assert d["first_name"] == "Jane"
    assert d["sex"] == "FEMALE"
    assert d["birthday"] == date(1990, 5, 5)
    assert d["height_cm"] == 165.0
    assert d["vo2max"] == 48.0
    assert d["resting_hr"] == 55
    assert d["timezone"] == "America/New_York"
    assert json.loads(d["linked_apps_json"]) == ["Strava"]


def test_parse_account_profile_fields():
    from garminview.ingestion.polar.parsers.account import parse_account_profile

    d = parse_account_profile(FIXTURES / "account-profile-17498985-abcd.json", NOW)
    assert d["user_id"] == 17498985
    assert d["motto"] == "Just do it"
    assert d["city"] == "Pittsburgh"
    assert json.loads(d["favourite_sports_json"]) == ["RUNNING", "CYCLING"]


def test_parse_account_data_unparseable_filename(tmp_path):
    """No user id in filename -> user_id None, still parses body."""
    from garminview.ingestion.polar.parsers.account import parse_account_data

    p = _write(tmp_path, "account-data-noid.json", {"username": "x"})
    d = parse_account_data(p, NOW)
    assert d["user_id"] is None
    assert d["username"] == "x"


# ── calendar ─────────────────────────────────────────────────────────


def test_parse_calendar_fields():
    from garminview.ingestion.polar.parsers.calendar import parse_calendar

    rows = parse_calendar(FIXTURES / "calendar-items-123.json", NOW)
    assert len(rows) == 1
    r = rows[0]
    assert r["datetime_"] == datetime(2024, 1, 15, 0, 0, 0)
    assert r["height_cm"] == 165.0
    assert r["ftp"] == 220
    assert r["max_hr"] == 190
    assert r["training_background"] == "FREQUENT"


def test_parse_calendar_empty(tmp_path):
    from garminview.ingestion.polar.parsers.calendar import parse_calendar

    p = _write(tmp_path, "calendar-items-9.json", {})
    assert parse_calendar(p, NOW) == []


# ── generic blobs ────────────────────────────────────────────────────


def test_parse_sport_profiles():
    from garminview.ingestion.polar.parsers.generic import parse_sport_profiles

    rows = parse_sport_profiles(FIXTURES / "sport-profiles-123.json", NOW)
    assert len(rows) == 2
    assert rows[0]["sport"] == "RUNNING"
    assert json.loads(rows[0]["raw_json"])["settingA"] == 1
    assert rows[0]["source_file"] == "sport-profiles-123.json"


def test_parse_sport_profiles_single_object(tmp_path):
    """A dict (not a list) is coerced into one row."""
    from garminview.ingestion.polar.parsers.generic import parse_sport_profiles

    p = _write(tmp_path, "sport-profiles-9.json", {"sport": "SWIMMING"})
    rows = parse_sport_profiles(p, NOW)
    assert len(rows) == 1
    assert rows[0]["sport"] == "SWIMMING"


def test_parse_generic_blob():
    from garminview.ingestion.polar.parsers.generic import parse_generic_blob

    row = parse_generic_blob(FIXTURES / "products-devices-123.json", NOW)
    assert row["source_file"] == "products-devices-123.json"
    assert json.loads(row["raw_json"])["devices"][0]["name"] == "Vantage V2"


def test_parse_programs_detects_type():
    from garminview.ingestion.polar.parsers.generic import parse_programs

    row = parse_programs(FIXTURES / "programs-eventtrainingprograms-123.json", NOW)
    assert row["program_type"] == "eventtrainingprograms"
    assert json.loads(row["raw_json"])["programs"][0]["name"] == "5k Plan"


# ── datetime-helper edge cases ───────────────────────────────────────


def test_sleep_parse_dt_strips_timezone():
    from garminview.ingestion.polar.parsers.sleep import _parse_dt

    assert _parse_dt("2024-01-14T23:00:00.000-05:00") == datetime(2024, 1, 14, 23, 0, 0)
    assert _parse_dt("2024-01-14T23:00:00Z") == datetime(2024, 1, 14, 23, 0, 0)
    assert _parse_dt(None) is None
    assert _parse_dt("garbage") is None


def test_training_session_parse_dt_variants():
    from garminview.ingestion.polar.parsers.training_session import _parse_dt

    assert _parse_dt("2024-01-15T08:00:00+02:00") == datetime(2024, 1, 15, 8, 0, 0)
    assert _parse_dt("2024-01-15T08:00") == datetime(2024, 1, 15, 8, 0, 0)
    assert _parse_dt(None) is None
