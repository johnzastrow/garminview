import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

import garminview.models  # noqa: F401 — registers all models with Base.metadata
from garminview.core.database import Base
from garminview.core.config import Config, DBBackend


@pytest.fixture(scope="function")
def test_config():
    return Config(db_backend=DBBackend.sqlite, db_path=":memory:")


@pytest.fixture(scope="function")
def engine(test_config):
    # StaticPool keeps a single in-memory connection shared across all
    # sessions — required for in-memory SQLite so all connections see the
    # same tables created by Base.metadata.create_all().
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def session(engine):
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
