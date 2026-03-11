from pydantic import BaseModel
from datetime import date


class DailySummaryResponse(BaseModel):
    date: date
    steps: int | None = None
    hr_min: int | None = None
    hr_max: int | None = None
    hr_resting: int | None = None
    stress_avg: int | None = None
    body_battery_max: int | None = None
    body_battery_min: int | None = None
    spo2_avg: float | None = None
    respiration_avg: float | None = None
    sleep_score: int | None = None
    wellness_score: float | None = None
    calories_total: int | None = None
    calories_bmr: int | None = None
    calories_active: int | None = None
    intensity_min_moderate: int | None = None
    intensity_min_vigorous: int | None = None

    model_config = {"from_attributes": True}


class SleepResponse(BaseModel):
    date: date
    total_sleep_min: int | None = None
    deep_sleep_min: int | None = None
    light_sleep_min: int | None = None
    rem_sleep_min: int | None = None
    awake_min: int | None = None
    score: int | None = None
    qualifier: str | None = None
    avg_spo2: float | None = None

    model_config = {"from_attributes": True}
