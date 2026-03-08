from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from garminview.models.sync import SyncLog


class SyncLogger:
    def __init__(self, session: Session, source: str, mode: str,
                 date_start: date | None = None, date_end: date | None = None):
        self._session = session
        self._log = SyncLog(
            started_at=datetime.now(timezone.utc),
            source=source,
            mode=mode,
            date_start=date_start,
            date_end=date_end,
            status="running",
            records_upserted=0,
        )
        session.add(self._log)
        session.commit()

    def increment(self, count: int = 1) -> None:
        self._log.records_upserted = (self._log.records_upserted or 0) + count
        self._session.commit()

    def success(self) -> None:
        self._log.finished_at = datetime.now(timezone.utc)
        self._log.status = "success"
        self._session.commit()

    def fail(self, error: str) -> None:
        self._log.finished_at = datetime.now(timezone.utc)
        self._log.status = "failed"
        self._log.error_message = error
        self._session.commit()
