"""Unit tests for garminview.analysis.metrics.cardiovascular."""
import pytest

from garminview.analysis.metrics.cardiovascular import (
    calc_rhr_zscore,
    calc_hrv_cv,
    calc_heart_rate_recovery,
    calc_cardiac_drift,
)


def test_rhr_zscore_normal():
    # (55 - 50) / 2.5 = 2.0
    assert calc_rhr_zscore(55, 50, 2.5) == 2.0


def test_rhr_zscore_negative():
    assert calc_rhr_zscore(48, 50, 4) == -0.5


def test_rhr_zscore_zero_std_returns_none():
    # Guard against division by zero → None, not a crash.
    assert calc_rhr_zscore(55, 50, 0) is None


def test_hrv_cv_known_series():
    # values [10, 20]: mean 15, stdev (sample) sqrt(50)=7.0710678, CV = 47.1405%
    assert calc_hrv_cv([10, 20]) == pytest.approx(47.1405, abs=1e-3)


def test_hrv_cv_ignores_none_values():
    # None entries are dropped before the calculation.
    assert calc_hrv_cv([10, None, 20]) == pytest.approx(47.1405, abs=1e-3)


def test_hrv_cv_too_few_values_returns_none():
    assert calc_hrv_cv([42]) is None
    assert calc_hrv_cv([None, None]) is None


def test_hrv_cv_zero_mean_returns_none():
    assert calc_hrv_cv([-5, 5]) is None  # mean 0 → None


def test_heart_rate_recovery():
    # HR dropped from 170 to 140 one minute post-exercise → HRR-1 of 30.
    assert calc_heart_rate_recovery(170, 140) == 30


def test_cardiac_drift_positive():
    # (1.05 - 1.00) / 1.00 * 100 = 5.0
    assert calc_cardiac_drift(1.00, 1.05) == 5.0


def test_cardiac_drift_zero_baseline_returns_zero():
    # first-half EF of 0 → guard returns 0.0 rather than dividing by zero.
    assert calc_cardiac_drift(0, 1.05) == 0.0
