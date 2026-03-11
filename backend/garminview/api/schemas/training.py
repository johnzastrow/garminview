from pydantic import BaseModel
from datetime import date


class TrainingLoadResponse(BaseModel):
    date: date
    trimp: float | None = None
    atl: float | None = None
    ctl: float | None = None
    tsb: float | None = None
    acwr: float | None = None

    model_config = {"from_attributes": True}


class TrainingReadinessResponse(BaseModel):
    date: date
    score: int | None = None
    sleep_score: int | None = None
    recovery_score: int | None = None
    hrv_score: int | None = None
    status: str | None = None

    model_config = {"from_attributes": True}


class MaxHRAgingYearResponse(BaseModel):
    year: int
    annual_peak_hr: int | None = None
    annual_p95_hr: float | None = None
    annual_p90_hr: float | None = None
    activity_count: int | None = None
    age_predicted_max: float | None = None
    hr_reserve: float | None = None
    pct_age_predicted: float | None = None
    decline_rate_bpm_per_year: float | None = None

    model_config = {"from_attributes": True}
