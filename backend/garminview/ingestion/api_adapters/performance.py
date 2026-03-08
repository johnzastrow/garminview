from datetime import date, timedelta
from typing import Iterator
from garminview.ingestion.api_adapters.base_api import BaseAPIAdapter


class RacePredictionsAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:race_predictions"

    def target_table(self) -> str:
        return "race_predictions"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_race_predictions")
                if raw:
                    yield self._parse(d, raw)
                    break  # race predictions aren't per-day
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "pred_5k_s": raw.get("time5K"),
            "pred_10k_s": raw.get("time10K"),
            "pred_half_s": raw.get("timeHalfMarathon"),
            "pred_full_s": raw.get("timeMarathon"),
        }


class LactateThresholdAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:lactate_threshold"

    def target_table(self) -> str:
        return "lactate_threshold"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_lactate_threshold")
                if raw:
                    yield self._parse(d, raw)
                    break
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "lt_speed": raw.get("speed"),
            "lt_hr": raw.get("heartRate"),
            "lt_power": raw.get("power"),
        }
