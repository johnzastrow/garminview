"""Backfill core garminview tables from polar_* staging tables.

Garmin-wins: only writes where no Garmin row exists, or existing source='polar'.
Weight excluded — Polar export contains profile settings, not scale measurements.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from garminview.models.activities import Activity, ActivityHRZone
from garminview.models.health import RestingHeartRate, Sleep, SleepEvent
from garminview.models.polar import (
    PolarExercise,
    PolarExerciseStatistic,
    PolarSleep,
    PolarSleepState,
    PolarTrainingSession,
)
from garminview.models.supplemental import VO2Max

_log = logging.getLogger(__name__)

# ── Sport ID mapping ─────────────────────────────────────────────────

_POLAR_SPORT_MAP: dict[str, str] = {
    "1": "running",
    "2": "cycling",
    "11": "other",
    "15": "strength_training",
    "16": "other",
    "17": "treadmill_running",
    "18": "indoor_cycling",
    "20": "hiit",
    "34": "hiit",
    "55": "fitness_equipment",
    "58": "hiit",
    "83": "other",
    "103": "lap_swimming",
    "111": "yoga",
    "113": "backcountry_skiing",
    "117": "indoor_rowing",
    "118": "indoor_cycling",
    "126": "strength_training",
    "127": "yoga",
}


# ── ISO duration parsing ─────────────────────────────────────────────

def _parse_iso_duration_minutes(s: str | None) -> int | None:
    """Parse ISO 8601 duration like PT6H53M30S to total minutes (rounded)."""
    if not s:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", s)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    return round(hours * 60 + minutes + seconds / 60)


def _parse_iso_duration_seconds(s: str | None) -> float:
    """Parse ISO 8601 duration to total seconds."""
    if not s:
        return 0.0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", s)
    if not m:
        return 0.0
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


# ── Helpers ───────────────────────────────────────────────────────────

def _polar_id_to_int(session_id: str) -> int:
    """Convert a Polar session ID to a BigInteger activity_id.

    Most Polar IDs are numeric strings (e.g. "332906208"). For the rare UUID
    IDs, generate a stable 63-bit hash to avoid collisions with Garmin IDs.
    """
    if session_id.isdigit():
        return int(session_id)
    # Stable hash: take first 15 hex chars of MD5 → fits in signed BIGINT
    h = hashlib.md5(session_id.encode()).hexdigest()[:15]
    return int(h, 16)


# ── Activities backfill ──────────────────────────────────────────────

def backfill_polar_activities(session: Session) -> dict[str, Any]:
    """Backfill activities from polar_training_sessions.

    Inserts all Polar sessions that don't collide with a Garmin activity
    within ±5 minutes. Uses source='polar'.
    """
    inserted = 0
    skipped_collision = 0

    # Get all Garmin activity start times for collision check
    garmin_starts = session.query(Activity.start_time).filter(
        Activity.source != "polar"
    ).all()
    garmin_times = {s[0] for s in garmin_starts if s[0]}

    polar_sessions = session.query(PolarTrainingSession).order_by(
        PolarTrainingSession.start_time
    ).all()

    for ps in polar_sessions:
        if not ps.start_time:
            continue

        # Polar stores local time; Garmin stores UTC.
        # Convert Polar local → UTC using tz_offset_min for accurate collision check.
        tz_offset = timedelta(minutes=ps.tz_offset_min) if ps.tz_offset_min else timedelta(0)
        polar_utc = ps.start_time - tz_offset

        # Collision check: any Garmin activity within ±5 minutes?
        collision = any(
            abs((polar_utc - gt).total_seconds()) <= 300
            for gt in garmin_times
        )
        if collision:
            skipped_collision += 1
            continue

        # Check if already backfilled
        act_id = _polar_id_to_int(ps.session_id)
        existing = session.get(Activity, act_id)
        if existing and existing.source != "polar":
            skipped_collision += 1
            continue

        # Get HR stats from exercise statistics
        avg_hr = None
        max_hr = None
        avg_cadence = None
        avg_speed = None

        ex_ids = [
            e[0] for e in session.query(PolarExercise.exercise_id).filter(
                PolarExercise.session_id == ps.session_id
            ).all()
        ]
        stats = session.query(PolarExerciseStatistic).filter(
            PolarExerciseStatistic.exercise_id.in_(ex_ids)
        ).all() if ex_ids else []

        for stat in stats:
            st = stat.stat_type.upper()
            if "HEART_RATE" in st:
                avg_hr = round(stat.avg) if stat.avg else None
                max_hr = round(stat.max) if stat.max else None
            elif "CADENCE" in st:
                avg_cadence = round(stat.avg) if stat.avg else None
            elif "SPEED" in st:
                # Polar's SPEED stat .avg is actually max speed, not average.
                # Calculate true avg_speed from distance / duration instead.
                pass

        # Calculate avg_speed from distance and duration (more accurate)
        if ps.distance_m and ps.duration_ms and ps.duration_ms > 0:
            avg_speed = ps.distance_m / (ps.duration_ms / 1000)
        else:
            avg_speed = None

        sport = _POLAR_SPORT_MAP.get(ps.sport_id, "other")

        activity = Activity(
            activity_id=act_id,
            name=ps.name if ps.name != "None" else sport.replace("_", " ").title(),
            type="polar",
            sport=sport,
            sub_sport=None,
            start_time=polar_utc,
            elapsed_time_s=ps.duration_ms // 1000 if ps.duration_ms else None,
            moving_time_s=None,
            distance_m=ps.distance_m,
            calories=ps.calories,
            avg_hr=avg_hr,
            max_hr=max_hr,
            avg_cadence=avg_cadence,
            avg_speed=avg_speed,
            ascent_m=None,
            descent_m=None,
            training_load=ps.training_load,
            aerobic_effect=None,
            anaerobic_effect=None,
            source="polar",
        )

        if existing and existing.source == "polar":
            for k, v in {c.key: getattr(activity, c.key) for c in Activity.__table__.columns}.items():
                setattr(existing, k, v)
        else:
            session.add(activity)
        inserted += 1

    session.flush()
    _log.info("Polar activities backfill: %d inserted, %d skipped", inserted, skipped_collision)
    return {"activities_inserted": inserted, "activities_skipped": skipped_collision}


# ── Sleep backfill ───────────────────────────────────────────────────

def _compute_sleep_stages(session: Session, night: date, sleep_start: datetime, sleep_end: datetime) -> dict[str, int]:
    """Calculate sleep stage durations from hypnogram state changes.

    Returns dict with keys: deep_min, light_min, rem_min, awake_min.
    """
    states = (
        session.query(PolarSleepState)
        .filter(PolarSleepState.night == night)
        .order_by(PolarSleepState.state_index)
        .all()
    )

    if not states:
        return {"deep_min": 0, "light_min": 0, "rem_min": 0, "awake_min": 0}

    # Calculate total sleep span in seconds
    total_seconds = (sleep_end - sleep_start).total_seconds() if sleep_start and sleep_end else 0

    # Detect if device distinguishes sleep stages or only tracks wake/asleep
    distinct_states = {(s.state or "").upper() for s in states}
    has_full_stages = bool(distinct_states & {"NONREM1", "NONREM2", "REM"})

    # Parse offsets and compute durations
    totals = {"deep_min": 0, "light_min": 0, "rem_min": 0, "awake_min": 0}
    for i, s in enumerate(states):
        offset_sec = _parse_iso_duration_seconds(s.offset_from_start)
        if i + 1 < len(states):
            next_offset = _parse_iso_duration_seconds(states[i + 1].offset_from_start)
        else:
            next_offset = total_seconds
        duration_min = max(0, (next_offset - offset_sec) / 60)

        state = (s.state or "").upper()
        if state == "WAKE":
            totals["awake_min"] += duration_min
        elif has_full_stages:
            # Full sleep stage tracking (Polar Ignite and later)
            if state == "NONREM3":
                totals["deep_min"] += duration_min
            elif state in ("NONREM1", "NONREM2"):
                totals["light_min"] += duration_min
            elif state == "REM":
                totals["rem_min"] += duration_min
        else:
            # Basic wake/asleep only (older Polar devices use NONREM3 = asleep)
            # Can't distinguish stages — leave deep/light/rem as None
            pass

    # Round all to nearest minute
    result = {k: round(v) for k, v in totals.items()}
    if not has_full_stages:
        # Set stages to None rather than 0 — we don't know, not "zero"
        result["deep_min"] = None
        result["light_min"] = None
        result["rem_min"] = None
    return result


def backfill_polar_sleep(session: Session) -> dict[str, Any]:
    """Backfill sleep from polar_sleep + polar_sleep_states.

    Updates existing empty Garmin rows or inserts new ones. source='polar'.
    """
    updated = 0
    inserted = 0
    skipped = 0

    polar_nights = session.query(PolarSleep).order_by(PolarSleep.night).all()

    for ps in polar_nights:
        existing = session.get(Sleep, ps.night)

        # Skip if Garmin has real data
        if existing and existing.total_sleep_min and existing.source != "polar":
            skipped += 1
            continue

        total_min = _parse_iso_duration_minutes(ps.asleep_duration)
        stages = _compute_sleep_stages(session, ps.night, ps.sleep_start, ps.sleep_end)
        score = round(ps.efficiency_pct) if ps.efficiency_pct else None

        if ps.efficiency_pct and ps.efficiency_pct >= 90:
            qualifier = "GOOD"
        elif ps.efficiency_pct and ps.efficiency_pct >= 75:
            qualifier = "FAIR"
        else:
            qualifier = "POOR"

        if existing:
            existing.start = ps.sleep_start
            existing.end = ps.sleep_end
            existing.total_sleep_min = total_min
            existing.deep_sleep_min = stages["deep_min"]
            existing.light_sleep_min = stages["light_min"]
            existing.rem_sleep_min = stages["rem_min"]
            existing.awake_min = stages["awake_min"]
            existing.score = score
            existing.qualifier = qualifier
            existing.source = "polar"
            updated += 1
        else:
            session.add(Sleep(
                date=ps.night,
                start=ps.sleep_start,
                end=ps.sleep_end,
                total_sleep_min=total_min,
                deep_sleep_min=stages["deep_min"],
                light_sleep_min=stages["light_min"],
                rem_sleep_min=stages["rem_min"],
                awake_min=stages["awake_min"],
                score=score,
                qualifier=qualifier,
                source="polar",
            ))
            inserted += 1

        # Sleep events: delete existing for this night, then insert from hypnogram
        session.query(SleepEvent).filter(SleepEvent.date == ps.night).delete(
            synchronize_session=False
        )

        states = (
            session.query(PolarSleepState)
            .filter(PolarSleepState.night == ps.night)
            .order_by(PolarSleepState.state_index)
            .all()
        )

        total_seconds = (
            (ps.sleep_end - ps.sleep_start).total_seconds()
            if ps.sleep_start and ps.sleep_end else 0
        )

        # Detect if this night has full sleep stages
        distinct_states = {(s.state or "").upper() for s in states}
        has_full_stages = bool(distinct_states & {"NONREM1", "NONREM2", "REM"})

        if has_full_stages:
            state_map = {
                "NONREM3": "deep",
                "NONREM1": "light",
                "NONREM2": "light",
                "REM": "rem",
                "WAKE": "awake",
            }
        else:
            # Basic wake/asleep — map NONREM3 to "light" (generic sleep)
            state_map = {
                "NONREM3": "light",
                "WAKE": "awake",
            }

        for i, s in enumerate(states):
            event_type = state_map.get((s.state or "").upper())
            if not event_type:
                continue

            offset_sec = _parse_iso_duration_seconds(s.offset_from_start)
            if i + 1 < len(states):
                next_offset = _parse_iso_duration_seconds(states[i + 1].offset_from_start)
            else:
                next_offset = total_seconds
            duration_min = round(max(0, (next_offset - offset_sec) / 60))

            event_start = ps.sleep_start + timedelta(seconds=offset_sec) if ps.sleep_start else None

            session.add(SleepEvent(
                date=ps.night,
                event_type=event_type,
                start=event_start,
                duration_min=duration_min,
            ))

    session.flush()
    _log.info("Polar sleep backfill: %d updated, %d inserted, %d skipped", updated, inserted, skipped)
    return {"sleep_updated": updated, "sleep_inserted": inserted, "sleep_skipped": skipped}


# ── Resting HR backfill ──────────────────────────────────────────────

def backfill_polar_resting_hr(session: Session) -> dict[str, Any]:
    """Backfill resting_heart_rate from polar_training_sessions.

    For each day with Polar sessions, takes the resting_hr from the earliest session.
    Only inserts where no Garmin row exists.
    """
    inserted = 0
    skipped = 0

    # Get per-day resting HR: earliest session per day
    daily_rhr = (
        session.query(
            func.date(PolarTrainingSession.start_time).label("d"),
            PolarTrainingSession.resting_hr,
        )
        .filter(PolarTrainingSession.resting_hr.isnot(None))
        .order_by(PolarTrainingSession.start_time)
        .all()
    )

    # Deduplicate: keep first (earliest) per day
    seen: dict[str, int] = {}
    for row in daily_rhr:
        d_str = str(row[0])
        if d_str not in seen:
            seen[d_str] = row[1]

    for d_str, rhr in seen.items():
        d = date.fromisoformat(d_str)
        existing = session.get(RestingHeartRate, d)

        if existing and existing.resting_hr is not None and existing.source != "polar":
            skipped += 1
            continue

        if existing:
            existing.resting_hr = rhr
            existing.source = "polar"
        else:
            session.add(RestingHeartRate(date=d, resting_hr=rhr, source="polar"))
        inserted += 1

    session.flush()
    _log.info("Polar resting HR backfill: %d inserted, %d skipped", inserted, skipped)
    return {"resting_hr_inserted": inserted, "resting_hr_skipped": skipped}


# ── VO2max backfill ──────────────────────────────────────────────────

def backfill_polar_vo2max(session: Session) -> dict[str, Any]:
    """Backfill vo2max from polar_training_sessions.

    Takes the VO2max from the latest session per day (most current value).
    Only inserts where no Garmin row exists.
    """
    inserted = 0
    skipped = 0

    # Get per-day VO2max: latest session per day
    daily_vo2 = (
        session.query(
            func.date(PolarTrainingSession.start_time).label("d"),
            PolarTrainingSession.vo2max,
        )
        .filter(PolarTrainingSession.vo2max.isnot(None))
        .order_by(PolarTrainingSession.start_time.desc())
        .all()
    )

    # Deduplicate: keep latest per day
    seen: dict[str, float] = {}
    for row in daily_vo2:
        d_str = str(row[0])
        if d_str not in seen:
            seen[d_str] = row[1]

    for d_str, vo2 in seen.items():
        d = date.fromisoformat(d_str)
        existing = session.get(VO2Max, d)

        if existing and existing.source != "polar":
            skipped += 1
            continue

        if existing:
            existing.vo2max_running = vo2
            existing.source = "polar"
        else:
            session.add(VO2Max(date=d, vo2max_running=vo2, source="polar"))
        inserted += 1

    session.flush()
    _log.info("Polar VO2max backfill: %d inserted, %d skipped", inserted, skipped)
    return {"vo2max_inserted": inserted, "vo2max_skipped": skipped}


# ── Orchestrator ─────────────────────────────────────────────────────

def backfill_all_polar(session: Session) -> dict[str, Any]:
    """Run all Polar backfill functions and commit."""
    result: dict[str, Any] = {}
    result.update(backfill_polar_activities(session))
    result.update(backfill_polar_sleep(session))
    result.update(backfill_polar_resting_hr(session))
    result.update(backfill_polar_vo2max(session))
    session.commit()
    _log.info("Polar backfill complete: %s", result)
    return result
