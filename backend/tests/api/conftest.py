"""Shared helpers for API route tests.

Provides a `make_client` factory that builds a FastAPI TestClient backed by a
fresh in-memory SQLite database, with the `get_db` dependency overridden so the
app and the test share the same engine. Mirrors the wiring used by
`test_hr_zones_api.py` / `test_admin_tasks.py`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import garminview.models  # noqa: F401 — registers all models with Base.metadata
from garminview.core.database import Base
from garminview.api.main import create_app
from garminview.api import deps


@pytest.fixture()
def make_client():
    """Factory: creates a TestClient backed by a fresh in-memory SQLite DB.

    Pass an optional ``seed(session)`` callable to populate rows before the
    client is returned. The callable runs inside a committed session.
    """
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

        # TestClient without a `with` block does not trigger the lifespan, so
        # the APScheduler is never started — keeps these tests hermetic.
        return TestClient(app)

    return _factory
