"""
Max HR Aging analysis.

Computes annual max HR statistics from activity data and compares against
the age-predicted Tanaka formula (208 - 0.7 × age) to track the rate of
HR ceiling decline over the period of record.
"""
import numpy as np
from scipy import stats
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select

from garminview.models.activities import Activity
from garminview.models.health import RestingHeartRate
from garminview.models.config import UserProfile
from garminview.models.derived import MaxHRAgingYear
from garminview.core.logging import get_logger

log = get_logger(__name__)

# Sport/type values to EXCLUDE — submaximal or non-cardio activities
_EXCLUDED_SPORTS = {
    "strength_training", "yoga", "flexibility", "meditation",
    "breathing", "indoor_rowing", "pilates", "barre", "stretching",
    "walk", "walking",
}

# Minimum criteria for a usable max-HR reading
_MIN_DURATION_S = 600   # 10 minutes
_MIN_HR = 130           # discard warm-up-only or sensor artefact sessions


class MaxHRAgingAnalysis:
    def __init__(self, session: Session):
        self._session = session

    def run(self) -> None:
        activities = self._load_activities()
        if not activities:
            log.info("max_hr_aging_no_data")
            return

        dob = self._get_dob()
        rhr_by_year = self._load_rhr_by_year()

        # Group qualifying max_hr values by calendar year
        by_year: dict[int, list[int]] = {}
        for a in activities:
            if not a.start_time or not a.max_hr:
                continue
            sport = (a.sport or a.type or "").lower()
            if sport in _EXCLUDED_SPORTS:
                continue
            if (a.elapsed_time_s or 0) < _MIN_DURATION_S:
                continue
            if a.max_hr < _MIN_HR:
                continue
            yr = a.start_time.year
            by_year.setdefault(yr, []).append(a.max_hr)

        if not by_year:
            log.info("max_hr_aging_no_qualifying_activities")
            return

        years = sorted(by_year)
        p90_series = []
        rows = []

        for yr in years:
            hrs = np.array(by_year[yr])
            peak = int(hrs.max())
            p95 = float(np.percentile(hrs, 95))
            p90 = float(np.percentile(hrs, 90))
            p90_series.append(p90)

            age_pred = self._tanaka(dob, yr) if dob else None
            rhr = rhr_by_year.get(yr)
            reserve = (p90 - rhr) if rhr else None
            pct = (p90 / age_pred * 100) if age_pred else None

            rows.append({
                "year": yr,
                "annual_peak_hr": peak,
                "annual_p95_hr": round(p95, 2),
                "annual_p90_hr": round(p90, 2),
                "activity_count": len(hrs),
                "age_predicted_max": round(age_pred, 2) if age_pred else None,
                "hr_reserve": round(reserve, 2) if reserve else None,
                "pct_age_predicted": round(pct, 2) if pct else None,
                "decline_rate_bpm_per_year": None,  # filled after regression
            })

        # Linear regression on p90 vs year to get decline rate
        decline_rate = None
        if len(years) >= 3:
            slope, _, _, _, _ = stats.linregress(years, p90_series)
            decline_rate = round(slope, 4)  # negative = declining

        for row in rows:
            row["decline_rate_bpm_per_year"] = decline_rate

        self._upsert(rows)
        log.info("max_hr_aging_computed", years=len(rows), decline_rate=decline_rate)

    def _load_activities(self) -> list:
        return self._session.execute(
            select(Activity).where(Activity.max_hr.isnot(None))
        ).scalars().all()

    def _get_dob(self) -> date | None:
        profile = self._session.get(UserProfile, 1)
        return profile.birth_date if profile else None

    def _load_rhr_by_year(self) -> dict[int, float]:
        """Return average resting HR per calendar year."""
        rows = self._session.execute(select(RestingHeartRate)).scalars().all()
        by_year: dict[int, list[int]] = {}
        for r in rows:
            if r.resting_hr:
                by_year.setdefault(r.date.year, []).append(r.resting_hr)
        return {yr: float(np.mean(vals)) for yr, vals in by_year.items()}

    @staticmethod
    def _tanaka(dob: date, year: int) -> float:
        """Tanaka (2001) age-predicted max HR: 208 - 0.7 × age."""
        age = year - dob.year
        return 208 - 0.7 * age

    def _upsert(self, rows: list[dict]) -> None:
        dialect = self._session.bind.dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _insert
        else:
            from sqlalchemy.dialects.mysql import insert as _insert

        if not rows:
            return

        if dialect == "sqlite":
            stmt = _insert(MaxHRAgingYear).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["year"],
                set_={k: getattr(stmt.excluded, k) for k in rows[0] if k != "year"},
            )
        else:
            stmt = _insert(MaxHRAgingYear).values(rows)
            stmt = stmt.on_duplicate_key_update(
                **{k: stmt.inserted[k] for k in rows[0] if k != "year"}
            )

        self._session.execute(stmt)
        self._session.commit()
