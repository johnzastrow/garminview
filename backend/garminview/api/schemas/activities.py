from pydantic import BaseModel
from datetime import datetime


class ActivityResponse(BaseModel):
    activity_id: int
    name: str | None
    type: str | None
    sport: str | None
    start_time: datetime | None
    elapsed_time_s: int | None
    distance_m: float | None
    calories: int | None
    avg_hr: int | None
    training_load: float | None
    source: str | None

    model_config = {"from_attributes": True}


class ActivityDetailResponse(ActivityResponse):
    moving_time_s: int | None
    max_hr: int | None
    avg_cadence: int | None
    avg_speed: float | None
    ascent_m: float | None
    descent_m: float | None
    aerobic_effect: float | None
    anaerobic_effect: float | None
