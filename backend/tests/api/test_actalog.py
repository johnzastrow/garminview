import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from garminview.api.main import create_app
from garminview.models.actalog import (
    ActalogWorkout, ActalogMovement, ActalogWorkoutMovement,
    ActalogWorkoutWod, ActalogWod,
)


def seed_workout(session, workout_id: int = 1) -> None:
    session.add(ActalogWorkout(
        id=workout_id,
        workout_date=datetime(2026, 1, 15, 9, 0),
        workout_name="Test",
        workout_type="strength",
        total_time_s=3600,
        synced_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    session.add(ActalogMovement(id=10, name="Back Squat", movement_type="weightlifting"))
    session.add(ActalogWorkoutMovement(
        id=101, workout_id=workout_id, movement_id=10,
        sets=3, reps=5, weight_kg=100.0, is_pr=True, order_index=1,
    ))
    session.commit()


@pytest.mark.asyncio
async def test_list_workouts_empty(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_workouts_returns_rows(engine, session):
    seed_workout(session)
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == 1


@pytest.mark.asyncio
async def test_workout_detail(engine, session):
    seed_workout(session)
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts/1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert len(body["movements"]) == 1
    assert body["movements"][0]["is_pr"] is True


@pytest.mark.asyncio
async def test_workout_not_found(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts/999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_session_vitals_no_duration(engine, session):
    """Workout with null total_time_s must return has_vitals=false."""
    session.add(ActalogWorkout(
        id=2, workout_date=datetime(2026, 1, 16, 9, 0),
        workout_name="No Duration", workout_type="metcon",
        total_time_s=None,
        synced_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    session.commit()
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/actalog/workouts/2/session-vitals")
    assert r.status_code == 200
    assert r.json()["has_vitals"] is False
    assert r.json()["workout"]["id"] == 2


@pytest.mark.asyncio
async def test_admin_config_get(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/admin/actalog/config")
    assert r.status_code == 200
    body = r.json()
    assert "url" in body
    assert "password" not in body  # must be masked/omitted


@pytest.mark.asyncio
async def test_admin_config_put(engine):
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.put("/admin/actalog/config", json={"url": "https://test.example", "email": "a@b.com"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


@pytest.mark.asyncio
async def test_trigger_sync_not_configured(engine):
    """POST /admin/actalog/sync must return 400 when Actalog is not configured."""
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/admin/actalog/sync")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_test_connection_missing_params(engine):
    """POST /admin/actalog/test-connection must return 400 when credentials are missing."""
    app = create_app(engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/admin/actalog/test-connection")
    assert r.status_code == 400
