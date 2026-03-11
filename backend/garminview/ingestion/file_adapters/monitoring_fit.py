import fitparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator
from garminview.ingestion.base import BaseAdapter

# Garmin FIT epoch: 1989-12-31 00:00:00 UTC
_FIT_EPOCH = datetime(1989, 12, 31)


def _resolve_timestamp(last_ts: datetime | None, data: dict) -> datetime | None:
    """Return an absolute timestamp from a monitoring message dict.

    FIT monitoring files use two timestamp schemes:
    - Full `timestamp`: absolute datetime (only on some messages)
    - `timestamp_16`: lower 16 bits of FIT-epoch seconds — must be resolved
      against the last seen full timestamp to get an absolute time.
    """
    ts = data.get("timestamp")
    if ts is not None:
        return ts

    ts16 = data.get("timestamp_16")
    if ts16 is None or last_ts is None:
        return None

    # Convert last full timestamp to FIT-epoch seconds
    fit_secs = int((last_ts - _FIT_EPOCH).total_seconds())
    # Clear lower 16 bits, fill in ts16, handle 16-bit wraparound (~18h)
    base = fit_secs & ~0xFFFF
    candidate = base | (ts16 & 0xFFFF)
    if candidate < fit_secs:
        candidate += 0x10000
    return _FIT_EPOCH + timedelta(seconds=candidate)


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
        # Files live in year subdirs: FitFiles/Monitoring/2024/*.fit
        # Only scan year directories that overlap with the requested date range.
        years = range(start_date.year, end_date.year + 1)
        for year in years:
            year_dir = self._data_dir / str(year)
            if not year_dir.is_dir():
                continue
            for path in sorted(year_dir.glob("*.fit")):
                yield from self._parse_fit(path, start_date, end_date)

    def _parse_fit(self, path: Path, start_date: date | None = None, end_date: date | None = None) -> Iterator[dict]:
        try:
            ff = fitparse.FitFile(str(path))
            last_ts: datetime | None = None

            for record in ff.get_messages("monitoring"):
                data = {f.name: f.value for f in record}
                ts = _resolve_timestamp(last_ts, data)
                if ts is None:
                    continue

                # Track last full timestamp for resolving subsequent timestamp_16 values
                if data.get("timestamp") is not None:
                    last_ts = ts
                else:
                    last_ts = ts  # resolved timestamp is still the new base

                # Skip records outside the requested date window
                if start_date and ts.date() < start_date:
                    continue
                if end_date and ts.date() > end_date:
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
