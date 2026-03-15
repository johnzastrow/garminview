import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from garminview.ingestion.actalog_sync import ActalogSync
import garminview.models  # noqa: registers all models
from garminview.core.database import Base


def make_workout_detail(workout_id: int, with_movement: bool = True) -> dict:
    detail = {
        "id": workout_id,
        "date": "2026-01-15T09:00:00Z",
        "name": "Morning Strength",
        "type": "strength",
        "duration": 3600,
        "notes": "Felt good",
        "movements": [],
        "wods": [],
    }
    if with_movement:
        detail["movements"] = [{
            "id": 101,
            "movement": {"id": 10, "name": "Back Squat", "type": "weightlifting"},
            "sets": 3, "reps": 5, "weight": 100.0,
            "time": None, "distance": None, "rpe": 8,
            "is_pr": True, "order": 1,
        }]
    return detail


def test_upsert_idempotent(engine, session):
    sync = ActalogSync(session, weight_unit="kg")
    detail = make_workout_detail(1)

    sync._upsert_workout(detail)
    sync._upsert_workout(detail)  # second call must not raise or duplicate
    session.commit()

    from garminview.models.actalog import ActalogWorkout
    count = session.query(ActalogWorkout).count()
    assert count == 1


def test_weight_conversion_lbs(engine, session):
    sync = ActalogSync(session, weight_unit="lbs")
    detail = make_workout_detail(2)
    sync._upsert_workout(detail)
    session.commit()

    from garminview.models.actalog import ActalogWorkoutMovement
    wm = session.query(ActalogWorkoutMovement).first()
    assert wm is not None
    # 100 lbs → 45.359 kg
    assert abs(wm.weight_kg - 45.359) < 0.01


def test_weight_kg_unchanged(engine, session):
    sync = ActalogSync(session, weight_unit="kg")
    detail = make_workout_detail(3)
    sync._upsert_workout(detail)
    session.commit()

    from garminview.models.actalog import ActalogWorkoutMovement
    wm = session.query(ActalogWorkoutMovement).first()
    assert wm.weight_kg == 100.0


def test_pr_aggregation(engine, session):
    """After upsert, _refresh_prs should create one PR row per movement."""
    sync = ActalogSync(session, weight_unit="kg")
    detail = make_workout_detail(4)
    sync._upsert_workout(detail)
    session.commit()

    pr_summaries = [{"movement_id": 10, "best_weight": 100.0, "best_reps": 5, "last_pr_date": "2026-01-15"}]
    sync._refresh_prs(pr_summaries)
    session.commit()

    from garminview.models.actalog import ActalogPersonalRecord
    pr = session.query(ActalogPersonalRecord).filter_by(movement_id=10).first()
    assert pr is not None
    assert pr.max_weight_kg == 100.0
    # best_time_s derived from workout_movements — movement has time=None so NULL
    assert pr.best_time_s is None
