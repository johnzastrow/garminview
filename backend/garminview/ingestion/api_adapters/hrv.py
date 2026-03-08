from datetime import date, timedelta
from typing import Iterator
from garminview.ingestion.api_adapters.base_api import BaseAPIAdapter


class HRVAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:hrv"

    def target_table(self) -> str:
        return "hrv_data"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_hrv_data", d.isoformat())
                if raw:
                    yield self._parse(d, raw)
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        summary = raw.get("hrvSummary", {})
        return {
            "date": d,
            "hrv_rmssd": summary.get("rmssd"),
            "hrv_5min_high": summary.get("highFrequency"),
            "hrv_5min_low": summary.get("lowFrequency"),
            "baseline_low": summary.get("baselineLowUpper"),
            "baseline_high": summary.get("baselineBalancedUpper"),
            "status": summary.get("status"),
        }
