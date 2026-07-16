"""Tests for garminview.analysis.energy_balance.

The module itself only computes and logs coverage (nutrition-day / Garmin-day
overlap); the actual per-day energy balance is computed at query time in the
/nutrition/energy-balance endpoint (covered in tests/api/test_data_routers.py).
Here we assert the coverage path runs, short-circuits when there's no nutrition
data, and logs the correct matched-day count.
"""
from datetime import date
from unittest.mock import MagicMock

from garminview.analysis import energy_balance as eb_mod
from garminview.analysis.energy_balance import EnergyBalanceAnalysis
from garminview.models.nutrition import MFPDailyNutrition
from garminview.models.health import DailySummary


def test_run_no_nutrition_short_circuits(session, monkeypatch):
    # No MFP rows at all → run() returns immediately without logging coverage.
    mock_log = MagicMock()
    monkeypatch.setattr(eb_mod, "log", mock_log)

    EnergyBalanceAnalysis(session).run()

    # The coverage log line must never be emitted when there's no nutrition.
    events = [c.args[0] for c in mock_log.info.call_args_list if c.args]
    assert "energy_balance_coverage" not in events


def test_run_reports_matched_days(session, monkeypatch):
    # 3 nutrition days, 2 of which overlap Garmin daily summaries → matched=2.
    session.add(MFPDailyNutrition(date=date(2026, 1, 1), calories_in=2000))
    session.add(MFPDailyNutrition(date=date(2026, 1, 2), calories_in=2100))
    session.add(MFPDailyNutrition(date=date(2026, 1, 3), calories_in=1900))
    session.add(DailySummary(date=date(2026, 1, 1), calories_total=2500))
    session.add(DailySummary(date=date(2026, 1, 2), calories_total=2600))
    session.commit()

    mock_log = MagicMock()
    monkeypatch.setattr(eb_mod, "log", mock_log)

    EnergyBalanceAnalysis(session).run()

    coverage_calls = [
        c for c in mock_log.info.call_args_list
        if c.args and c.args[0] == "energy_balance_coverage"
    ]
    assert len(coverage_calls) == 1
    kwargs = coverage_calls[0].kwargs
    assert kwargs["nutrition_days"] == 3
    assert kwargs["garmin_days"] == 2
    assert kwargs["matched_days"] == 2
