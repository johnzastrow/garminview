from datetime import date, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from garminview.ingestion.sync_logger import SyncLogger
from garminview.ingestion.file_adapters.daily_summary import DailySummaryAdapter
from garminview.ingestion.file_adapters.sleep import SleepAdapter
from garminview.ingestion.file_adapters.weight import WeightAdapter
from garminview.ingestion.file_adapters.rhr import RHRAdapter
from garminview.ingestion.file_adapters.monitoring_fit import MonitoringFitAdapter
from garminview.ingestion.file_adapters.activity_json import ActivityJsonAdapter
from garminview.ingestion.file_adapters.activity_fit import ActivityFitAdapter
from garminview.models.health import DailySummary
from garminview.core.logging import get_logger

log = get_logger(__name__)


class IngestionOrchestrator:
    def __init__(self, session: Session, health_data_dir: str | Path,
                 garmin_client=None):
        self._session = session
        self._data_dir = Path(health_data_dir).expanduser()
        self._garmin_client = garmin_client

    def run_full(self, start_date: date, end_date: date) -> None:
        self._run_file_adapters(start_date, end_date)
        if self._garmin_client:
            self._run_api_adapters(start_date, end_date)

    def run_incremental(self) -> None:
        last = self._get_last_sync_date()
        end = date.today()
        self.run_full(last, end)

    def run_analysis_only(self) -> None:
        from garminview.analysis.engine import AnalysisEngine
        AnalysisEngine(self._session).run_all()

    def _get_last_sync_date(self) -> date:
        result = self._session.execute(
            select(func.max(DailySummary.date))
        ).scalar()
        return result - timedelta(days=3) if result else date(2020, 1, 1)

    def _run_file_adapters(self, start_date: date, end_date: date) -> None:
        adapters = [
            DailySummaryAdapter(self._data_dir / "monitoring"),
            SleepAdapter(self._data_dir / "sleep"),
            WeightAdapter(self._data_dir / "weight"),
            RHRAdapter(self._data_dir / "rhr"),
            MonitoringFitAdapter(self._data_dir / "monitoring"),
            ActivityJsonAdapter(self._data_dir / "activities"),
            ActivityFitAdapter(self._data_dir / "activities"),
        ]
        for adapter in adapters:
            sync_log = SyncLogger(self._session, adapter.source_name(),
                                  "incremental", start_date, end_date)
            try:
                count = self._upsert_adapter(adapter, start_date, end_date)
                sync_log.increment(count)
                sync_log.success()
            except Exception as e:
                log.error("adapter_failed", source=adapter.source_name(), error=str(e))
                sync_log.fail(str(e))

    def _upsert_adapter(self, adapter, start_date: date, end_date: date) -> int:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        count = 0
        table = adapter.target_table()
        model = self._get_model_for_table(table)
        for record in adapter.fetch(start_date, end_date):
            stmt = sqlite_insert(model).values(**record)
            stmt = stmt.on_conflict_do_update(
                index_elements=self._get_pk_columns(model),
                set_=record,
            )
            self._session.execute(stmt)
            count += 1
        self._session.commit()
        return count

    def _get_model_for_table(self, table_name: str):
        import garminview.models as m
        TABLE_MAP = {
            "daily_summary": m.DailySummary,
            "sleep": m.Sleep,
            "sleep_events": m.SleepEvent,
            "weight": m.Weight,
            "resting_heart_rate": m.RestingHeartRate,
            "monitoring_heart_rate": m.MonitoringHeartRate,
            "activities": m.Activity,
        }
        return TABLE_MAP[table_name]

    def _get_pk_columns(self, model) -> list:
        from sqlalchemy import inspect
        return [c.key for c in inspect(model).primary_key]

    def _run_api_adapters(self, start_date: date, end_date: date) -> None:
        pass  # populated in Task 11
