"""Unit tests for garminview.analysis.metrics.body_composition."""
import pytest

from garminview.analysis.metrics.body_composition import (
    calc_lbm,
    calc_ffmi,
    calc_weight_velocity,
)


def test_lbm():
    # 80 kg at 20% body fat → 64 kg lean mass.
    assert calc_lbm(80.0, 20.0) == 64.0


def test_ffmi():
    # LBM 64 kg, height 1.8 m → 64 / 3.24 = 19.7531
    assert calc_ffmi(64.0, 1.8) == pytest.approx(19.7531, abs=1e-3)


def test_ffmi_nonpositive_height_returns_zero():
    assert calc_ffmi(64.0, 0) == 0.0
    assert calc_ffmi(64.0, -1.8) == 0.0


def test_weight_velocity_loss():
    # 80 → 79 over 7 days → -1.0 kg/week.
    assert calc_weight_velocity([80.0, 79.0], 7) == -1.0


def test_weight_velocity_gain():
    # 80 → 82 over 14 days → +1.0 kg/week.
    assert calc_weight_velocity([80.0, 82.0], 14) == 1.0


def test_weight_velocity_ignores_none():
    # None entries dropped; first/last of the cleaned series drive the slope.
    assert calc_weight_velocity([80.0, None, 79.0], 7) == -1.0


def test_weight_velocity_too_few_points_returns_none():
    assert calc_weight_velocity([80.0], 7) is None


def test_weight_velocity_nonpositive_days_returns_none():
    assert calc_weight_velocity([80.0, 79.0], 0) is None
