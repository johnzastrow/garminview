import pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import garminview.models  # noqa: registers all models
from garminview.core.database import Base
from garminview.api.main import create_app
from garminview.api import deps
from garminview.models.health import DailyHRZones
from garminview.models.config import UserProfile
from garminview.models.monitoring import MonitoringHeartRate


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    app = create_app(engine=engine)

    def override_db():
        with factory() as s:
            yield s

    app.dependency_overrides[deps.get_db] = override_db

    with factory() as s:
        s.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
        s.add(MonitoringHeartRate(timestamp=datetime(2026, 1, 10, 8, 0), hr=140))
        s.add(MonitoringHeartRate(timestamp=datetime(2026, 1, 10, 8, 1), hr=150))
        s.add(MonitoringHeartRate(timestamp=datetime(2026, 1, 10, 8, 2), hr=250))  # outlier
        s.add(DailyHRZones(
            date=date(2026, 1, 10),
            z1_min=0, z2_min=5, z3_min=3, z4_min=1, z5_min=0,
            valid_max_hr=158, raw_max_hr=250,
            rejected_count=1, total_count=3,
            zone_method="karvonen",
            computed_at=datetime.now(timezone.utc),
        ))
        s.commit()

    return TestClient(app)


def test_hr_zones_returns_list(client):
    resp = client.get("/health/hr-zones", params={"start": "2026-01-01", "end": "2026-01-31"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    row = data[0]
    assert row["date"] == "2026-01-10"
    assert row["z2_min"] == 5
    assert row["z3_min"] == 3
    assert row["valid_max_hr"] == 158
    assert row["raw_max_hr"] == 250
    assert row["rejected_count"] == 1


def test_hr_zones_empty_range_returns_empty(client):
    resp = client.get("/health/hr-zones", params={"start": "2025-01-01", "end": "2025-01-31"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_hr_zones_no_params_returns_data(client):
    resp = client.get("/health/hr-zones")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
