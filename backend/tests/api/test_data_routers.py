"""Tests for the UI-facing data routers: activities, body, training,
assessments, and nutrition. Each seeds real rows, GETs the endpoint, and
asserts JSON shape, date filtering, and empty-DB behaviour.
"""
from datetime import date, datetime

from garminview.models.activities import Activity, ActivityHRZone, StepsActivity
from garminview.models.health import Weight, DailySummary
from garminview.models.supplemental import BodyComposition, TrainingReadiness
from garminview.models.derived import DailyDerived, MaxHRAgingYear
from garminview.models.assessments import Assessment, CorrelationResult, DataQualityFlag
from garminview.models.nutrition import MFPDailyNutrition


# --- activities ----------------------------------------------------------

def _seed_activities(s):
    s.add(Activity(activity_id=1, name="Morning Run", type="run", sport="running",
                   start_time=datetime(2026, 1, 10, 7, 0), distance_m=5000, avg_hr=150,
                   max_hr=175, elapsed_time_s=1800, avg_speed=2.8))
    s.add(Activity(activity_id=2, name="Evening Ride", type="cycling", sport="cycling",
                   start_time=datetime(2026, 2, 15, 18, 0), distance_m=20000, avg_hr=130,
                   max_hr=160, elapsed_time_s=3600))


def test_list_activities_empty(make_client):
    client = make_client()
    resp = client.get("/activities/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_activities_ordered_desc(make_client):
    client = make_client(_seed_activities)
    resp = client.get("/activities/")
    assert resp.status_code == 200
    data = resp.json()
    assert [a["activity_id"] for a in data] == [2, 1]  # newest first
    assert data[0]["name"] == "Evening Ride"


def test_list_activities_filter_by_sport(make_client):
    client = make_client(_seed_activities)
    resp = client.get("/activities/", params={"sport": "running"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["activity_id"] == 1


def test_list_activities_date_filter(make_client):
    client = make_client(_seed_activities)
    resp = client.get("/activities/", params={"start": "2026-02-01", "end": "2026-02-28"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["activity_id"] == 2


def test_get_activity_detail(make_client):
    client = make_client(_seed_activities)
    resp = client.get("/activities/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["activity_id"] == 1
    assert body["max_hr"] == 175
    assert body["avg_speed"] == 2.8


def test_get_activity_missing_404(make_client):
    client = make_client(_seed_activities)
    resp = client.get("/activities/999")
    assert resp.status_code == 404


def test_activities_hr_zones_aggregate(make_client):
    def seed(s):
        _seed_activities(s)
        s.add(ActivityHRZone(activity_id=1, zone=2, time_in_zone_s=600))
        s.add(ActivityHRZone(activity_id=1, zone=3, time_in_zone_s=400))
        s.add(ActivityHRZone(activity_id=2, zone=2, time_in_zone_s=300))
    client = make_client(seed)
    resp = client.get("/activities/hr-zones")
    assert resp.status_code == 200
    data = resp.json()
    by_zone = {r["zone"]: r["total_s"] for r in data}
    assert by_zone[2] == 900  # 600 + 300 summed across activities
    assert by_zone[3] == 400


def test_activities_vo2max_trend(make_client):
    def seed(s):
        _seed_activities(s)
        s.add(StepsActivity(activity_id=1, vo2max=52.4))
        s.add(StepsActivity(activity_id=2, vo2max=None))  # excluded (NULL)
    client = make_client(seed)
    resp = client.get("/activities/vo2max-trend")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["date"] == "2026-01-10"
    assert data[0]["vo2max"] == 52.4


# --- body ----------------------------------------------------------------

def test_weight_trend_and_filter(make_client):
    def seed(s):
        s.add(Weight(date=date(2026, 1, 1), weight_kg=80.0))
        s.add(Weight(date=date(2026, 1, 15), weight_kg=79.2))
        s.add(Weight(date=date(2026, 3, 1), weight_kg=78.0))
    client = make_client(seed)

    # Full range, ordered ascending by date.
    resp = client.get("/body/weight")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["weight_kg"] for r in data] == [80.0, 79.2, 78.0]

    # Date-filtered window.
    resp = client.get("/body/weight", params={"start": "2026-01-10", "end": "2026-02-01"})
    assert [r["date"] for r in resp.json()] == ["2026-01-15"]


def test_weight_empty(make_client):
    client = make_client()
    assert client.get("/body/weight").json() == []


def test_body_composition(make_client):
    def seed(s):
        s.add(BodyComposition(date=date(2026, 1, 5), weight_kg=80.0, fat_pct=18.5,
                              muscle_mass_kg=62.0, bmi=24.1, bmr=1750))
    client = make_client(seed)
    resp = client.get("/body/composition")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["fat_pct"] == 18.5
    assert data[0]["bmr"] == 1750


# --- training ------------------------------------------------------------

def test_training_load(make_client):
    def seed(s):
        s.add(DailyDerived(date=date(2026, 1, 1), trimp=100.0, atl=50.0, ctl=40.0,
                           tsb=-10.0, acwr=1.25))
        s.add(DailyDerived(date=date(2026, 1, 2), trimp=80.0, atl=55.0, ctl=42.0,
                           tsb=-13.0, acwr=1.31))
    client = make_client(seed)
    resp = client.get("/training/load")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["date"] for r in data] == ["2026-01-01", "2026-01-02"]
    assert data[0]["tsb"] == -10.0
    assert data[1]["acwr"] == 1.31


def test_training_load_date_filter(make_client):
    def seed(s):
        s.add(DailyDerived(date=date(2026, 1, 1), trimp=100.0))
        s.add(DailyDerived(date=date(2026, 6, 1), trimp=90.0))
    client = make_client(seed)
    resp = client.get("/training/load", params={"start": "2026-05-01", "end": "2026-06-30"})
    assert [r["date"] for r in resp.json()] == ["2026-06-01"]


def test_training_readiness(make_client):
    def seed(s):
        s.add(TrainingReadiness(date=date(2026, 1, 1), score=78, sleep_score=80,
                                recovery_score=75, hrv_score=70, status="ready"))
    client = make_client(seed)
    resp = client.get("/training/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["score"] == 78
    assert data[0]["status"] == "ready"


def test_max_hr_aging(make_client):
    def seed(s):
        s.add(MaxHRAgingYear(year=2025, annual_peak_hr=185, activity_count=120,
                             age_predicted_max=178.0))
        s.add(MaxHRAgingYear(year=2024, annual_peak_hr=188, activity_count=140))
    client = make_client(seed)
    resp = client.get("/training/max-hr-aging")
    assert resp.status_code == 200
    data = resp.json()
    assert [r["year"] for r in data] == [2024, 2025]  # ordered by year asc
    assert data[1]["annual_peak_hr"] == 185


# --- assessments ---------------------------------------------------------

def test_list_assessments_and_period_filter(make_client):
    def seed(s):
        s.add(Assessment(period_type="weekly", period_start=date(2026, 1, 5),
                         category="sleep", severity="info", summary_text="ok"))
        s.add(Assessment(period_type="monthly", period_start=date(2026, 1, 1),
                         category="training", severity="warning", summary_text="high load"))
    client = make_client(seed)

    resp = client.get("/assessments/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/assessments/", params={"period_type": "weekly"})
    data = resp.json()
    assert len(data) == 1
    assert data[0]["category"] == "sleep"


def test_correlation_matrix(make_client):
    def seed(s):
        s.add(CorrelationResult(computed_at=datetime(2026, 1, 1, 0, 0),
                                metric_a="sleep", metric_b="hrv",
                                r_pearson=0.65, p_value=0.01))
    client = make_client(seed)
    resp = client.get("/assessments/correlations/matrix")
    assert resp.status_code == 200
    corrs = resp.json()["correlations"]
    assert len(corrs) == 1
    assert corrs[0]["metric_a"] == "sleep"
    assert corrs[0]["r_pearson"] == 0.65


def test_data_quality_completeness(make_client):
    def seed(s):
        s.add(DataQualityFlag(date=date(2026, 1, 1), metric="steps", flag_type="missing"))
        s.add(DataQualityFlag(date=date(2026, 1, 2), metric="hr", flag_type="implausible"))
    client = make_client(seed)
    resp = client.get("/assessments/data-quality/completeness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_flags"] == 2
    assert {f["flag_type"] for f in body["flags"]} == {"missing", "implausible"}


def test_data_quality_empty(make_client):
    client = make_client()
    resp = client.get("/assessments/data-quality/completeness")
    assert resp.status_code == 200
    assert resp.json() == {"total_flags": 0, "flags": []}


# --- nutrition -----------------------------------------------------------

def test_nutrition_daily(make_client):
    def seed(s):
        s.add(MFPDailyNutrition(date=date(2026, 1, 1), calories_in=2100,
                                protein_g=150.0, carbs_g=200.0, fat_g=70.0))
    client = make_client(seed)
    resp = client.get("/nutrition/daily")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["calories_in"] == 2100
    assert data[0]["protein_g"] == 150.0


def test_energy_balance_computes_deficit(make_client):
    def seed(s):
        # Day with both sides present → balance = 2100 - 2600 = -500.
        s.add(MFPDailyNutrition(date=date(2026, 1, 1), calories_in=2100, protein_g=150.0))
        s.add(DailySummary(date=date(2026, 1, 1), calories_total=2600))
        # Day with only nutrition → balance None (no Garmin calories_out).
        s.add(MFPDailyNutrition(date=date(2026, 1, 2), calories_in=1800))
    client = make_client(seed)
    resp = client.get("/nutrition/energy-balance")
    assert resp.status_code == 200
    by_date = {r["date"]: r for r in resp.json()}
    assert by_date["2026-01-01"]["calories_out"] == 2600
    assert by_date["2026-01-01"]["energy_balance"] == -500
    assert by_date["2026-01-02"]["calories_out"] is None
    assert by_date["2026-01-02"]["energy_balance"] is None
