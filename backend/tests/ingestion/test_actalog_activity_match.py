"""Tests for matching Actalog workouts to Garmin activities by date + duration.

Seeds Activity + ActalogWorkout rows in the in-memory ``session`` fixture and
exercises the candidate listing and the auto-match ranking (clear winner,
out-of-tolerance, ambiguous tie, and the unrankable cases).
"""

from datetime import datetime

from garminview.ingestion.actalog_activity_match import (
    auto_match,
    list_candidates,
    resolve_activity,
)
from garminview.models.activities import Activity
from garminview.models.actalog import ActalogWorkout


def _activity(session, activity_id, start_time, elapsed_s):
    a = Activity(
        activity_id=activity_id,
        start_time=start_time,
        elapsed_time_s=elapsed_s,
        source="garmin_fit",
    )
    session.add(a)
    return a


def _workout(session, workout_date, total_time_s):
    w = ActalogWorkout(workout_date=workout_date, total_time_s=total_time_s)
    session.add(w)
    session.flush()
    return w


# ── list_candidates ──────────────────────────────────────────────────


def test_list_candidates_same_day_only_sorted(session):
    # Two activities on the workout day, one the day before.
    _activity(session, 1, datetime(2024, 1, 15, 18, 0), 1800)
    _activity(session, 2, datetime(2024, 1, 15, 7, 0), 1700)
    _activity(session, 3, datetime(2024, 1, 14, 8, 0), 1800)
    session.flush()

    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)
    cands = list_candidates(session, workout)

    assert [a.activity_id for a in cands] == [2, 1]  # sorted by start_time asc


def test_list_candidates_none_when_no_date(session):
    workout = _workout(session, None, 1800)
    assert list_candidates(session, workout) == []


def test_list_candidates_empty_when_no_activities(session):
    workout = _workout(session, datetime(2024, 5, 1, 0, 0), 1800)
    assert list_candidates(session, workout) == []


# ── auto_match ───────────────────────────────────────────────────────


def test_auto_match_clear_winner(session):
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1790)  # 10s off -> winner
    _activity(session, 2, datetime(2024, 1, 15, 18, 0), 600)  # far off
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)

    match = auto_match(session, workout)
    assert match is not None
    assert match.activity_id == 1


def test_auto_match_declines_when_out_of_tolerance(session):
    # Closest activity is 900s vs target 1800s -> 50% off, beyond the 30% bound.
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 900)
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)
    assert auto_match(session, workout) is None


def test_auto_match_ambiguous_tie_declines(session):
    # Two activities equidistant from the target -> ambiguous, decline.
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1750)  # 50s under
    _activity(session, 2, datetime(2024, 1, 15, 18, 0), 1850)  # 50s over
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)
    assert auto_match(session, workout) is None


def test_auto_match_none_without_target_duration(session):
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1800)
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), None)
    assert auto_match(session, workout) is None


def test_auto_match_none_when_no_candidates(session):
    workout = _workout(session, datetime(2024, 6, 1, 0, 0), 1800)
    assert auto_match(session, workout) is None


def test_auto_match_ignores_activities_without_elapsed(session):
    # Only candidate has no elapsed_time_s -> cannot rank -> None.
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), None)
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)
    assert auto_match(session, workout) is None


# ── resolve_activity ─────────────────────────────────────────────────
# The garmin_activity_id / garmin_match_confirmed columns now exist (migration
# 0010 + the model), so resolve_activity fully exercises its branches.


def test_resolve_activity_confirmed_link(session):
    """Confirmed match with a linked id returns that activity, status 'linked'."""
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1790)
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)
    workout.garmin_activity_id = 1
    workout.garmin_match_confirmed = True
    session.flush()

    activity, status = resolve_activity(session, workout)
    assert status == "linked"
    assert activity is not None
    assert activity.activity_id == 1


def test_resolve_activity_confirmed_none(session):
    """Confirmed 'no activity' (id NULL) returns (None, 'none') and ignores
    any otherwise-auto-matchable activity on the day."""
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1790)  # would auto-match
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)
    workout.garmin_activity_id = None
    workout.garmin_match_confirmed = True
    session.flush()

    activity, status = resolve_activity(session, workout)
    assert activity is None
    assert status == "none"


def test_resolve_activity_auto(session):
    """Unconfirmed clear winner resolves as 'auto' with that activity."""
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1790)
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)

    activity, status = resolve_activity(session, workout)
    assert status == "auto"
    assert activity is not None
    assert activity.activity_id == 1


def test_resolve_activity_ambiguous(session):
    """Unconfirmed with candidates but no clear winner resolves as 'ambiguous'."""
    _activity(session, 1, datetime(2024, 1, 15, 7, 0), 1750)   # 50s under
    _activity(session, 2, datetime(2024, 1, 15, 18, 0), 1850)  # 50s over
    session.flush()
    workout = _workout(session, datetime(2024, 1, 15, 0, 0), 1800)

    activity, status = resolve_activity(session, workout)
    assert activity is None
    assert status == "ambiguous"


def test_resolve_activity_unavailable(session):
    """Unconfirmed with no activities on the date resolves as 'unavailable'."""
    workout = _workout(session, datetime(2024, 6, 1, 0, 0), 1800)

    activity, status = resolve_activity(session, workout)
    assert activity is None
    assert status == "unavailable"
