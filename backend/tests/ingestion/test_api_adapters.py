"""Tests for the Garmin API adapters (body / training / performance).

The adapters transform Garmin Connect JSON payloads into record dicts. We test
the pure ``_parse`` mapping directly, and drive ``fetch`` with a fake client so
no network is touched. Empty / partial payloads must degrade to None fields.
"""

from datetime import date, datetime, timezone

import pytest

from garminview.ingestion.api_adapters.body import (
    BloodPressureAdapter,
    BodyCompositionAdapter,
    GearAdapter,
    PersonalRecordsAdapter,
    VO2MaxAdapter,
)
from garminview.ingestion.api_adapters.performance import (
    LactateThresholdAdapter,
    RacePredictionsAdapter,
)
from garminview.ingestion.api_adapters.training import (
    TrainingReadinessAdapter,
    TrainingStatusAdapter,
)


class FakeClient:
    """Stand-in for garminconnect.Garmin: each method returns canned data."""

    def __init__(self, **responses):
        self._responses = responses

    def __getattr__(self, name):
        # Return a callable that yields the canned response for `name`.
        resp = self._responses.get(name)

        def _method(*args, **kwargs):
            if isinstance(resp, Exception):
                raise resp
            return resp

        return _method


D = date(2024, 1, 15)


# ── VO2Max ───────────────────────────────────────────────────────────


def test_vo2max_parse():
    raw = {
        "vo2MaxPreciseValue": 52.3,
        "vo2MaxCyclingPreciseValue": 48.1,
        "fitnessAge": 35,
    }
    out = VO2MaxAdapter(None)._parse(D, raw)
    assert out == {
        "date": D,
        "vo2max_running": 52.3,
        "vo2max_cycling": 48.1,
        "fitness_age": 35,
    }


def test_vo2max_parse_empty():
    out = VO2MaxAdapter(None)._parse(D, {})
    assert out["vo2max_running"] is None
    assert out["fitness_age"] is None
    assert out["date"] == D


def test_vo2max_fetch_iterates_days():
    client = FakeClient(get_max_metrics={"vo2MaxPreciseValue": 50.0})
    rows = list(VO2MaxAdapter(client).fetch(D, date(2024, 1, 17)))
    assert len(rows) == 3  # inclusive 3-day span
    assert all(r["vo2max_running"] == 50.0 for r in rows)
    assert [r["date"] for r in rows] == [
        date(2024, 1, 15),
        date(2024, 1, 16),
        date(2024, 1, 17),
    ]


def test_vo2max_fetch_skips_empty_responses():
    client = FakeClient(get_max_metrics=None)
    assert list(VO2MaxAdapter(client).fetch(D, date(2024, 1, 17))) == []


# ── Body composition ─────────────────────────────────────────────────


def test_body_composition_parse():
    raw = {
        "weight": 75.0,
        "fatPercent": 18.0,
        "muscleMass": 60.0,
        "boneMass": 3.2,
        "bodyWater": 55.0,
        "bmi": 23.1,
        "bmr": 1700,
        "metabolicAge": 30,
        "visceralFat": 7,
        "physiqueRating": 5,
    }
    out = BodyCompositionAdapter(None)._parse(D, raw)
    assert out["weight_kg"] == 75.0
    assert out["fat_pct"] == 18.0
    assert out["muscle_mass_kg"] == 60.0
    assert out["hydration_pct"] == 55.0
    assert out["source"] == "garmin"


def test_body_composition_fetch_uses_calendar_date():
    client = FakeClient(
        get_body_composition=[
            {"calendarDate": "2024-01-15", "weight": 75.0},
            {"calendarDate": "2024-01-16", "weight": 74.5},
            {"weight": 99.0},  # missing calendarDate -> skipped
        ]
    )
    rows = list(BodyCompositionAdapter(client).fetch(D, date(2024, 1, 20)))
    assert len(rows) == 2
    assert rows[0]["date"] == date(2024, 1, 15)
    assert rows[1]["date"] == date(2024, 1, 16)


# ── Blood pressure ───────────────────────────────────────────────────


def test_blood_pressure_fetch_maps_timestamp():
    ts_ms = int(datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    client = FakeClient(
        get_blood_pressure=[
            {
                "measurementTimestampGMT": ts_ms,
                "systolic": 120,
                "diastolic": 80,
                "pulse": 60,
            },
            {"systolic": 130},  # no timestamp -> skipped
        ]
    )
    rows = list(BloodPressureAdapter(client).fetch(D, date(2024, 1, 20)))
    assert len(rows) == 1
    assert rows[0]["systolic"] == 120
    assert rows[0]["diastolic"] == 80
    assert rows[0]["timestamp"] == datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_blood_pressure_fetch_empty():
    client = FakeClient(get_blood_pressure=None)
    assert list(BloodPressureAdapter(client).fetch(D, date(2024, 1, 20))) == []


# ── Personal records ─────────────────────────────────────────────────


def test_personal_records_fetch():
    client = FakeClient(
        get_personal_records=[
            {
                "activityType": "running",
                "typeId": 1,
                "value": 1200.0,
                "prStartDate": "2024-01-10",
            },
            {
                "activityType": "cycling",
                "typeId": 7,
                "value": 3600.0,
                "updateDate": "2024-01-11",
            },
            {"activityType": "swim", "typeId": 3, "value": 900.0},  # no date -> None
        ]
    )
    rows = list(PersonalRecordsAdapter(client).fetch(D, date(2024, 1, 20)))
    assert len(rows) == 3
    assert rows[0]["achieved_date"] == date(2024, 1, 10)
    assert rows[1]["achieved_date"] == date(2024, 1, 11)  # falls back to updateDate
    assert rows[2]["achieved_date"] is None


# ── Gear ─────────────────────────────────────────────────────────────


def test_gear_fetch_skips_uuidless_rows():
    client = FakeClient(
        get_gear=[
            {
                "uuid": "abc",
                "displayName": "Shoes",
                "gearTypeName": "Shoes",
                "gearStatusName": "active",
                "dateBegin": "2023-06-01",
            },
            {"displayName": "no uuid"},  # skipped
        ]
    )
    rows = list(GearAdapter(client).fetch(D, date(2024, 1, 20)))
    assert len(rows) == 1
    assert rows[0]["gear_uuid"] == "abc"
    assert rows[0]["name"] == "Shoes"
    assert rows[0]["date_begin"] == date(2023, 6, 1)
    assert rows[0]["date_end"] is None


# ── Training readiness / status ──────────────────────────────────────


def test_training_readiness_parse():
    raw = {
        "score": 80,
        "sleepScore": 90,
        "recoveryScore": 70,
        "trainingLoadScore": 60,
        "hrvScore": 55,
        "level": "READY",
    }
    out = TrainingReadinessAdapter(None)._parse(D, raw)
    assert out["score"] == 80
    assert out["hrv_score"] == 55
    assert out["status"] == "READY"


def test_training_readiness_fetch():
    client = FakeClient(get_training_readiness={"score": 80, "level": "READY"})
    rows = list(TrainingReadinessAdapter(client).fetch(D, date(2024, 1, 16)))
    assert len(rows) == 2
    assert rows[0]["status"] == "READY"


def test_training_status_parse_empty():
    out = TrainingStatusAdapter(None)._parse(D, {})
    assert out["status"] is None
    assert out["load_ratio"] is None
    assert out["date"] == D


# ── Race predictions / lactate threshold (single-shot with break) ────


def test_race_predictions_parse():
    raw = {
        "time5K": 1200,
        "time10K": 2500,
        "timeHalfMarathon": 5400,
        "timeMarathon": 11400,
    }
    out = RacePredictionsAdapter(None)._parse(D, raw)
    assert out["pred_5k_s"] == 1200
    assert out["pred_full_s"] == 11400


def test_race_predictions_fetch_breaks_after_one():
    """Race predictions aren't per-day: fetch yields once then breaks."""
    client = FakeClient(get_race_predictions={"time5K": 1200})
    rows = list(RacePredictionsAdapter(client).fetch(D, date(2024, 1, 31)))
    assert len(rows) == 1
    assert rows[0]["pred_5k_s"] == 1200


def test_lactate_threshold_fetch():
    client = FakeClient(
        get_lactate_threshold={"speed": 3.5, "heartRate": 165, "power": 250}
    )
    rows = list(LactateThresholdAdapter(client).fetch(D, date(2024, 1, 31)))
    assert len(rows) == 1
    assert rows[0]["lt_hr"] == 165
    assert rows[0]["lt_power"] == 250


# ── Adapter metadata ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "adapter_cls,source,table",
    [
        (VO2MaxAdapter, "garmin_api:vo2max", "vo2max"),
        (BodyCompositionAdapter, "garmin_api:body_composition", "body_composition"),
        (BloodPressureAdapter, "garmin_api:blood_pressure", "blood_pressure"),
        (
            TrainingReadinessAdapter,
            "garmin_api:training_readiness",
            "training_readiness",
        ),
        (RacePredictionsAdapter, "garmin_api:race_predictions", "race_predictions"),
    ],
)
def test_adapter_source_and_table_names(adapter_cls, source, table):
    a = adapter_cls(None)
    assert a.source_name() == source
    assert a.target_table() == table
