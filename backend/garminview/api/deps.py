from sqlalchemy.orm import Session
from garminview.core.database import get_session_factory


def get_db() -> Session:
    """Sentinel dependency — overridden at app creation time via dependency_overrides."""
    raise RuntimeError("get_db not wired — call create_app() to initialize")
