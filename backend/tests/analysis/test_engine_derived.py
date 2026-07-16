"""Tests for AnalysisEngine._compute_daily_derived — the daily_derived rollup.

Seeds DailySummary + Sleep rows, runs the engine, and asserts the derived
numeric outputs (TRIMP / ATL / CTL / TSB / sleep efficiency) match the metric
functions the engine composes. Includes an edge case where HR inputs are NULL.
"""
from datetime import date

from garminview.analysis.engine import AnalysisEngine
from garminview.analysis.metrics.training_load import (
    calc_trimp, calc_ewma_series, calc_acwr,
)
from garminview.analysis.metrics.sleep_science import calc_sleep_efficiency
from garminview.models.health import DailySummary, Sleep
from garminview.models.derived import DailyDerived


def _run(session):
    AnalysisEngine(session).run_all()


def test_empty_db_produces_no_derived_rows(session):
    _run(session)
    assert session.query(DailyDerived).count() == 0


def test_daily_derived_computes_trimp_and_load(session):
    # Two consecutive days of activity.
    session.add(DailySummary(date=date(2026, 1, 1), hr_avg=140, hr_max=180,
                             intensity_min_moderate=30, intensity_min_vigorous=10))
    session.add(DailySummary(date=date(2026, 1, 2), hr_avg=120, hr_max=170,
                             intensity_min_moderate=20, intensity_min_vigorous=0))
    session.commit()

    _run(session)

    rows = {r.date: r for r in session.query(DailyDerived).all()}
    assert set(rows) == {date(2026, 1, 1), date(2026, 1, 2)}

    # Recompute the expected series exactly as the engine does.
    dur1 = 30 + 10 * 2
    dur2 = 20 + 0 * 2
    trimp1 = calc_trimp(duration_min=dur1, avg_hr=140, max_hr=180)
    trimp2 = calc_trimp(duration_min=dur2, avg_hr=120, max_hr=170)
    atl = calc_ewma_series([trimp1, trimp2], tau=7)
    ctl = calc_ewma_series([trimp1, trimp2], tau=42)

    r1 = rows[date(2026, 1, 1)]
    r2 = rows[date(2026, 1, 2)]
    assert r1.trimp == round(trimp1, 4)
    assert r2.trimp == round(trimp2, 4)
    assert r1.atl == atl[0]
    assert r2.atl == atl[1]
    assert r1.ctl == ctl[0]
    assert r2.tsb == round(ctl[1] - atl[1], 4)
    assert r2.acwr == calc_acwr(atl[1], ctl[1])


def test_daily_derived_sleep_efficiency(session):
    session.add(DailySummary(date=date(2026, 2, 1), hr_avg=130, hr_max=175,
                             intensity_min_moderate=25, intensity_min_vigorous=5))
    session.add(Sleep(date=date(2026, 2, 1), total_sleep_min=420, awake_min=30))
    session.commit()

    _run(session)

    row = session.query(DailyDerived).filter_by(date=date(2026, 2, 1)).one()
    expected = calc_sleep_efficiency(420, 30, 420 + 30)  # 93.33%
    assert row.sleep_efficiency_pct == expected


def test_daily_derived_null_hr_does_not_crash(session):
    # NULL hr_avg / hr_max — engine falls back to defaults (70 / 180) and must
    # still produce a row without raising.
    session.add(DailySummary(date=date(2026, 3, 1), hr_avg=None, hr_max=None,
                             intensity_min_moderate=None, intensity_min_vigorous=None))
    session.commit()

    _run(session)

    row = session.query(DailyDerived).filter_by(date=date(2026, 3, 1)).one()
    # duration = 0 → TRIMP 0; row exists and is finite.
    assert row.trimp == 0.0
    assert row.sleep_efficiency_pct is None  # no Sleep row


def test_daily_derived_is_idempotent(session):
    # Running twice must upsert, not duplicate (date is the PK).
    session.add(DailySummary(date=date(2026, 4, 1), hr_avg=140, hr_max=180,
                             intensity_min_moderate=30, intensity_min_vigorous=10))
    session.commit()
    _run(session)
    _run(session)
    assert session.query(DailyDerived).count() == 1
