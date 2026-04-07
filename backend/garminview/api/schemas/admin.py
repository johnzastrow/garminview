from pydantic import BaseModel
from datetime import datetime


class TaskItem(BaseModel):
    item_type: str          # "sync" | "action"
    action_key: str | None = None   # "profile_setup" | "anomalies" | "actalog_review"
    title: str
    detail: str | None = None
    link: str | None = None         # frontend route, action items only
    count: int | None = None        # for action items with a count
    timestamp: datetime | None = None   # sync start time; null for action items
    duration_s: float | None = None     # finished_at - started_at
    records_upserted: int | None = None # records_upserted from sync_log
    status: str | None = None           # "success" | "error" | "running"
