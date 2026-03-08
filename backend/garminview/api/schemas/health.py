from pydantic import BaseModel
from datetime import date


class DailySummaryResponse(BaseModel):
    date: date
    steps: int | None
    hr_resting: int | None
    stress_avg: int | None
    body_battery_max: int | None
    sleep_score: int | None
    wellness_score: float | None

    model_config = {"from_attributes": True}


class SleepResponse(BaseModel):
    date: date
    total_sleep_min: int | None
    deep_sleep_min: int | None
    light_sleep_min: int | None
    rem_sleep_min: int | None
    awake_min: int | None
    score: int | None
    qualifier: str | None
    avg_spo2: float | None

    model_config = {"from_attributes": True}
