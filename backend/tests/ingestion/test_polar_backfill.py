"""Tests for backfilling core garminview tables from polar_* staging tables.

Seeds polar_* rows in the in-memory ``session`` fixture and runs each backfill
function, asserting rows land in the core tables and that the "Garmin wins"
collision/skip rules hold.
"""

from datetime import date, datetime

import pytest

from garminview.ingestion.polar_backfill import (
    _parse_iso_duration_minutes,
    _parse_iso_duration_seconds,
    _polar_id_to_int,
    backfill_polar_activities,
    backfill_polar_resting_hr,
    backfill_polar_sleep,
    backfill_polar_vo2max,
    backfill_all_polar,
)
from garminview.models.activities import Activity
from garminview.models.health import RestingHeartRate, Sleep, SleepEvent
from garminview.models.polar import (
    PolarExercise,
    PolarExerciseStatistic,
    PolarSleep,
    PolarSleepState,
    PolarTrainingSession,
)
from garminview.models.supplemental import VO2Max


# ── helpers ──────────────────────────────────────────────────────────


def test_parse_iso_duration_minutes():
    assert _parse_iso_duration_minutes("PT6H53M30S") == 414  # 6*60+53+0.5 rounded
    assert _parse_iso_duration_minutes("PT30M") == 30
    assert _parse_iso_duration_minutes(None) is None
    assert _parse_iso_duration_minutes("garbage") is None  # no PT prefix -> no match
    assert _parse_iso_duration_minutes("PT") == 0  # PT prefix, all groups empty -> 0


def test_parse_iso_duration_seconds():
    assert _parse_iso_duration_seconds("PT1H") == 3600
    assert _parse_iso_duration_seconds("PT0S") == 0
    assert _parse_iso_duration_seconds(None) == 0.0


def test_polar_id_to_int():
    assert _polar_id_to_int("332906208") == 332906208
    # Non-numeric -> stable hash, deterministic
    h1 = _polar_id_to_int("abc-uuid")
    h2 = _polar_id_to_int("abc-uuid")
    assert h1 == h2
    assert h1 != _polar_id_to_int("different-uuid")


def _polar_session(session, session_id, start_time, **kw):
    ps = PolarTrainingSession(session_id=session_id, start_time=start_time, **kw)
    session.add(ps)
    return ps


# ── activities backfill ──────────────────────────────────────────────


def test_backfill_activities_inserts_new(session):
    _polar_session(
        session,
        "332906208",
        datetime(2024, 1, 15, 13, 0),
        name="Morning Run",
        sport_id="1",
        duration_ms=2700000,
        distance_m=8000.0,
        calories=500,
        training_load=120.5,
        tz_offset_min=-300,
    )
    session.flush()

    result = backfill_polar_activities(session)
    assert result["activities_inserted"] == 1

    act = session.get(Activity, 332906208)
    assert act is not None
    assert act.source == "polar"
    assert act.sport == "running"  # sport_id "1" mapped
    assert act.elapsed_time_s == 2700  # 2700000 ms / 1000
    # local 13:00 minus tz_offset -300 -> +5h -> 18:00 UTC
    assert act.start_time == datetime(2024, 1, 15, 18, 0)
    # avg_speed = distance / duration_s = 8000 / 2700
    assert act.avg_speed == pytest.approx(8000 / 2700)


def test_backfill_activities_pulls_hr_from_statistics(session):
    _polar_session(
        session,
        "500",
        datetime(2024, 2, 1, 12, 0),
        sport_id="1",
        duration_ms=1800000,
        tz_offset_min=0,
    )
    session.add(PolarExercise(exercise_id="ex500", session_id="500", exercise_index=0))
    session.add(
        PolarExerciseStatistic(
            exercise_id="ex500", stat_type="HEART_RATE", avg=155.4, max=182.6
        )
    )
    session.add(
        PolarExerciseStatistic(
            exercise_id="ex500", stat_type="CADENCE", avg=88.2, max=95.0
        )
    )
    session.flush()

    backfill_polar_activities(session)
    act = session.get(Activity, 500)
    assert act.avg_hr == 155  # rounded
    assert act.max_hr == 183
    assert act.avg_cadence == 88


def test_backfill_activities_skips_garmin_collision(session):
    # Garmin activity at 18:00 UTC; Polar local 13:00 with -300 offset -> 18:00 UTC.
    session.add(
        Activity(
            activity_id=999,
            start_time=datetime(2024, 1, 15, 18, 0),
            source="garmin_fit",
        )
    )
    _polar_session(
        session,
        "332906208",
        datetime(2024, 1, 15, 13, 0),
        sport_id="1",
        duration_ms=1800000,
        tz_offset_min=-300,
    )
    session.flush()

    result = backfill_polar_activities(session)
    assert result["activities_inserted"] == 0
    assert result["activities_skipped"] == 1
    assert session.get(Activity, 332906208) is None


# ── sleep backfill ───────────────────────────────────────────────────


def test_backfill_sleep_inserts_with_stages(session):
    night = date(2024, 1, 15)
    session.add(
        PolarSleep(
            night=night,
            asleep_duration="PT7H30M",
            efficiency_pct=92.0,
            sleep_start=datetime(2024, 1, 14, 23, 0),
            sleep_end=datetime(2024, 1, 15, 7, 0),
        )
    )
    # Full-stage hypnogram: light -> deep -> rem -> wake
    for idx, (offset, state) in enumerate(
        [
            ("PT0S", "NONREM2"),
            ("PT1H", "NONREM3"),
            ("PT3H", "REM"),
            ("PT4H", "WAKE"),
        ]
    ):
        session.add(
            PolarSleepState(
                night=night, state_index=idx, offset_from_start=offset, state=state
            )
        )
    session.flush()

    result = backfill_polar_sleep(session)
    assert result["sleep_inserted"] == 1

    sleep = session.get(Sleep, night)
    assert sleep.source == "polar"
    assert sleep.total_sleep_min == 450  # 7h30m
    assert sleep.qualifier == "GOOD"  # efficiency >= 90
    assert sleep.score == 92
    # NONREM2 (light) 0->1h = 60, NONREM3 (deep) 1h->3h = 120, REM 3h->4h = 60
    assert sleep.light_sleep_min == 60
    assert sleep.deep_sleep_min == 120
    assert sleep.rem_sleep_min == 60

    # Hypnogram states become SleepEvents (non-wake + wake mapped)
    events = session.query(SleepEvent).filter(SleepEvent.date == night).all()
    assert len(events) == 4
    assert {e.event_type for e in events} == {"light", "deep", "rem", "awake"}


def test_backfill_sleep_skips_real_garmin_row(session):
    night = date(2024, 1, 15)
    session.add(Sleep(date=night, total_sleep_min=400, source="garmin"))
    session.add(
        PolarSleep(
            night=night,
            asleep_duration="PT7H",
            efficiency_pct=80.0,
            sleep_start=datetime(2024, 1, 14, 23, 0),
            sleep_end=datetime(2024, 1, 15, 6, 0),
        )
    )
    session.flush()

    result = backfill_polar_sleep(session)
    assert result["sleep_skipped"] == 1
    assert result["sleep_inserted"] == 0
    sleep = session.get(Sleep, night)
    assert sleep.source == "garmin"  # untouched


def test_backfill_sleep_basic_device_leaves_stages_none(session):
    """A device that only reports NONREM3/WAKE can't distinguish stages."""
    night = date(2024, 3, 1)
    session.add(
        PolarSleep(
            night=night,
            asleep_duration="PT6H",
            efficiency_pct=70.0,
            sleep_start=datetime(2024, 2, 29, 23, 0),
            sleep_end=datetime(2024, 3, 1, 5, 0),
        )
    )
    for idx, (offset, state) in enumerate([("PT0S", "NONREM3"), ("PT5H", "WAKE")]):
        session.add(
            PolarSleepState(
                night=night, state_index=idx, offset_from_start=offset, state=state
            )
        )
    session.flush()

    backfill_polar_sleep(session)
    sleep = session.get(Sleep, night)
    assert sleep.deep_sleep_min is None
    assert sleep.light_sleep_min is None
    assert sleep.rem_sleep_min is None
    assert sleep.qualifier == "POOR"  # efficiency < 75


# ── resting HR backfill ──────────────────────────────────────────────


def test_backfill_resting_hr_earliest_per_day(session):
    _polar_session(session, "a", datetime(2024, 1, 15, 7, 0), resting_hr=50)
    _polar_session(session, "b", datetime(2024, 1, 15, 18, 0), resting_hr=58)
    session.flush()

    result = backfill_polar_resting_hr(session)
    assert result["resting_hr_inserted"] == 1
    rhr = session.get(RestingHeartRate, date(2024, 1, 15))
    assert rhr.resting_hr == 50  # earliest session wins
    assert rhr.source == "polar"


def test_backfill_resting_hr_skips_garmin(session):
    session.add(
        RestingHeartRate(date=date(2024, 1, 15), resting_hr=48, source="garmin")
    )
    _polar_session(session, "a", datetime(2024, 1, 15, 7, 0), resting_hr=50)
    session.flush()

    result = backfill_polar_resting_hr(session)
    assert result["resting_hr_skipped"] == 1
    assert session.get(RestingHeartRate, date(2024, 1, 15)).resting_hr == 48


# ── VO2max backfill ──────────────────────────────────────────────────


def test_backfill_vo2max_latest_per_day(session):
    _polar_session(session, "a", datetime(2024, 1, 15, 7, 0), vo2max=50.0)
    _polar_session(session, "b", datetime(2024, 1, 15, 18, 0), vo2max=52.0)
    session.flush()

    result = backfill_polar_vo2max(session)
    assert result["vo2max_inserted"] == 1
    vo2 = session.get(VO2Max, date(2024, 1, 15))
    assert vo2.vo2max_running == 52.0  # latest session wins
    assert vo2.source == "polar"


# ── orchestrator ─────────────────────────────────────────────────────


def test_backfill_all_polar_runs_and_commits(session):
    _polar_session(
        session,
        "332906208",
        datetime(2024, 1, 15, 13, 0),
        sport_id="1",
        duration_ms=1800000,
        tz_offset_min=-300,
        resting_hr=50,
        vo2max=52.0,
    )
    session.add(
        PolarSleep(
            night=date(2024, 1, 15),
            asleep_duration="PT7H",
            efficiency_pct=91.0,
            sleep_start=datetime(2024, 1, 14, 23, 0),
            sleep_end=datetime(2024, 1, 15, 6, 0),
        )
    )
    session.flush()

    result = backfill_all_polar(session)
    assert result["activities_inserted"] == 1
    assert result["sleep_inserted"] == 1
    assert result["resting_hr_inserted"] == 1
    assert result["vo2max_inserted"] == 1
    # committed -> visible after expiring the identity map
    session.expire_all()
    assert session.get(Activity, 332906208) is not None
