import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import garminview.models  # noqa: F401 — registers all models with Base.metadata
from garminview.core.database import Base
from garminview.core.config import Config, DBBackend


@pytest.fixture(scope="function")
def test_config():
    return Config(db_backend=DBBackend.sqlite, db_path=":memory:")


@pytest.fixture(scope="function")
def engine(test_config):
    from garminview.core.database import create_db_engine
    eng = create_db_engine(test_config)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def session(engine):
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
