"""Match Actalog workouts to Garmin activities by date + duration.

Actalog stores `workout_date` as date-only (midnight). To pull realistic
heart-rate data for a workout, we need the actual start time of day,
which lives in the Garmin `activities` table. This module finds the best
candidate Garmin activity for a given Actalog workout, or enumerates all
activities on the day for manual disambiguation in the UI.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from garminview.models.activities import Activity
from garminview.models.actalog import ActalogWorkout


# Proportional duration tolerance for a "clear winner" auto-match. Top
# candidate must land within this ratio (so a 1800s workout matches
# activities between ~1260s and ~2340s). If the top candidate falls
# outside this bound, we decline to auto-match and let the user pick.
_DURATION_TOLERANCE = 0.30

# If two candidates land within this ratio of one another in duration,
# we call the match ambiguous rather than auto-picking one.
_AMBIGUITY_MARGIN = 0.10


def _workout_day(workout: ActalogWorkout) -> date | None:
    return workout.workout_date.date() if workout.workout_date else None


def list_candidates(session: Session, workout: ActalogWorkout) -> list[Activity]:
    """All Garmin activities on the same calendar date as the workout.

    No sport-type filter — the UI presents everything so the user can
    resolve ambiguous cases (e.g. a strength class that Garmin logged as
    "other"). Sorted by start_time ascending so the morning entries come
    first, which is the typical user mental model.
    """
    day = _workout_day(workout)
    if day is None:
        return []
    day_start = datetime.combine(day, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    return (
        session.query(Activity)
        .filter(Activity.start_time >= day_start)
        .filter(Activity.start_time < day_end)
        .order_by(Activity.start_time.asc())
        .all()
    )


def auto_match(session: Session, workout: ActalogWorkout) -> Activity | None:
    """Return the activity closest in duration to the workout, or None.

    Criteria (in order):
      1. Same calendar date as `workout.workout_date`.
      2. Closest `elapsed_time_s` to `workout.total_time_s`.
      3. Top candidate must be within ±30% of the workout's duration.
      4. No other candidate may be within 10% of the top candidate's
         duration difference (ambiguous → decline).

    If `workout.total_time_s` is unknown, we can't rank, so we return
    None and leave it for manual selection.
    """
    if workout.total_time_s is None or workout.total_time_s <= 0:
        return None

    candidates = list_candidates(session, workout)
    if not candidates:
        return None

    target = float(workout.total_time_s)

    def delta(a: Activity) -> float:
        if a.elapsed_time_s is None:
            return float("inf")
        return abs(a.elapsed_time_s - target)

    ranked = sorted(candidates, key=delta)
    top = ranked[0]
    top_delta = delta(top)
    if top_delta == float("inf"):
        return None

    # Must land within tolerance of the target duration.
    if top_delta > target * _DURATION_TOLERANCE:
        return None

    # If a runner-up is within 10% of the top's delta, it's a tie — the
    # user needs to disambiguate.
    if len(ranked) > 1:
        runner_up_delta = delta(ranked[1])
        if runner_up_delta != float("inf") and \
           abs(runner_up_delta - top_delta) <= target * _AMBIGUITY_MARGIN:
            return None

    return top


def resolve_activity(
    session: Session, workout: ActalogWorkout,
) -> tuple[Activity | None, str]:
    """Return the activity we should use for HR lookup and a status string.

    Status values:
      - ``"linked"``       — user explicitly picked this activity
      - ``"none"``         — user explicitly said no Garmin activity exists
      - ``"auto"``         — auto-match found a clear winner (not yet confirmed)
      - ``"ambiguous"``    — candidates exist but no clear winner
      - ``"unavailable"``  — no Garmin activities on that date at all
    """
    if workout.garmin_match_confirmed:
        if workout.garmin_activity_id is not None:
            act = session.get(Activity, workout.garmin_activity_id)
            return act, "linked"
        return None, "none"

    auto = auto_match(session, workout)
    if auto is not None:
        return auto, "auto"

    if list_candidates(session, workout):
        return None, "ambiguous"
    return None, "unavailable"
