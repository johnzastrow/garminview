import fitparse
from datetime import date
from pathlib import Path
from typing import Iterator
from garminview.ingestion.base import BaseAdapter


class MonitoringFitAdapter(BaseAdapter):
    """Parses monitoring FIT files → monitoring_heart_rate, monitoring_steps,
    monitoring_intensity, monitoring_respiration, monitoring_pulse_ox, monitoring_climb."""

    def __init__(self, data_dir: str | Path):
        self._data_dir = Path(data_dir).expanduser()

    def source_name(self) -> str:
        return "garmin_files:monitoring_fit"

    def target_table(self) -> str:
        return "monitoring_heart_rate"  # primary; others written by orchestrator

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        # Files live in year subdirs: FitFiles/Monitoring/2024/*_WELLNESS.fit
        for path in sorted(self._data_dir.rglob("*.fit")):
            yield from self._parse_fit(path)

    def _parse_fit(self, path: Path) -> Iterator[dict]:
        try:
            ff = fitparse.FitFile(str(path))
            for record in ff.get_messages("monitoring"):
                data = {f.name: f.value for f in record}
                ts = data.get("timestamp")
                if not ts:
                    continue
                yield {
                    "type": "heart_rate",
                    "timestamp": ts,
                    "hr": data.get("heart_rate"),
                    "steps": data.get("steps"),
                    "activity_type": str(data.get("activity_type", "")),
                    "moderate_time_s": data.get("moderate_activity_time"),
                    "vigorous_time_s": data.get("vigorous_activity_time"),
                    "ascent_m": data.get("ascent"),
                    "descent_m": data.get("descent"),
                    "cum_ascent_m": data.get("cum_ascent"),
                    "cum_descent_m": data.get("cum_descent"),
                    "rr": data.get("respiration_rate"),
                    "spo2": data.get("pulse_ox"),
                }
        except Exception as e:
            from garminview.core.logging import get_logger
            get_logger(__name__).warning("fit_parse_error", path=str(path), error=str(e))
