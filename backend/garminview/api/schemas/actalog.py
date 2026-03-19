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


class ActalogConfigIn(BaseModel):
    url: str | None = None
    email: str | None = None
    password: str | None = None
    weight_unit: str | None = None
    sync_interval_hours: int | None = None
    sync_enabled: bool | None = None


# ---------------------------------------------------------------------------
# Notes parser schemas
# ---------------------------------------------------------------------------

class NoteParseItem(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    workout_id: int | None
    workout_name: str | None = None
    workout_date: datetime | None = None
    content_class: str | None
    parse_status: str | None
    parsed_at: datetime | None
    reviewed_at: datetime | None
    error_message: str | None
    llm_model: str | None
    raw_notes: str | None
    formatted_markdown: str | None = None  # from parsed_json
    parsed_json: str | None
    parse_duration_s: float | None = None
    llm_tokens_prompt: int | None = None
    llm_tokens_generated: int | None = None
    llm_inference_s: float | None = None


class NoteParseQueue(BaseModel):
    total: int
    items: list[NoteParseItem]


class ParserRunResult(BaseModel):
    processed: int
    pending: int
    skipped: int
    errors: int


class ParserModelStats(BaseModel):
    model: str | None
    n: int
    avg_wall_s: float | None
    avg_inference_s: float | None
    avg_tokens_prompt: float | None
    avg_tokens_generated: float | None
    min_wall_s: float | None
    max_wall_s: float | None


class ParserStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_model: list[ParserModelStats]


class ParserConfigOut(BaseModel):
    ollama_url: str | None
    model: str | None
    min_note_length: int | None
    system_prompt: str | None


class ParserConfigIn(BaseModel):
    ollama_url: str | None = None
    model: str | None = None
    min_note_length: int | None = None
    system_prompt: str | None = None


class NoteParseApproveIn(BaseModel):
    formatted_markdown: str | None = None  # optional human edit before approve
    performance_notes: str | None = None


class ParserJobStatus(BaseModel):
    running: bool
    total_staged: int
