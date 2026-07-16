"""API tests for the Garmin activity-matching endpoints and the session-vitals
HR-window anchoring that resolve_activity() drives.

Uses the in-memory ``make_client`` factory from ``tests/api/conftest.py``.
"""
from datetime import datetime

from garminview.models.activities import Activity
from garminview.models.actalog import ActalogWorkout
from garminview.models.monitoring import MonitoringHeartRate


def _seed_workout_and_activities(session):
    # Workout: date-only midnight, 1800s duration.
    session.add(ActalogWorkout(
        id=1,
        workout_date=datetime(2024, 1, 15, 0, 0),
        workout_name="Squats",
        workout_type="strength",
        total_time_s=1800,
    ))
    # One clear-winner activity (10s off) + a far-off one.
    session.add(Activity(
        activity_id=100, start_time=datetime(2024, 1, 15, 7, 0),
        elapsed_time_s=1790, sport="strength_training", avg_hr=130, max_hr=165,
        distance_m=0.0, calories=250, source="garmin_fit",
    ))
    session.add(Activity(
        activity_id=200, start_time=datetime(2024, 1, 15, 18, 0),
        elapsed_time_s=600, sport="walking", avg_hr=95, max_hr=110,
        distance_m=800.0, calories=60, source="garmin_fit",
    ))


# ── GET /match-candidates ────────────────────────────────────────────


def test_get_match_candidates(make_client):
    client = make_client(seed=_seed_workout_and_activities)
    r = client.get("/actalog/workouts/1/match-candidates")
    assert r.status_code == 200
    body = r.json()
    assert body["workout_date"].startswith("2024-01-15")
    # Clear winner -> auto, anchored on activity 100.
    assert body["current"]["status"] == "auto"
    assert body["current"]["activity"]["activity_id"] == 100
    assert body["current"]["activity"]["start_time"].startswith("2024-01-15T07:00")
    # Both same-day activities are candidates, sorted by start_time asc.
    assert [c["activity_id"] for c in body["candidates"]] == [100, 200]


def test_get_match_candidates_missing_workout(make_client):
    client = make_client(seed=_seed_workout_and_activities)
    r = client.get("/actalog/workouts/999/match-candidates")
    assert r.status_code == 404


# ── POST /match ──────────────────────────────────────────────────────


def test_post_match_sets_link(make_client):
    client = make_client(seed=_seed_workout_and_activities)
    r = client.post("/actalog/workouts/1/match", json={"activity_id": 200})
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["status"] == "linked"
    assert body["current"]["activity"]["activity_id"] == 200

    # Re-fetch: the confirmed link persists (not the auto winner 100).
    r2 = client.get("/actalog/workouts/1/match-candidates")
    assert r2.json()["current"]["status"] == "linked"
    assert r2.json()["current"]["activity"]["activity_id"] == 200


def test_post_match_null_returns_none(make_client):
    client = make_client(seed=_seed_workout_and_activities)
    r = client.post("/actalog/workouts/1/match", json={"activity_id": None})
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["status"] == "none"
    assert body["current"]["activity"] is None
    # Candidates still enumerated for a possible re-pick.
    assert [c["activity_id"] for c in body["candidates"]] == [100, 200]


def test_post_match_missing_workout(make_client):
    client = make_client(seed=_seed_workout_and_activities)
    r = client.post("/actalog/workouts/999/match", json={"activity_id": 100})
    assert r.status_code == 404


def test_post_match_bad_activity_id(make_client):
    client = make_client(seed=_seed_workout_and_activities)
    r = client.post("/actalog/workouts/1/match", json={"activity_id": 12345})
    assert r.status_code == 400


# ── session-vitals HR-window anchoring ───────────────────────────────


def test_session_vitals_anchors_to_matched_activity_window(make_client):
    """HR is pulled from the matched activity's real window (07:00), not the
    midnight/noon fallback."""

    def seed(session):
        _seed_workout_and_activities(session)
        # HR sample inside the activity window (07:10) — should be included.
        session.add(MonitoringHeartRate(timestamp=datetime(2024, 1, 15, 7, 10), hr=140))
        # HR sample at noon — outside the 07:00–07:30 activity window; must be
        # excluded, proving we anchored on the activity and not on noon.
        session.add(MonitoringHeartRate(timestamp=datetime(2024, 1, 15, 12, 5), hr=70))

    client = make_client(seed=seed)
    r = client.get("/actalog/workouts/1/session-vitals")
    assert r.status_code == 200
    body = r.json()
    assert body["has_vitals"] is True
    hrs = [p["hr"] for p in body["hr_series"]]
    assert hrs == [140]  # only the in-activity-window sample


def test_session_vitals_noon_fallback_when_no_match(make_client):
    """With no Garmin activity on the date, the window anchors to NOON, so a
    noon-adjacent HR sample is included and a morning one is not."""

    def seed(session):
        session.add(ActalogWorkout(
            id=1,
            workout_date=datetime(2024, 3, 1, 0, 0),
            workout_name="Solo",
            workout_type="cardio",
            total_time_s=1800,
        ))
        # Noon-window sample (12:10) — included by the noon anchor.
        session.add(MonitoringHeartRate(timestamp=datetime(2024, 3, 1, 12, 10), hr=120))
        # Early-morning sample (00:10) — would be caught by a midnight anchor,
        # must be excluded now.
        session.add(MonitoringHeartRate(timestamp=datetime(2024, 3, 1, 0, 10), hr=55))

    client = make_client(seed=seed)
    r = client.get("/actalog/workouts/1/session-vitals")
    assert r.status_code == 200
    body = r.json()
    hrs = [p["hr"] for p in body["hr_series"]]
    assert hrs == [120]  # noon window only
