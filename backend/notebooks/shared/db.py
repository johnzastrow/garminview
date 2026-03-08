from sqlalchemy.orm import Session
from garminview.core.config import get_config
from garminview.core.database import create_db_engine, get_session_factory


def get_notebook_session() -> Session:
    """Get a DB session for notebook use, reading config from env/.env"""
    config = get_config()
    engine = create_db_engine(config)
    factory = get_session_factory(engine)
    return factory()
