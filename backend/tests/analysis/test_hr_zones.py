import pytest
from datetime import date, datetime, timezone
from garminview.analysis.hr_zones import (
    compute_zone_thresholds,
    filter_outliers,
    classify_readings,
    compute_daily_hr_zones,
)
from garminview.models.health import DailyHRZones
from garminview.models.config import UserProfile
from garminview.models.monitoring import MonitoringHeartRate


# ── compute_zone_thresholds ──────────────────────────────────────────────────

def test_zone_thresholds_karvonen():
    # max_hr=180, resting_hr=60 → HRR=120
    thresholds = compute_zone_thresholds(max_hr=180, resting_hr=60)
    assert set(thresholds.keys()) == {1, 2, 3, 4, 5}
    # Zone 1: 50-60% HRR = 60+60=120 to 60+72=132
    assert thresholds[1] == (120, 132)
    # Zone 2: 60-70% HRR = 132 to 144
    assert thresholds[2] == (132, 144)
    # Zone 5 upper bound = max_hr
    assert thresholds[5][1] == 180


def test_zone_thresholds_ascending():
    thresholds = compute_zone_thresholds(max_hr=185, resting_hr=55)
    boundaries = [thresholds[z][0] for z in sorted(thresholds)] + [thresholds[5][1]]
    assert boundaries == sorted(boundaries), "zone boundaries must be ascending"


# ── filter_outliers ──────────────────────────────────────────────────────────

def test_filter_outliers_removes_spikes():
    readings = [65, 120, 150, 220, 250, 70]  # 220, 250 above max_hr+10=190
    valid, rejected = filter_outliers(readings, resting_hr=60, max_hr=180)
    assert 220 not in valid
    assert 250 not in valid
    assert rejected == 2


def test_filter_outliers_removes_low():
    readings = [30, 40, 100, 150]  # 30, 40 below resting_hr-5=55
    valid, rejected = filter_outliers(readings, resting_hr=60, max_hr=180)
    assert 30 not in valid
    assert 40 not in valid
    assert rejected == 2


def test_filter_outliers_all_valid():
    readings = [60, 100, 140, 175]
    valid, rejected = filter_outliers(readings, resting_hr=60, max_hr=180)
    assert valid == readings
    assert rejected == 0


def test_filter_outliers_empty():
    valid, rejected = filter_outliers([], resting_hr=60, max_hr=180)
    assert valid == []
    assert rejected == 0


# ── classify_readings ────────────────────────────────────────────────────────

def test_classify_readings_basic():
    # max_hr=180, resting_hr=60 → Z2=[132,144), Z3=[144,156), Z4=[156,168), Z5=[168,180]
    thresholds = compute_zone_thresholds(max_hr=180, resting_hr=60)
    readings = [133, 133, 145, 157, 170]  # 2×Z2, 1×Z3, 1×Z4, 1×Z5
    counts = classify_readings(readings, thresholds)
    assert counts[2] == 2
    assert counts[3] == 1
    assert counts[4] == 1
    assert counts[5] == 1


def test_classify_readings_below_z1_goes_to_z1():
    thresholds = compute_zone_thresholds(max_hr=180, resting_hr=60)
    # Z1 lower = 120; reading of 65 is below Z1
    counts = classify_readings([65], thresholds)
    assert counts[1] == 1


def test_classify_readings_empty():
    thresholds = compute_zone_thresholds(max_hr=180, resting_hr=60)
    counts = classify_readings([], thresholds)
    assert all(v == 0 for v in counts.values())


# ── compute_daily_hr_zones (integration) ─────────────────────────────────────

def test_compute_daily_hr_zones_writes_row(session):
    # Seed user profile
    session.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
    session.flush()

    # Seed 5 monitoring HR readings on 2026-01-15
    d = date(2026, 1, 15)
    for i, hr_val in enumerate([65, 133, 133, 145, 170]):  # below Z1, Z2, Z2, Z3, Z5
        session.add(MonitoringHeartRate(
            timestamp=datetime(2026, 1, 15, 8, i, 0),  # different minute each
            hr=hr_val,
        ))
    session.commit()

    compute_daily_hr_zones(session, [d])

    row = session.get(DailyHRZones, d)
    assert row is not None
    assert row.z2_min == 2
    assert row.z3_min == 1
    assert row.z5_min == 1
    assert row.total_count == 5
    assert row.rejected_count == 0
    assert row.zone_method == "karvonen"
    assert row.valid_max_hr is not None


def test_compute_daily_hr_zones_no_profile_is_noop(session):
    d = date(2026, 1, 15)
    compute_daily_hr_zones(session, [d])
    row = session.get(DailyHRZones, d)
    assert row is None


def test_compute_daily_hr_zones_filters_outliers(session):
    session.add(UserProfile(id=1, max_hr_override=180, resting_hr=60))
    session.flush()

    d = date(2026, 1, 16)
    # One valid reading + one spike
    for i, hr_val in enumerate([140, 250]):
        session.add(MonitoringHeartRate(timestamp=datetime(2026, 1, 16, 9, i, 0), hr=hr_val))
    session.commit()

    compute_daily_hr_zones(session, [d])

    row = session.get(DailyHRZones, d)
    assert row.rejected_count == 1
    assert row.raw_max_hr == 250
    assert row.valid_max_hr == 140
