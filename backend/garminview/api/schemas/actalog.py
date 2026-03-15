from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class WorkoutListItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    workout_date: datetime | None
    workout_name: str | None
    workout_type: str | None
    total_time_s: int | None


class MovementItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    workout_id: int | None
    movement_id: int | None
    sets: int | None
    reps: int | None
    weight_kg: float | None
    time_s: int | None
    distance_m: float | None
    rpe: int | None
    is_pr: bool
    order_index: int | None


class WodItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    workout_id: int | None
    wod_id: int | None
    score_value: str | None
    time_s: int | None
    rounds: int | None
    reps: int | None
    weight_kg: float | None
    rpe: int | None
    is_pr: bool
    order_index: int | None


class WorkoutDetail(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    workout_date: datetime | None
    workout_name: str | None
    workout_type: str | None
    total_time_s: int | None
    notes: str | None
    movements: list[MovementItem]
    wods: list[WodItem]


class SessionVitals(BaseModel):
    workout: WorkoutDetail
    has_vitals: bool
    hr_series: list[dict] = []
    body_battery: list[dict] = []
    stress: list[dict] = []


class MovementRef(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str | None
    movement_type: str | None


class MovementHistoryItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    workout_id: int | None
    sets: int | None
    reps: int | None
    weight_kg: float | None
    time_s: int | None
    rpe: int | None
    is_pr: bool
    workout_date: datetime | None  # joined from workout


class PRItem(BaseModel):
    model_config = {"from_attributes": True}
    movement_id: int
    movement_name: str | None
    movement_type: str | None
    max_weight_kg: float | None
    max_reps: int | None
    best_time_s: int | None
    workout_date: datetime | None


class CrossRefItem(BaseModel):
    workout_date: datetime | None
    workout_name: str | None
    workout_type: str | None
    total_volume_kg: float | None
    body_battery_max: int | None
    hr_resting: int | None
    sleep_score: int | None
    stress_avg: int | None


class ActalogConfigOut(BaseModel):
    url: str | None
    email: str | None
    weight_unit: str | None
    sync_interval_hours: int | None
    sync_enabled: bool
    last_sync: str | None


class ActalogSyncStatus(BaseModel):
    last_sync: str | None
    status: str | None
    records_upserted: int | None
    error_message: str | None
