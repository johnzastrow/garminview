from pydantic import BaseModel
from datetime import datetime


class ActivityResponse(BaseModel):
    activity_id: int
    name: str | None = None
    type: str | None = None
    sport: str | None = None
    start_time: datetime | None = None
    elapsed_time_s: int | None = None
    distance_m: float | None = None
    calories: int | None = None
    avg_hr: int | None = None
    training_load: float | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class ActivityDetailResponse(ActivityResponse):
    moving_time_s: int | None = None
    max_hr: int | None = None
    avg_cadence: int | None = None
    avg_speed: float | None = None
    ascent_m: float | None = None
    descent_m: float | None = None
    aerobic_effect: float | None = None
    anaerobic_effect: float | None = None
