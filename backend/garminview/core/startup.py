from datetime import datetime, timezone
from sqlalchemy.orm import Session
from garminview.models.sync import SchemaVersion

CURRENT_SCHEMA_VERSION = "20260307_001"


def check_schema_version(session: Session) -> None:
    latest = (session.query(SchemaVersion)
              .order_by(SchemaVersion.applied_at.desc()).first())
    if latest and latest.version != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Schema version mismatch: DB has {latest.version}, "
            f"code expects {CURRENT_SCHEMA_VERSION}. Run: alembic upgrade head"
        )


def record_migration(session: Session, version: str, description: str) -> None:
    session.add(SchemaVersion(
        version=version,
        description=description,
        applied_at=datetime.now(timezone.utc),
        applied_by="alembic",
    ))
    session.commit()
