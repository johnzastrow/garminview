from datetime import date, timedelta
from typing import Iterator
from garminview.ingestion.api_adapters.base_api import BaseAPIAdapter


class VO2MaxAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:vo2max"

    def target_table(self) -> str:
        return "vo2max"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        d = start_date
        while d <= end_date:
            try:
                raw = self._call("get_max_metrics", d.isoformat())
                if raw:
                    yield self._parse(d, raw)
            except Exception:
                pass
            d += timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "vo2max_running": raw.get("vo2MaxPreciseValue"),
            "vo2max_cycling": raw.get("vo2MaxCyclingPreciseValue"),
            "fitness_age": raw.get("fitnessAge"),
        }


class BodyCompositionAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:body_composition"

    def target_table(self) -> str:
        return "body_composition"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        # Garmin API chunks by 28 days
        chunk_start = start_date
        while chunk_start <= end_date:
            chunk_end = min(end_date, chunk_start + timedelta(days=28))
            try:
                results = self._call("get_body_composition",
                                     chunk_start.isoformat(), chunk_end.isoformat())
                for raw in (results or []):
                    d_str = raw.get("calendarDate")
                    if d_str:
                        yield self._parse(date.fromisoformat(d_str), raw)
            except Exception:
                pass
            chunk_start = chunk_end + timedelta(days=1)

    def _parse(self, d: date, raw: dict) -> dict:
        return {
            "date": d,
            "weight_kg": raw.get("weight"),
            "fat_pct": raw.get("fatPercent"),
            "muscle_mass_kg": raw.get("muscleMass"),
            "bone_mass_kg": raw.get("boneMass"),
            "hydration_pct": raw.get("bodyWater"),
            "bmi": raw.get("bmi"),
            "bmr": raw.get("bmr"),
            "metabolic_age": raw.get("metabolicAge"),
            "visceral_fat": raw.get("visceralFat"),
            "physique_rating": raw.get("physiqueRating"),
            "source": "garmin",
        }


class BloodPressureAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:blood_pressure"

    def target_table(self) -> str:
        return "blood_pressure"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        try:
            results = self._call("get_blood_pressure",
                                 start_date.isoformat(), end_date.isoformat())
            for raw in (results or []):
                ts = raw.get("measurementTimestampGMT")
                if ts:
                    from datetime import datetime, timezone
                    yield {
                        "timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                        "systolic": raw.get("systolic"),
                        "diastolic": raw.get("diastolic"),
                        "pulse": raw.get("pulse"),
                    }
        except Exception:
            pass


class PersonalRecordsAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:personal_records"

    def target_table(self) -> str:
        return "personal_records"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        try:
            results = self._call("get_personal_records", "")
            for raw in (results or []):
                d_str = raw.get("prStartDate") or raw.get("updateDate")
                yield {
                    "activity_type": raw.get("activityType"),
                    "metric": raw.get("typeId"),
                    "value": raw.get("value"),
                    "achieved_date": date.fromisoformat(d_str) if d_str else None,
                }
        except Exception:
            pass


class GearAdapter(BaseAPIAdapter):
    def source_name(self) -> str:
        return "garmin_api:gear"

    def target_table(self) -> str:
        return "gear"

    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        try:
            results = self._call("get_gear", "")
            for raw in (results or []):
                uuid = raw.get("uuid")
                if not uuid:
                    continue
                yield {
                    "gear_uuid": uuid,
                    "name": raw.get("displayName"),
                    "type": raw.get("gearTypeName"),
                    "status": raw.get("gearStatusName"),
                    "date_begin": date.fromisoformat(raw["dateBegin"]) if raw.get("dateBegin") else None,
                    "date_end": date.fromisoformat(raw["dateEnd"]) if raw.get("dateEnd") else None,
                }
        except Exception:
            pass
