from datetime import date, timedelta
from typing import Iterator
from garminview.ingestion.api_adapters.base_api import BaseAPIAdapter


class TrainingReadinessAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:training_readiness"

    def target_table(self) -> str:
        return "training_readiness"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_training_readiness", d.isoformat())
                if raw:
                    yield self._parse(d, raw)
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "score": raw.get("score"),
            "sleep_score": raw.get("sleepScore"),
            "recovery_score": raw.get("recoveryScore"),
            "training_load_score": raw.get("trainingLoadScore"),
            "hrv_score": raw.get("hrvScore"),
            "status": raw.get("level"),
        }


class TrainingStatusAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:training_status"

    def target_table(self) -> str:
        return "training_status"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_training_status", d.isoformat())
                if raw:
                    yield self._parse(d, raw)
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "status": raw.get("trainingStatusFeedback"),
            "load_ratio": raw.get("trainingLoadRatio"),
        }
