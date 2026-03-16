from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from garminview.core.logging import get_logger
from garminview.models.actalog import (
    ActalogWorkout, ActalogMovement, ActalogWod,
    ActalogWorkoutMovement, ActalogWorkoutWod, ActalogPersonalRecord,
)
from garminview.ingestion.actalog_client import ActalogClient
from garminview.ingestion.sync_logger import SyncLogger

log = get_logger(__name__)

LBS_TO_KG = 0.453592


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def _parse_time_score(score: str | None) -> int | None:
    """Parse a mm:ss score string to seconds."""
    if not score:
        return None
    parts = score.split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass
    return None


class ActalogSync:
    def __init__(self, session: Session, weight_unit: str = "kg") -> None:
        self._session = session
        self._weight_unit = weight_unit

    def _to_kg(self, raw: float | None) -> float | None:
        if raw is None:
            return None
        if self._weight_unit == "lbs":
            return round(raw * LBS_TO_KG, 3)
        return raw

    def _upsert(self, model, pk_col: str, pk_val, data: dict) -> None:
        """Generic single-row upsert by integer PK."""
        row = self._session.get(model, pk_val)
        if row is None:
            row = model(**{pk_col: pk_val})
            self._session.add(row)
        for k, v in data.items():
            setattr(row, k, v)

    def _upsert_workout(self, detail: dict) -> None:
        """Upsert one full workout including embedded movements and WODs."""
        wid = detail["id"]
        duration = (detail.get("total_time") or detail.get("duration")
                    or detail.get("total_time_s"))

        self._upsert(ActalogWorkout, "id", wid, {
            "workout_date": _parse_dt(detail.get("workout_date") or detail.get("date")),
            "workout_name": detail.get("workout_name") or detail.get("name"),
            "workout_type": detail.get("workout_type") or detail.get("type"),
            "total_time_s": duration,
            "notes": detail.get("notes"),
            "synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })

        for m in detail.get("movements", []):
            mov = m.get("movement") or {}
            mid = mov.get("id") or m.get("movement_id")
            if mid:
                self._upsert(ActalogMovement, "id", mid, {
                    "name": mov.get("name"),
                    "movement_type": mov.get("type"),
                })
            raw_w = m.get("weight")
            self._upsert(ActalogWorkoutMovement, "id", m["id"], {
                "workout_id": wid,
                "movement_id": mid,
                "sets": m.get("sets"),
                "reps": m.get("reps"),
                "weight_kg": self._to_kg(raw_w),
                "time_s": m.get("time"),
                "distance_m": m.get("distance"),
                "rpe": m.get("rpe"),
                "is_pr": bool(m.get("is_pr", False)),
                "order_index": m.get("order"),
            })

        for w in detail.get("wods", []):
            wod = w.get("wod") or {}
            wodid = wod.get("id") or w.get("wod_id")
            if wodid:
                self._upsert(ActalogWod, "id", wodid, {
                    "name": wod.get("name"),
                    "regime": wod.get("regime"),
                    "score_type": wod.get("score_type"),
                })
            score_val = w.get("score") or w.get("score_value")
            raw_w = w.get("weight")
            self._upsert(ActalogWorkoutWod, "id", w["id"], {
                "workout_id": wid,
                "wod_id": wodid,
                "score_value": score_val,
                "time_s": _parse_time_score(score_val),
                "rounds": w.get("rounds"),
                "reps": w.get("reps"),
                "weight_kg": self._to_kg(raw_w),
                "rpe": w.get("rpe"),
                "is_pr": bool(w.get("is_pr", False)),
                "order_index": w.get("order"),
            })

    def _garmin_duration_fallback(self, workout_id: int) -> None:
        """Try to fill total_time_s from a same-day Garmin activity if null."""
        workout = self._session.get(ActalogWorkout, workout_id)
        if not workout or workout.total_time_s is not None or not workout.workout_date:
            return
        from garminview.models.activities import Activity
        day = workout.workout_date.date()
        matches = (
            self._session.query(Activity)
            .filter(Activity.start_time >= datetime.combine(day, datetime.min.time()))
            .filter(Activity.start_time < datetime.combine(day + timedelta(days=1), datetime.min.time()))
            .filter(Activity.elapsed_time_s.isnot(None))
            .all()
        )
        if len(matches) == 1:
            workout.total_time_s = matches[0].elapsed_time_s
            log.info("actalog_garmin_duration_fallback", workout_id=workout_id)

    def _refresh_prs(self, pr_summaries: list[dict]) -> None:
        """DELETE + INSERT actalog_personal_records from pr-movements data."""
        self._session.query(ActalogPersonalRecord).delete()

        for pr in pr_summaries:
            mid = pr.get("movement_id")
            if not mid:
                continue

            # Derive best_time_s from PR-flagged workout_movements
            best_time_row = self._session.execute(
                text(
                    "SELECT MIN(time_s) FROM actalog_workout_movements "
                    "WHERE movement_id = :mid AND is_pr = 1 AND time_s IS NOT NULL"
                ),
                {"mid": mid},
            ).fetchone()
            best_time_s = best_time_row[0] if best_time_row else None

            # Derive workout_id and workout_date from most recent PR movement
            best_workout_row = self._session.execute(
                text(
                    "SELECT wm.workout_id, w.workout_date "
                    "FROM actalog_workout_movements wm "
                    "JOIN actalog_workouts w ON w.id = wm.workout_id "
                    "WHERE wm.movement_id = :mid AND wm.is_pr = 1 "
                    "ORDER BY w.workout_date DESC LIMIT 1"
                ),
                {"mid": mid},
            ).fetchone()

            raw_w = pr.get("best_weight")
            self._session.add(ActalogPersonalRecord(
                movement_id=mid,
                max_weight_kg=self._to_kg(raw_w),
                max_reps=pr.get("best_reps"),
                best_time_s=best_time_s,
                workout_id=best_workout_row[0] if best_workout_row else None,
                workout_date=(
                    _parse_dt(
                        best_workout_row[1].isoformat()
                        if isinstance(best_workout_row[1], datetime)
                        else str(best_workout_row[1])
                    )
                    if best_workout_row and best_workout_row[1] is not None
                    else _parse_dt(pr.get("last_pr_date"))
                ),
            ))

    async def run(self, client: ActalogClient, sync_log: SyncLogger) -> dict:
        """Execute a full sync. Returns counts dict."""
        counts = {"workouts": 0, "movements": 0, "wods": 0, "prs": 0, "errors": 0}
        try:
            await client.authenticate()
            workout_list = await client.list_workouts()

            for item in workout_list:
                try:
                    detail = await client.get_workout(item["id"])
                    self._upsert_workout(detail)
                    self._garmin_duration_fallback(item["id"])
                    self._session.flush()
                    counts["workouts"] += 1
                    sync_log.increment()
                except Exception as exc:
                    log.warning("actalog_workout_sync_failed", workout_id=item.get("id"), error=str(exc))
                    counts["errors"] += 1

            self._session.commit()

            pr_summaries = await client.list_pr_movements()
            self._refresh_prs(pr_summaries)
            self._session.commit()
            counts["prs"] = len(pr_summaries)

        except Exception as exc:
            self._session.rollback()
            sync_log.fail(str(exc))
            raise

        if counts["workouts"] == 0 and counts["errors"] > 0:
            sync_log.fail(f"All {counts['errors']} workouts failed to sync")
        else:
            sync_log.success()
        return counts
