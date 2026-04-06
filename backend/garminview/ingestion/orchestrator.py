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
from garminview.ingestion.file_adapters.garmindb_hr_zones import GarminDBHRZonesAdapter
from garminview.ingestion.file_adapters.garmindb_monitoring import (
    GarminDBRespirationAdapter, GarminDBPulseOxAdapter, GarminDBClimbAdapter,
    GarminDBIntensityAdapter, GarminDBStepsAdapter,
)
from garminview.ingestion.file_adapters.garmindb_sleep_events import GarminDBSleepEventsAdapter
from garminview.ingestion.file_adapters.garmindb_stress import GarminDBStressAdapter
from garminview.ingestion.file_adapters.garmindb_steps_activities import GarminDBStepsActivitiesAdapter
from garminview.ingestion.file_adapters.garmindb_activity_laps import GarminDBActivityLapsAdapter
from garminview.models.health import DailySummary
from garminview.core.logging import get_logger

log = get_logger(__name__)


class IngestionOrchestrator:
    def __init__(self, session: Session, health_data_dir: str | Path,
                 garmin_client=None, mfp_data_dir: str | Path | None = None):
        self._session = session
        self._data_dir = Path(health_data_dir).expanduser()
        self._garmin_client = garmin_client
        self._mfp_data_dir = Path(mfp_data_dir).expanduser() if mfp_data_dir else None

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
        # sleep_events uses autoincrement PK — delete range then re-insert
        sleep_events_adapter = GarminDBSleepEventsAdapter(self._data_dir)
        sync_log = SyncLogger(self._session, sleep_events_adapter.source_name(),
                              "incremental", start_date, end_date)
        try:
            from sqlalchemy import text
            self._session.execute(
                text("DELETE FROM sleep_events WHERE date >= :s AND date <= :e"),
                {"s": start_date, "e": end_date},
            )
            self._session.commit()
            count = self._upsert_adapter(sleep_events_adapter, start_date, end_date)
            sync_log.increment(count)
            sync_log.success()
        except Exception as e:
            log.error("adapter_failed", source=sleep_events_adapter.source_name(), error=str(e))
            sync_log.fail(str(e))

        adapters = [
            DailySummaryAdapter(self._data_dir / "FitFiles" / "Monitoring"),
            SleepAdapter(self._data_dir / "Sleep"),
            WeightAdapter(self._data_dir / "Weight"),
            RHRAdapter(self._data_dir / "RHR"),
            MonitoringFitAdapter(self._data_dir / "FitFiles" / "Monitoring"),
            ActivityJsonAdapter(self._data_dir / "FitFiles" / "Activities"),
            ActivityFitAdapter(self._data_dir / "FitFiles" / "Activities"),
            GarminDBHRZonesAdapter(self._data_dir),
            GarminDBRespirationAdapter(self._data_dir),
            GarminDBPulseOxAdapter(self._data_dir),
            GarminDBClimbAdapter(self._data_dir),
            GarminDBIntensityAdapter(self._data_dir),
            GarminDBStepsAdapter(self._data_dir),
            GarminDBStressAdapter(self._data_dir),
            GarminDBStepsActivitiesAdapter(self._data_dir),
            GarminDBActivityLapsAdapter(self._data_dir),
        ]
        if self._mfp_data_dir:
            from garminview.ingestion.file_adapters.mfp_nutrition import (
                MFPNutritionAdapter, MFPFoodDiaryAdapter, MFPMeasurementAdapter
            )
            adapters += [
                MFPNutritionAdapter(self._mfp_data_dir),
                MFPMeasurementAdapter(self._mfp_data_dir),
            ]
            # Food diary uses autoincrement PK — delete existing rows for the date
            # range first, then insert fresh to avoid duplicates.
            food_diary_adapter = MFPFoodDiaryAdapter(self._mfp_data_dir)
            sync_log = SyncLogger(self._session, food_diary_adapter.source_name(),
                                  "incremental", start_date, end_date)
            try:
                from sqlalchemy import text
                self._session.execute(
                    text("DELETE FROM mfp_food_diary WHERE date >= :s AND date <= :e"),
                    {"s": start_date, "e": end_date},
                )
                self._session.commit()
                count = self._upsert_adapter(food_diary_adapter, start_date, end_date)
                sync_log.increment(count)
                sync_log.success()
            except Exception as e:
                log.error("adapter_failed", source=food_diary_adapter.source_name(), error=str(e))
                sync_log.fail(str(e))

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

    _BATCH_SIZE = 500

    def _upsert_adapter(self, adapter, start_date: date, end_date: date) -> int:
        from sqlalchemy import inspect as sa_inspect
        table = adapter.target_table()
        model = self._get_model_for_table(table)
        valid_cols = {c.key for c in sa_inspect(model).mapper.column_attrs}
        pk_cols = self._get_pk_columns(model)
        dialect = self._session.bind.dialect.name  # "sqlite" or "mysql"

        batch: list[dict] = []
        count = 0

        def _flush(rows: list[dict]) -> None:
            if not rows:
                return
            if dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as _insert
                stmt = _insert(model).values(rows)
                non_pk = [c for c in rows[0] if c not in pk_cols]
                stmt = stmt.on_conflict_do_update(
                    index_elements=pk_cols,
                    set_={col: getattr(stmt.excluded, col) for col in non_pk},
                )
            else:
                from sqlalchemy.dialects.mysql import insert as _insert
                stmt = _insert(model).values(rows)
                non_pk = [c for c in rows[0] if c not in pk_cols]
                stmt = stmt.on_duplicate_key_update(
                    **{col: stmt.inserted[col] for col in non_pk}
                )
            self._session.execute(stmt)

        for record in adapter.fetch(start_date, end_date):
            row = {k: v for k, v in record.items() if k in valid_cols}
            if not row:
                continue
            # Skip rows where all non-PK payload columns are None (e.g. steps-only
            # monitoring messages that carry no HR data).
            non_pk_vals = {k: v for k, v in row.items() if k not in pk_cols}
            if non_pk_vals and all(v is None for v in non_pk_vals.values()):
                continue
            batch.append(row)
            count += 1
            if len(batch) >= self._BATCH_SIZE:
                _flush(batch)
                batch = []

        _flush(batch)
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
            "monitoring_intensity": m.MonitoringIntensity,
            "monitoring_steps": m.MonitoringSteps,
            "monitoring_respiration": m.MonitoringRespiration,
            "monitoring_pulse_ox": m.MonitoringPulseOx,
            "monitoring_climb": m.MonitoringClimb,
            "stress": m.Stress,
            "activities": m.Activity,
            "activity_laps": m.ActivityLap,
            "activity_records": m.ActivityRecord,
            "steps_activities": m.StepsActivity,
            "activity_hr_zones": m.ActivityHRZone,
            "mfp_daily_nutrition": m.MFPDailyNutrition,
            "mfp_food_diary": m.MFPFoodDiaryEntry,
            "mfp_measurements": m.MFPMeasurement,
            "mfp_exercises": m.MFPExercise,
        }
        if table_name not in TABLE_MAP:
            raise KeyError(f"No model mapped for table '{table_name}'. Add it to TABLE_MAP.")
        return TABLE_MAP[table_name]

    def _get_pk_columns(self, model) -> list:
        from sqlalchemy import inspect
        return [c.key for c in inspect(model).primary_key]

    def _run_api_adapters(self, start_date: date, end_date: date) -> None:
        from garminview.models.config import AppConfig

        def _cfg(key: str) -> str | None:
            row = self._session.get(AppConfig, key)
            return row.value if row else None

        email = _cfg("garmin_email")
        password = _cfg("garmin_password")
        if not email or not password:
            log.warning("garmin_api_skipped",
                        reason="garmin_email/garmin_password not set in app_config")
            return

        try:
            from garminconnect import Garmin
            client = Garmin(email, password)
            client.login()
        except Exception as exc:
            log.error("garmin_login_failed", error=str(exc))
            return

        from garminview.ingestion.api_adapters.hrv import HRVAdapter
        from garminview.ingestion.api_adapters.training import (
            TrainingReadinessAdapter, TrainingStatusAdapter,
        )
        from garminview.ingestion.api_adapters.body import (
            VO2MaxAdapter, BodyCompositionAdapter, BloodPressureAdapter,
            PersonalRecordsAdapter, GearAdapter,
        )
        from garminview.ingestion.api_adapters.performance import (
            RacePredictionsAdapter, LactateThresholdAdapter,
        )

        api_adapters = [
            HRVAdapter(client),
            TrainingReadinessAdapter(client),
            TrainingStatusAdapter(client),
            VO2MaxAdapter(client),
            BodyCompositionAdapter(client),
            BloodPressureAdapter(client),
            PersonalRecordsAdapter(client),
            GearAdapter(client),
            RacePredictionsAdapter(client),
            LactateThresholdAdapter(client),
        ]

        for adapter in api_adapters:
            sync_log = SyncLogger(self._session, adapter.source_name(),
                                  "incremental", start_date, end_date)
            try:
                count = self._upsert_adapter(adapter, start_date, end_date)
                sync_log.increment(count)
                sync_log.success()
            except Exception as exc:
                log.error("api_adapter_failed",
                          source=adapter.source_name(), error=str(exc))
                sync_log.fail(str(exc))
