"""
HR zone analysis: Karvonen zone computation, outlier filtering,
daily classification from monitoring_heart_rate → daily_hr_zones.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from garminview.models.config import UserProfile
from garminview.models.health import DailyHRZones
from garminview.models.monitoring import MonitoringHeartRate


def compute_zone_thresholds(max_hr: int, resting_hr: int) -> dict[int, tuple[int, int]]:
    """Return Karvonen zone boundaries {zone: (lo_bpm, hi_bpm)}.

    Uses HR Reserve (HRR) percentages:
      Zone 1: 50–60%  Zone 2: 60–70%  Zone 3: 70–80%
      Zone 4: 80–90%  Zone 5: 90–100%
    """
    hrr = max_hr - resting_hr
    pcts = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
    bpms = [round(resting_hr + p * hrr) for p in pcts]
    return {z: (bpms[z - 1], bpms[z]) for z in range(1, 6)}


def filter_outliers(
    readings: list[int], resting_hr: int, max_hr: int
) -> tuple[list[int], int]:
    """Remove readings outside [resting_hr−5, max_hr+10].

    Returns (valid_readings, rejected_count).
    """
    lo = resting_hr - 5
    hi = max_hr + 10
    valid = [r for r in readings if lo <= r <= hi]
    return valid, len(readings) - len(valid)


def classify_readings(
    valid_readings: list[int], thresholds: dict[int, tuple[int, int]]
) -> dict[int, int]:
    """Count valid readings per zone.

    Readings below the Zone 1 lower bound count as Zone 1.
    Readings at or above the Zone 5 upper bound count as Zone 5.
    Returns {zone: count}.
    """
    counts = {z: 0 for z in thresholds}
    sorted_zones = sorted(thresholds.items())
    min_lo = sorted_zones[0][1][0]
    max_hi = sorted_zones[-1][1][1]

    for r in valid_readings:
        if r < min_lo:
            counts[sorted_zones[0][0]] += 1
        elif r >= max_hi:
            counts[sorted_zones[-1][0]] += 1
        else:
            for zone, (lo, hi) in sorted_zones:
                if lo <= r < hi:
                    counts[zone] += 1
                    break

    return counts


def _percentile_97(values: list[int]) -> int:
    """97th percentile using linear interpolation. Pure Python, no numpy."""
    if not values:
        raise ValueError("empty list")
    s = sorted(values)
    idx = (len(s) - 1) * 0.97
    lo = int(idx)
    hi = lo + 1
    if hi >= len(s):
        return s[-1]
    frac = idx - lo
    return round(s[lo] + frac * (s[hi] - s[lo]))


def compute_daily_hr_zones(session: Session, dates: list[date]) -> None:
    """Compute and upsert daily_hr_zones rows for the given dates.

    Silently returns if user_profile has no max_hr_override or resting_hr.
    """
    profile = session.query(UserProfile).first()
    if not profile or not profile.max_hr_override or not profile.resting_hr:
        return

    max_hr = profile.max_hr_override
    resting_hr = profile.resting_hr
    thresholds = compute_zone_thresholds(max_hr, resting_hr)

    dialect = session.bind.dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _ins
    else:
        from sqlalchemy.dialects.mysql import insert as _ins

    for d in dates:
        day_start = datetime(d.year, d.month, d.day)
        day_end = day_start + timedelta(days=1)

        rows = (
            session.query(MonitoringHeartRate.hr)
            .filter(MonitoringHeartRate.timestamp >= day_start)
            .filter(MonitoringHeartRate.timestamp < day_end)
            .filter(MonitoringHeartRate.hr.isnot(None))
            .all()
        )
        all_readings = [r.hr for r in rows]
        raw_max = max(all_readings) if all_readings else None

        valid_readings, rejected_count = filter_outliers(all_readings, resting_hr, max_hr)
        valid_max = _percentile_97(valid_readings) if valid_readings else None
        zone_counts = (
            classify_readings(valid_readings, thresholds)
            if valid_readings
            else {z: 0 for z in thresholds}
        )

        row_data = {
            "date": d,
            "z1_min": zone_counts[1],
            "z2_min": zone_counts[2],
            "z3_min": zone_counts[3],
            "z4_min": zone_counts[4],
            "z5_min": zone_counts[5],
            "valid_max_hr": valid_max,
            "raw_max_hr": raw_max,
            "rejected_count": rejected_count,
            "total_count": len(all_readings),
            "zone_method": "karvonen",
            "computed_at": datetime.now(timezone.utc),
        }
        non_pk = [c for c in row_data if c != "date"]
        stmt = _ins(DailyHRZones).values([row_data])
        if dialect == "sqlite":
            stmt = stmt.on_conflict_do_update(
                index_elements=["date"],
                set_={c: getattr(stmt.excluded, c) for c in non_pk},
            )
        else:
            stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_pk})
        session.execute(stmt)

    session.commit()
