import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import garminview.models  # noqa: registers all models with Base.metadata
from garminview.core.database import Base
from garminview.api.main import create_app
from garminview.api import deps
from garminview.models.sync import SyncLog
from garminview.models.config import UserProfile, AppConfig
from garminview.models.actalog import ActalogNoteParse, ActalogWorkout


@pytest.fixture()
def make_client():
    """Factory: creates a TestClient backed by a fresh in-memory SQLite DB."""
    def _factory(seed=None):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        app = create_app(engine=engine)

        def override_db():
            with Session() as s:
                yield s

        app.dependency_overrides[deps.get_db] = override_db

        if seed:
            with Session() as s:
                seed(s)
                s.commit()

        return TestClient(app)
    return _factory


def _sync_row(**kwargs) -> SyncLog:
    """Build a SyncLog with sensible defaults, overridden by kwargs."""
    defaults = dict(
        started_at=datetime(2026, 3, 12, 10, 0, 0),
        finished_at=datetime(2026, 3, 12, 10, 0, 10),
        source="garmin_daily",
        mode="full",
        records_upserted=100,
        status="success",
    )
    defaults.update(kwargs)
    return SyncLog(**defaults)


def test_profile_missing_shows_profile_action(make_client):
    # No user_profile row → profile_setup action item must appear
    client = make_client()
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    action_keys = [i["action_key"] for i in resp.json() if i["item_type"] == "action"]
    assert "profile_setup" in action_keys


def test_complete_profile_no_profile_action(make_client):
    # Profile with both fields set → no profile_setup action item
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    action_keys = [i["action_key"] for i in resp.json() if i["item_type"] == "action"]
    assert "profile_setup" not in action_keys


def test_anomalies_action_when_unreviewed_flags_exist(make_client):
    # Anomalous monitoring HR reading (> 210 bpm, not excluded) → anomalies action appears
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        from datetime import datetime
        from garminview.models.monitoring import MonitoringHeartRate
        s.add(MonitoringHeartRate(timestamp=datetime(2026, 3, 12, 10, 0, 0), hr=215))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    items = resp.json()
    action_keys = [i["action_key"] for i in items if i["item_type"] == "action"]
    assert "anomalies" in action_keys
    anomaly_item = next(i for i in items if i.get("action_key") == "anomalies")
    assert anomaly_item["count"] == 1
    assert anomaly_item["link"] == "/admin"


def test_sync_history_appears(make_client):
    # Seeded sync_log row appears as a sync item with correct fields
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(_sync_row(source="garmin_daily", records_upserted=147))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    syncs = [i for i in resp.json() if i["item_type"] == "sync"]
    assert len(syncs) == 1
    assert syncs[0]["title"] == "Garmin daily sync"
    assert syncs[0]["records_upserted"] == 147
    assert syncs[0]["status"] == "success"


def test_sync_duration_computed(make_client):
    # duration_s = finished_at - started_at in seconds
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(_sync_row(
            started_at=datetime(2026, 3, 12, 10, 0, 0),
            finished_at=datetime(2026, 3, 12, 10, 0, 10),
        ))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    syncs = [i for i in resp.json() if i["item_type"] == "sync"]
    assert syncs[0]["duration_s"] == pytest.approx(10.0)


def test_limit_caps_sync_history(make_client):
    # limit=2 with 3 sync rows → only 2 sync items returned
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        for i in range(3):
            s.add(_sync_row(
                started_at=datetime(2026, 3, 12, 10, i, 0),
                finished_at=datetime(2026, 3, 12, 10, i, 5),
            ))
    client = make_client(seed)
    resp = client.get("/admin/tasks", params={"limit": 2})
    assert resp.status_code == 200
    syncs = [i for i in resp.json() if i["item_type"] == "sync"]
    assert len(syncs) == 2


def test_running_sync_has_null_duration(make_client):
    # finished_at = None → duration_s = None, status = "running"
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(_sync_row(finished_at=None, status="running", records_upserted=None))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    syncs = [i for i in resp.json() if i["item_type"] == "sync"]
    assert syncs[0]["duration_s"] is None
    assert syncs[0]["status"] == "running"


def test_actalog_review_when_pending_and_enabled(make_client):
    # Actalog enabled + 1 pending parse → actalog_review action with count=1
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(AppConfig(key="actalog_sync_enabled", value="true", category="actalog", data_type="string"))
        workout = ActalogWorkout(workout_name="Test WOD")
        s.add(workout)
        s.flush()
        s.add(ActalogNoteParse(workout_id=workout.id, parse_status="pending", raw_notes="squat 5x5"))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    items = resp.json()
    action_keys = [i["action_key"] for i in items if i["item_type"] == "action"]
    assert "actalog_review" in action_keys
    review = next(i for i in items if i.get("action_key") == "actalog_review")
    assert review["count"] == 1
    assert review["link"] == "/actalog"


def test_no_actalog_review_when_disabled(make_client):
    # Actalog disabled → actalog_review never shown, even if parses are pending
    def seed(s):
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(AppConfig(key="actalog_sync_enabled", value="false", category="actalog", data_type="string"))
        workout = ActalogWorkout(workout_name="Test WOD")
        s.add(workout)
        s.flush()
        s.add(ActalogNoteParse(workout_id=workout.id, parse_status="pending", raw_notes="squat 5x5"))
    client = make_client(seed)
    resp = client.get("/admin/tasks")
    action_keys = [i["action_key"] for i in resp.json() if i["item_type"] == "action"]
    assert "actalog_review" not in action_keys
