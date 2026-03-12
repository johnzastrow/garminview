from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from garminview.models.health import DailySummary, Sleep, RestingHeartRate
from garminview.models.supplemental import HRVData
from garminview.models.derived import DailyDerived
from garminview.analysis.metrics.training_load import (
    calc_trimp, calc_ewma_series, calc_acwr, calc_monotony, calc_strain
)
from garminview.analysis.metrics.sleep_science import (
    calc_sleep_efficiency, calc_sleep_debt
)
from garminview.analysis.metrics.composite_scores import calc_readiness_composite
from garminview.core.logging import get_logger

log = get_logger(__name__)


class AnalysisEngine:
    def __init__(self, session: Session):
        self._session = session

    def run_all(self) -> None:
        log.info("analysis_engine_start")
        self._compute_daily_derived()
        self._compute_weekly_derived()
        self._compute_max_hr_aging()
        self._run_trend_classifications()
        log.info("analysis_engine_complete")

    def _compute_daily_derived(self) -> None:
        if not self._get_earliest_date():
            return

        dialect = self._session.bind.dialect.name  # "sqlite" or "mysql"

        summaries = {r.date: r for r in self._session.query(DailySummary).all()}
        sleeps = {r.date: r for r in self._session.query(Sleep).all()}

        all_dates = sorted(summaries.keys())
        trimp_series = [
            calc_trimp(
                duration_min=(summaries[d].intensity_min_moderate or 0) +
                             (summaries[d].intensity_min_vigorous or 0) * 2,
                avg_hr=summaries[d].hr_avg or 70,
                max_hr=summaries[d].hr_max or 180,
            ) if d in summaries else 0.0
            for d in all_dates
        ]
        atl_series = calc_ewma_series(trimp_series, tau=7)
        ctl_series = calc_ewma_series(trimp_series, tau=42)

        rows = []
        for i, d in enumerate(all_dates):
            atl = atl_series[i]
            ctl = ctl_series[i]
            sleep = sleeps.get(d)
            sleep_eff = None
            if sleep and sleep.total_sleep_min and sleep.awake_min:
                time_in_bed = sleep.total_sleep_min + sleep.awake_min
                sleep_eff = calc_sleep_efficiency(sleep.total_sleep_min,
                                                  sleep.awake_min, time_in_bed)
            rows.append({
                "date": d,
                "trimp": round(trimp_series[i], 4),
                "atl": atl,
                "ctl": ctl,
                "tsb": round(ctl - atl, 4),
                "acwr": calc_acwr(atl, ctl),
                "sleep_efficiency_pct": sleep_eff,
            })

        _BATCH = 500
        for i in range(0, len(rows), _BATCH):
            batch = rows[i:i + _BATCH]
            if dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as _insert
                stmt = _insert(DailyDerived).values(batch)
                non_pk = [c for c in batch[0] if c != "date"]
                stmt = stmt.on_conflict_do_update(index_elements=["date"],
                                                  set_={c: getattr(stmt.excluded, c) for c in non_pk})
            else:
                from sqlalchemy.dialects.mysql import insert as _insert
                stmt = _insert(DailyDerived).values(batch)
                non_pk = [c for c in batch[0] if c != "date"]
                stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in non_pk})
            self._session.execute(stmt)

        self._session.commit()
        log.info("daily_derived_computed", count=len(all_dates))

    def _get_earliest_date(self) -> date | None:
        return self._session.execute(
            select(func.min(DailySummary.date))
        ).scalar()

    def _compute_weekly_derived(self) -> None:
        pass  # Phase 3 continuation

    def _compute_max_hr_aging(self) -> None:
        from garminview.analysis.max_hr_aging import MaxHRAgingAnalysis
        MaxHRAgingAnalysis(self._session).run()

    def _run_trend_classifications(self) -> None:
        pass  # Phase 3 continuation
