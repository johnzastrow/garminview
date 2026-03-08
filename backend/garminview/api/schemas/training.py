from pydantic import BaseModel
from datetime import date


class TrainingLoadResponse(BaseModel):
    date: date
    trimp: float | None
    atl: float | None
    ctl: float | None
    tsb: float | None
    acwr: float | None

    model_config = {"from_attributes": True}


class TrainingReadinessResponse(BaseModel):
    date: date
    score: int | None
    sleep_score: int | None
    recovery_score: int | None
    hrv_score: int | None
    status: str | None

    model_config = {"from_attributes": True}
